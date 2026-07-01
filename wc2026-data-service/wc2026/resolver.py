"""Bracket resolution: turn slot descriptors into FIFA codes as results come in.

Inputs are normalized MatchStates (keyed by match_number) + the static bracket.
Pure functions — no I/O — so the whole module is unit-testable.

Tiebreakers implemented (FIFA Art. 13 cascade, pragmatically):
  group rank: points, goal difference, goals scored, then head-to-head
  points/GD/GF among the tied teams, then fifa_code alphabetical as the final
  deterministic fallback (fair-play points are not derivable from scores; a
  lots-drawn outcome would be corrected by the ESPN feed once pairings are
  official, which always overrides projections).
Third-place ranking across groups: points, GD, GF, fifa_code.
Slot assignment for third-place pools is a deterministic backtracking match
over each R32 slot's allowed group pool.
"""
from __future__ import annotations

from .models import MatchState
from . import static_data


def _h2h_rank(codes: list[str], matches: list[MatchState]) -> dict[str, tuple]:
    """Head-to-head (points, gd, gf) among `codes` over finished `matches`."""
    table = {c: [0, 0, 0] for c in codes}
    for m in matches:
        h, a = m.home.fifa_code, m.away.fifa_code
        if m.status != "finished" or h not in table or a not in table:
            continue
        hs, as_ = m.home.score or 0, m.away.score or 0
        table[h][1] += hs - as_; table[h][2] += hs
        table[a][1] += as_ - hs; table[a][2] += as_
        if hs > as_:
            table[h][0] += 3
        elif as_ > hs:
            table[a][0] += 3
        else:
            table[h][0] += 1; table[a][0] += 1
    return {c: tuple(v) for c, v in table.items()}


def group_standings(group: str, states: dict[int, MatchState]) -> dict:
    """Standings for one group. Returns {complete, rows:[{fifa_code, played,
    won, drawn, lost, gf, ga, gd, points}]} ranked."""
    static_matches = static_data.group_matches()[group]
    finished: list[MatchState] = []
    rows: dict[str, dict] = {}
    for sm in static_matches:
        for code in (sm["home_slot"], sm["away_slot"]):
            rows.setdefault(code, {
                "fifa_code": code, "played": 0, "won": 0, "drawn": 0,
                "lost": 0, "gf": 0, "ga": 0, "gd": 0, "points": 0,
            })
        st = states.get(sm["match_number"])
        if st is None or st.status != "finished":
            continue
        if st.home.score is None or st.away.score is None:
            continue
        finished.append(st)
        h, a = st.home.fifa_code, st.away.fifa_code
        hs, as_ = st.home.score, st.away.score
        if h not in rows or a not in rows:
            continue  # defensive: feed disagrees with static draw
        for code, mine, theirs in ((h, hs, as_), (a, as_, hs)):
            r = rows[code]
            r["played"] += 1; r["gf"] += mine; r["ga"] += theirs
            r["gd"] = r["gf"] - r["ga"]
            if mine > theirs:
                r["won"] += 1; r["points"] += 3
            elif mine < theirs:
                r["lost"] += 1
            else:
                r["drawn"] += 1; r["points"] += 1

    ordered = sorted(rows.values(), key=lambda r: (-r["points"], -r["gd"], -r["gf"], r["fifa_code"]))
    # head-to-head refinement among exact ties on (points, gd, gf)
    final: list[dict] = []
    i = 0
    while i < len(ordered):
        j = i + 1
        key = (ordered[i]["points"], ordered[i]["gd"], ordered[i]["gf"])
        while j < len(ordered) and (ordered[j]["points"], ordered[j]["gd"], ordered[j]["gf"]) == key:
            j += 1
        tied = ordered[i:j]
        if len(tied) > 1:
            h2h = _h2h_rank([r["fifa_code"] for r in tied], finished)
            tied.sort(key=lambda r: (
                -h2h[r["fifa_code"]][0], -h2h[r["fifa_code"]][1],
                -h2h[r["fifa_code"]][2], r["fifa_code"],
            ))
        final.extend(tied)
        i = j
    complete = len(finished) == len(static_matches)
    return {"group": group, "complete": complete, "rows": final}


