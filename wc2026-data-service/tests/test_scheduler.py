"""Live-window logic (pure functions of `now`, no clock freezing needed)."""
from datetime import datetime, timezone

from wc2026 import static_data
from wc2026.models import MatchState, SideState
from wc2026.scheduler import live_windows, scoreboard_dates, espn_date, parse_utc


def utc(*args):
    return datetime(*args, tzinfo=timezone.utc)


def test_window_opens_15min_before_kickoff():
    # M1 kicks off 2026-06-11T19:00:00Z
    assert not live_windows(utc(2026, 6, 11, 18, 44), {})
    assert live_windows(utc(2026, 6, 11, 18, 46), {})
    assert live_windows(utc(2026, 6, 11, 20, 30), {})


def test_window_hard_cap():
    inside = live_windows(utc(2026, 6, 11, 22, 59), {})
    assert any(m["match_number"] == 1 for m in inside)
    after = live_windows(utc(2026, 6, 11, 23, 1), {})
    assert not any(m["match_number"] == 1 for m in after)


def test_window_closes_when_finished():
    m1 = static_data.bracket_by_number()[1]
    states = {1: MatchState(
        match_number=1, status="finished",
        home=SideState(fifa_code="MEX", score=2), away=SideState(fifa_code="RSA", score=0),
        kickoff_utc=m1["kickoff_utc"], venue_id=m1["venue_id"], round="group", group="A",
    )}
    open_now = live_windows(utc(2026, 6, 11, 20, 30), states)
    assert not any(m["match_number"] == 1 for m in open_now)


def test_no_windows_outside_tournament():
    assert not live_windows(utc(2026, 6, 1, 12, 0), {})
    assert not live_windows(utc(2026, 8, 1, 12, 0), {})


def test_espn_date_uses_eastern_grouping():
    # KOR-CZE kicks off 2026-06-12T02:00Z = June 11 evening Eastern
    assert espn_date(parse_utc("2026-06-12T02:00:00Z")) == "20260611"


def test_scoreboard_dates_cover_late_kickoffs():
    dates = scoreboard_dates(utc(2026, 6, 11, 21, 0))
    assert "20260611" in dates
