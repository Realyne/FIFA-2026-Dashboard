"""Static data layer validation (Phase 1)."""
import json
import re
from datetime import datetime, timezone
from pathlib import Path

import pytest

STATIC = Path(__file__).resolve().parent.parent / "data" / "static"


@pytest.fixture(scope="module")
def bracket():
    return json.loads((STATIC / "bracket.json").read_text())


@pytest.fixture(scope="module")
def teams():
    return json.loads((STATIC / "teams.json").read_text())


@pytest.fixture(scope="module")
def venues():
    return json.loads((STATIC / "venues.json").read_text())


def test_match_numbers_complete(bracket):
    assert [m["match_number"] for m in bracket] == list(range(1, 105))


def test_round_counts(bracket):
    counts = {}
    for m in bracket:
        counts[m["round"]] = counts.get(m["round"], 0) + 1
    assert counts == {
        "group": 72, "r32": 16, "r16": 8, "qf": 4,
        "sf": 2, "third_place": 1, "final": 1,
    }


def test_group_matches_use_fifa_codes(bracket, teams):
    codes = {t["fifa_code"] for t in teams}
    for m in bracket:
        if m["round"] == "group":
            assert m["home_slot"] in codes, m
            assert m["away_slot"] in codes, m
            assert m["group"] in "ABCDEFGHIJKL"


def test_r32_fed_by_group_slots(bracket):
    for m in bracket:
        if m["round"] == "r32":
            for slot in (m["home_slot"], m["away_slot"]):
                assert slot["type"] in ("group_rank", "third_place_pool"), m


def test_later_knockouts_fed_by_two_matches(bracket):
    by_num = {m["match_number"]: m for m in bracket}
    for m in bracket:
        if m["round"] in ("r16", "qf", "sf", "final"):
            feeders = [
                f for f in bracket
                if f.get("feeds_into") == m["match_number"]
            ]
            assert len(feeders) == 2, f"M{m['match_number']} has {len(feeders)} feeders"
            for slot in (m["home_slot"], m["away_slot"]):
                assert slot["type"] == "match_winner"
                assert by_num[slot["match_number"]]["feeds_into"] == m["match_number"]


def test_binary_tree_73_to_104(bracket):
    """Winner graph from the R32 to the final is a single-elimination binary tree."""
    ko = [m for m in bracket if m["match_number"] >= 73 and m["round"] != "third_place"]
    final = [m for m in ko if m["round"] == "final"]
    assert len(final) == 1 and final[0]["feeds_into"] is None
    # every non-final node has exactly one parent, reachable from the final
    children = {}
    for m in ko:
        if m["round"] != "final":
            assert m["feeds_into"] is not None
            children.setdefault(m["feeds_into"], []).append(m["match_number"])
    seen = set()
    stack = [final[0]["match_number"]]
    while stack:
        n = stack.pop()
        seen.add(n)
        kids = children.get(n, [])
        assert len(kids) in (0, 2), f"M{n} has {len(kids)} children"
        stack.extend(kids)
    assert seen == {m["match_number"] for m in ko}, "tree does not span all knockout matches"


def test_semifinal_losers_feed_third_place(bracket):
    third = next(m for m in bracket if m["round"] == "third_place")
    sfs = [m for m in bracket if m["round"] == "sf"]
    assert len(sfs) == 2
    for sf in sfs:
        assert sf["feeds_into_loser"] == third["match_number"]
    loser_nums = {s["match_number"] for s in
                  (third["home_slot"], third["away_slot"])}
    assert loser_nums == {s["match_number"] for s in sfs}


def test_48_unique_fifa_codes(teams):
    codes = [t["fifa_code"] for t in teams]
    assert len(codes) == 48
    assert len(set(codes)) == 48
    for c in codes:
        assert re.fullmatch(r"[A-Z]{3}", c), c


def test_teams_have_flags_and_groups(teams):
    for t in teams:
        assert t["flag_url"].startswith("https://flagcdn.com/"), t
        assert t["group"] in "ABCDEFGHIJKL"
    # 4 teams per group
    per_group = {}
    for t in teams:
        per_group[t["group"]] = per_group.get(t["group"], 0) + 1
    assert all(v == 4 for v in per_group.values())


def test_every_match_venue_exists(bracket, venues):
    ids = {v["id"] for v in venues}
    assert len(venues) == 16
    for m in bracket:
        assert m["venue_id"] in ids, m


def test_kickoffs_parse_and_in_window(bracket):
    lo = datetime(2026, 6, 11, tzinfo=timezone.utc)
    hi = datetime(2026, 7, 20, tzinfo=timezone.utc)
    for m in bracket:
        dt = datetime.strptime(m["kickoff_utc"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        assert lo <= dt < hi, m


def test_kickoffs_monotonic_for_group_numbers(bracket):
    """Group match numbering follows the chronological schedule."""
    groups = [m for m in bracket if m["round"] == "group"]
    ks = [m["kickoff_utc"] for m in groups]
    assert ks == sorted(ks)


def test_venue_timezones_are_iana(venues):
    from zoneinfo import ZoneInfo
    for v in venues:
        ZoneInfo(v["tz"])  # raises if invalid