def all_standings(states: dict[int, MatchState]) -> dict[str, dict]:
    return {grp: group_standings(grp, states) for grp in sorted(static_data.group_matches())}


def qualified_thirds(standings: dict[str, dict]) -> list[str] | None:
    """The 8 best third-placed teams; None until all groups complete."""
    if not all(s["complete"] for s in standings.values()):
        return None
    thirds = [s["rows"][2] for s in standings.values()]
    thirds.sort(key=lambda r: (-r["points"], -r["gd"], -r["gf"], r["fifa_code"]))
    return [r["fifa_code"] for r in thirds[:8]]


def _assign_thirds(
    slots: list[dict],
    thirds_by_group: dict[str, str],
    pinned: dict[int, str] | None = None,
) -> dict[int, str] | None:
    """Backtracking assignment: R32 slot -> third-placed team fifa_code.
    slots: [{match_number, groups:[...]}]; deterministic (sorted choices).

    pinned: {match_number: fifa_code} for slots the live feed has already
    named. The feed is authoritative, so those slots are fixed and consume
    their group up front — otherwise the backtracker could hand the same
    third-placed team to a second, still-projected match (a team appearing in
    two R32 slots at once)."""
    pinned = pinned or {}
    group_of = {code: grp for grp, code in thirds_by_group.items()}

    assignment: dict[int, str] = {}
    used: set[str] = set()
    remaining: list[dict] = []
    for slot in slots:
        code = pinned.get(slot["match_number"])
        grp = group_of.get(code) if code else None
        if grp and grp not in used:
            assignment[slot["match_number"]] = code
            used.add(grp)
        else:
            remaining.append(slot)

    remaining.sort(key=lambda s: len([g_ for g_ in s["groups"] if g_ in thirds_by_group and g_ not in used]))

    def backtrack(i: int) -> bool:
        if i == len(remaining):
            return True
        slot = remaining[i]
        for grp in sorted(slot["groups"]):
            code = thirds_by_group.get(grp)
            if code and grp not in used:
                used.add(grp)
                assignment[slot["match_number"]] = code
                if backtrack(i + 1):
                    return True
                used.discard(grp)
                assignment.pop(slot["match_number"], None)
        return False

    return assignment if backtrack(0) else None


def winner_loser(state: MatchState | None) -> tuple[str | None, str | None]:
    if state is None or state.status != "finished":
        return None, None
    h, a = state.home, state.away
    if h.score is None or a.score is None or h.fifa_code is None or a.fifa_code is None:
        return None, None
    if h.score != a.score:
        return (h.fifa_code, a.fifa_code) if h.score > a.score else (a.fifa_code, h.fifa_code)
    if h.pen_score is not None and a.pen_score is not None and h.pen_score != a.pen_score:
        return (h.fifa_code, a.fifa_code) if h.pen_score > a.pen_score else (a.fifa_code, h.fifa_code)
    return None, None


def slot_label(slot) -> str:
    """Human-readable label for an unresolved slot, e.g. 'Winner M74'."""
    if isinstance(slot, str):
        return slot
    t = slot["type"]
    if t == "group_rank":
        return f"{slot['rank']}{'st' if slot['rank']==1 else 'nd'} Group {slot['group']}"
    if t == "third_place_pool":
        return "3rd " + "/".join(slot["groups"])
    if t == "match_winner":
        return f"Winner M{slot['match_number']}"
    if t == "match_loser":
        return f"Loser M{slot['match_number']}"
    return "TBD"


