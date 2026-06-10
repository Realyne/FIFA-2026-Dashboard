"""Group standings, third-place allocation, and bracket resolution."""
from wc2026 import resolver, static_data
from wc2026.models import MatchState, SideState


def finished(n, home, away, hs, as_, pens=None):
    m = static_data.bracket_by_number()[n]
    return MatchState(
        match_number=n, status="finished",
        home=SideState(fifa_code=home, score=hs, pen_score=pens[0] if pens else None),
        away=SideState(fifa_code=away, score=as_, pen_score=pens[1] if pens else None),
        kickoff_utc=m["kickoff_utc"], venue_id=m["venue_id"],
        round=m["round"], group=m["group"],
    )


def group_a_states(results):
    """results: list of (hs, as) for group A's six matches in order."""
    ms = sorted(static_data.group_matches()["A"], key=lambda m: m["match_number"])
    return {
        m["match_number"]: finished(m["match_number"], m["home_slot"], m["away_slot"], hs, as_)
        for m, (hs, as_) in zip(ms, results)
    }


def test_group_standings_points_and_gd():
    # A: MEX-RSA 2-0, KOR-CZE 1-1, CZE-RSA 0-0, MEX-KOR 1-0, CZE-MEX 0-3, RSA-KOR 0-2
    states = group_a_states([(2, 0), (1, 1), (0, 0), (1, 0), (0, 3), (0, 2)])
    s = resolver.group_standings("A", states)
    assert s["complete"]
    codes = [r["fifa_code"] for r in s["rows"]]
    assert codes[0] == "MEX"  # 9 pts
    assert codes[1] == "KOR"  # 4 pts, beat RSA
    mex = s["rows"][0]
    assert mex["points"] == 9 and mex["gf"] == 6 and mex["ga"] == 0


def test_group_standings_head_to_head_breaks_tie():
    # MEX and KOR finish level on points/gd/gf; KOR beat MEX head-to-head.
    # MEX-RSA 2-0, KOR-CZE 2-0, CZE-RSA 1-1, MEX-KOR 0-1, CZE-MEX 0-1, RSA-KOR 1-0
    states = group_a_states([(2, 0), (2, 0), (1, 1), (0, 1), (0, 1), (1, 0)])
    s = resolver.group_standings("A", states)
    mex = next(r for r in s["rows"] if r["fifa_code"] == "MEX")
    kor = next(r for r in s["rows"] if r["fifa_code"] == "KOR")
    assert (mex["points"], mex["gd"], mex["gf"]) == (kor["points"], kor["gd"], kor["gf"])
    assert s["rows"][0]["fifa_code"] == "KOR"  # h2h winner ranks first


def test_incomplete_group_is_provisional():
    states = group_a_states([(2, 0), (1, 1), (0, 0), (1, 0), (0, 3), (0, 2)])
    del states[max(states)]
    s = resolver.group_standings("A", states)
    assert not s["complete"]


def test_resolve_bracket_group_winner_flows_to_r32():
    states = group_a_states([(2, 0), (1, 1), (0, 0), (1, 0), (0, 3), (0, 2)])
    resolved = resolver.resolve_bracket(states)
    by_num = {m["match_number"]: m for m in resolved}
    # M79 home slot is 1A
    m79 = by_num[79]
    assert m79["home_slot"] == {"type": "group_rank", "group": "A", "rank": 1}
    assert m79["home"]["fifa_code"] == "MEX"
    assert m79["home"]["provisional"] is False
    # unresolved slots carry a readable label
    m104 = by_num[104]
    assert m104["home"]["fifa_code"] is None
    assert m104["home"]["label"] == "Winner M101"


def test_resolve_knockout_winner_and_pens():
    states = {
        90: finished(90, "MEX", "SUI", 1, 1, pens=(5, 4)),
    }
    resolved = {m["match_number"]: m for m in resolver.resolve_bracket(states)}
    # M90 winner feeds M97 (per bracket feeds_into)
    target = static_data.bracket_by_number()[90]["feeds_into"]
    side = "home" if resolved[target]["home_slot"].get("match_number") == 90 else "away"
    assert resolved[target][side]["fifa_code"] == "MEX"


def test_live_states_override_projection():
    """If ESPN names actual teams for a knockout match, that wins."""
    m73 = static_data.bracket_by_number()[73]
    states = {73: MatchState(
        match_number=73, status="upcoming",
        home=SideState(fifa_code="CAN"), away=SideState(fifa_code="QAT"),
        kickoff_utc=m73["kickoff_utc"], venue_id=m73["venue_id"], round="r32",
    )}
    resolved = {m["match_number"]: m for m in resolver.resolve_bracket(states)}
    assert resolved[73]["home"]["fifa_code"] == "CAN"
    assert resolved[73]["away"]["fifa_code"] == "QAT"


def test_thirds_assignment_unique_and_in_pool():
    thirds_by_group = {g: c for g, c in zip("ABCDEFGH", [
        "RSA", "QAT", "HAI", "PAR", "CIV", "TUN", "EGY", "CPV"])}
    slots = []
    for m in static_data.bracket():
        for slot in (m["home_slot"], m["away_slot"]):
            if isinstance(slot, dict) and slot["type"] == "third_place_pool":
                slots.append({"match_number": m["match_number"], "groups": slot["groups"]})
    assert len(slots) == 8
    assignment = resolver._assign_thirds(slots, thirds_by_group)
    assert assignment is not None
    assert len(set(assignment.values())) == 8
    code_to_group = {v: k for k, v in thirds_by_group.items()}
    by_num = {}
    for m in static_data.bracket():
        for slot in (m["home_slot"], m["away_slot"]):
            if isinstance(slot, dict) and slot["type"] == "third_place_pool":
                by_num[m["match_number"]] = slot["groups"]
    for num, code in assignment.items():
        assert code_to_group[code] in by_num[num]