def resolve_bracket(states: dict[int, MatchState]) -> list[dict]:
    """bracket.json + live resolution. Each match gains home/away dicts:
    {fifa_code|null, label, provisional} plus score/status from states.
    Resolution from live MatchStates (ESPN naming real teams) always wins
    over projections from standings."""
    standings = all_standings(states)
    thirds = qualified_thirds(standings)
    thirds_by_group: dict[str, str] = {}
    if thirds is not None:
        for grp, s in standings.items():
            code = s["rows"][2]["fifa_code"]
            if code in thirds:
                thirds_by_group[grp] = code

    bracket = static_data.bracket()
    third_slots = []
    for m in bracket:
        for side in ("home", "away"):
            slot = m[side + "_slot"]
            if isinstance(slot, dict) and slot["type"] == "third_place_pool":
                third_slots.append({"match_number": m["match_number"], "side": side, "groups": slot["groups"]})

    # The live feed is authoritative: pin any third-place slot it has already
    # named so the projected assignment can't reuse that team elsewhere.
    group_of_third = {code: grp for grp, code in thirds_by_group.items()}
    pinned: dict[int, str] = {}
    for ts in third_slots:
        st = states.get(ts["match_number"])
        if st is None:
            continue
        code = getattr(st, ts["side"]).fifa_code
        if code and code in group_of_third:
            pinned[ts["match_number"]] = code

    thirds_assignment = _assign_thirds(third_slots, thirds_by_group, pinned) if thirds_by_group else None

    def resolve_slot(match_number: int, slot, side: str) -> dict:
        # 1. live feed already names the team
        st = states.get(match_number)
        if st is not None:
            code = getattr(st, side).fifa_code
            if code:
                return {"fifa_code": code, "label": None, "provisional": False}
        # 2. static group fixture
        if isinstance(slot, str):
            return {"fifa_code": slot, "label": None, "provisional": False}
        t = slot["type"]
        if t == "group_rank":
            s = standings.get(slot["group"])
            if s and s["rows"]:
                row = s["rows"][slot["rank"] - 1]
                if row["played"] > 0:
                    return {
                        "fifa_code": row["fifa_code"],
                        "label": slot_label(slot),
                        "provisional": not s["complete"],
                    }
        elif t == "third_place_pool":
            if thirds_assignment and match_number in thirds_assignment:
                return {"fifa_code": thirds_assignment[match_number],
                        "label": slot_label(slot), "provisional": False}
        elif t == "match_winner":
            w, _ = winner_loser(states.get(slot["match_number"]))
            if w:
                return {"fifa_code": w, "label": None, "provisional": False}
        elif t == "match_loser":
            _, l = winner_loser(states.get(slot["match_number"]))
            if l:
                return {"fifa_code": l, "label": None, "provisional": False}
        return {"fifa_code": None, "label": slot_label(slot), "provisional": False}

    out = []
    for m in bracket:
        st = states.get(m["match_number"])
        entry = dict(m)
        entry["home"] = resolve_slot(m["match_number"], m["home_slot"], "home")
        entry["away"] = resolve_slot(m["match_number"], m["away_slot"], "away")
        entry["status"] = st.status if st else "upcoming"
        entry["minute_display"] = st.minute_display if st else None
        entry["home"]["score"] = st.home.score if st else None
        entry["home"]["pen_score"] = st.home.pen_score if st else None
        entry["away"]["score"] = st.away.score if st else None
        entry["away"]["pen_score"] = st.away.pen_score if st else None
        out.append(entry)
    return out


# ---------------------------------------------------------------- mapping --
def map_event_to_match(state: MatchState, resolved: list[dict] | None = None) -> int | None:
    """Map a provider event (teams + kickoff) to a bracket match_number."""
    h, a = state.home.fifa_code, state.away.fifa_code
    candidates = []
    for m in (resolved if resolved is not None else resolve_bracket({})):
        mh = m["home"]["fifa_code"] if isinstance(m.get("home"), dict) else None
        ma = m["away"]["fifa_code"] if isinstance(m.get("away"), dict) else None
        if h and a and mh and ma:
            if {h, a} == {mh, ma} and m["kickoff_utc"][:10] == state.kickoff_utc[:10]:
                return m["match_number"]
        candidates.append(m)
    # teams unknown on one side (early knockout scheduling): exact kickoff match
    exact = [m for m in candidates if m["kickoff_utc"] == state.kickoff_utc]
    if len(exact) == 1:
        return exact[0]["match_number"]
    if h and a:
        # same teams any kickoff within the same day window (TZ grouping quirks)
        same_teams = [
            m for m in candidates
            if isinstance(m.get("home"), dict)
            and {m["home"].get("fifa_code"), m["away"].get("fifa_code")} == {h, a}
        ]
        if len(same_teams) == 1:
            return same_teams[0]["match_number"]
    return None
