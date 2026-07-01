"""ESPN parser tests against captured + synthetic fixtures."""
import json
from pathlib import Path

import httpx
import pytest

from wc2026.models import MatchState, SideState
from wc2026.providers.espn import ESPNProvider, parse_minute, map_status
from wc2026 import resolver

FIXTURES = Path(__file__).resolve().parent / "fixtures"


@pytest.fixture
def provider():
    return ESPNProvider(client=httpx.AsyncClient())


def load(name):
    return json.loads((FIXTURES / name).read_text())


# ----------------------------------------------------------- scoreboard ----
def test_parse_real_wc_scoreboard(provider):
    states = provider.parse_scoreboard(load("scoreboard_fifa_world_20260611.json"))
    assert len(states) == 2
    by_teams = {frozenset((s.home.fifa_code, s.away.fifa_code)): s for s in states}
    opener = by_teams[frozenset(("MEX", "RSA"))]
    # fixture captured after FT of the real opener (MEX 2-0 RSA)
    assert opener.status == "finished"
    assert (opener.home.score, opener.away.score) == (2, 0)
    assert opener.espn_event_id == "760415"
    assert opener.kickoff_utc == "2026-06-11T19:00:00Z"


def test_map_real_events_to_match_numbers(provider):
    states = provider.parse_scoreboard(load("scoreboard_fifa_world_20260611.json"))
    nums = sorted(resolver.map_event_to_match(s) for s in states)
    assert nums == [1, 2]  # MEX-RSA opener, KOR-CZE


def test_parse_shootout_and_stoppage(provider):
    states = provider.parse_scoreboard(load("scoreboard_synthetic_shootout.json"))
    pens = next(s for s in states if s.home.fifa_code == "ARG")
    assert pens.status == "finished"
    assert pens.home.score == 3 and pens.away.score == 3
    assert pens.home.pen_score == 4 and pens.away.pen_score == 2
    live = next(s for s in states if s.home.fifa_code == "ESP")
    assert live.status == "live"
    assert live.minute_display == "90+3"  # stoppage preserved
    assert live.home.pen_score is None  # no phantom 0-0 shootout


def test_parse_garbage_scoreboard_is_safe(provider, tmp_path, monkeypatch):
    monkeypatch.setenv("DEBUG_DIR", str(tmp_path))
    assert provider.parse_scoreboard({"events": "nope"}) == []
    assert provider.parse_scoreboard({}) == []
    assert provider.parse_scoreboard({"events": [{"id": "1"}]}) == []


# -------------------------------------------------------------- summary ----
def base_state(**kw):
    defaults = dict(match_number=50, espn_event_id="401856622", status="live",
                    kickoff_utc="2026-06-06T18:00:00Z", venue_id="metlife",
                    round="group", group="A",
                    home=SideState(fifa_code="BEL"), away=SideState(fifa_code="TUN"))
    defaults.update(kw)
    return MatchState(**defaults)


def test_parse_real_summary(provider):
    detail = provider.parse_summary(load("summary_fifa_friendly_401856622.json"), base_state())
    assert detail.status == "finished"
    assert detail.home.score == 5 and detail.away.score == 0

    goals = [e for e in detail.events if e.type in ("goal", "pen_goal", "own_goal")]
    assert len(goals) == 5
    assert all(e.fifa_code == "BEL" for e in goals)
    trossard = goals[0]
    assert trossard.player_name == "Leandro Trossard"
    assert trossard.assist_name == "Jérémy Doku"
    assert trossard.minute == "28"

    cards = [e for e in detail.events if e.type in ("yellow", "red")]
    assert any(e.minute == "90+3" for e in cards)  # stoppage preserved
    assert any(e.type == "red" for e in cards)

    subs = [e for e in detail.events if e.type == "sub"]
    assert subs, "expected substitutions"
    assert all(e.sub_off_player for e in subs)

    home = detail.lineups["home"]
    assert home.formation == "4-2-3-1"
    assert len(home.starters) == 11
    assert len(home.bench) > 0
    gk = home.starters[0]
    assert gk.name == "Thibaut Courtois" and gk.shirt_number == 1

    hs = detail.stats["home"]
    assert hs.possession_pct == 65.7
    assert hs.shots == 27 and hs.shots_on_target == 12
    assert hs.corners == 14 and hs.fouls == 9 and hs.offsides == 2


def test_parse_summary_missing_lineups(provider):
    data = load("summary_fifa_friendly_401856622.json")
    data["rosters"] = [{"homeAway": "home", "team": {"id": "459"}, "roster": []}]
    del data["boxscore"]
    detail = provider.parse_summary(data, base_state())
    assert detail.lineups == {}  # empty roster -> not announced yet
    assert detail.stats == {}
    assert detail.events  # events still parse


def test_parse_summary_total_garbage(provider):
    detail = provider.parse_summary({"weird": True}, base_state())
    assert detail.match_number == 50
    assert detail.events == [] and detail.lineups == {} and detail.stats == {}
    assert detail.shootout == {}


def test_no_shootout_on_regular_match(provider):
    detail = provider.parse_summary(load("summary_fifa_friendly_401856622.json"), base_state())
    assert detail.shootout == {}  # no phantom shootout for a normal result


def test_parse_shootout_sequence(provider):
    """Per-kick shootout detail: who took each kick and whether it scored."""
    home = base_state(home=SideState(fifa_code="ARG"), away=SideState(fifa_code="FRA"))
    detail = provider.parse_summary(load("summary_synthetic_shootout.json"), home)
    assert set(detail.shootout) == {"home", "away"}
    arg = detail.shootout["home"]  # team id 202 == home in the fixture header
    fra = detail.shootout["away"]  # team id 478 == away
    # kept in kick order
    assert [k.shot_number for k in arg] == [1, 2, 3, 4]
    assert [k.shot_number for k in fra] == [1, 2, 3, 4]
    # scored/missed captured exactly
    assert [k.scored for k in arg] == [True, True, True, True]
    assert [k.scored for k in fra] == [True, False, False, True]
    assert sum(k.scored for k in arg) == 4 and sum(k.scored for k in fra) == 2
    # takers named
    assert fra[0].player_name == "Kylian Mbappé" and fra[0].player_espn_id == "231388"
    assert arg[3].player_name == "Gonzalo Montiel"


# ---------------------------------------------------------------- units ----
@pytest.mark.parametrize("display,clock,want", [
    ("90'+3'", 5580.0, "90+3"),
    ("67'", 4020.0, "67"),
    ("", 1349.0, "23"),
    (None, None, None),
    ("HT", None, None),
])
def test_parse_minute(display, clock, want):
    assert parse_minute(display, clock) == want


@pytest.mark.parametrize("name,state,want", [
    ("STATUS_SCHEDULED", "pre", "upcoming"),
    ("STATUS_FIRST_HALF", "in", "live"),
    ("STATUS_HALFTIME", "in", "ht"),
    ("STATUS_SHOOTOUT", "in", "pens"),
    ("STATUS_FULL_TIME", "post", "finished"),
    ("STATUS_FINAL_PEN", "post", "finished"),
    ("STATUS_SOMETHING_NEW", "in", "live"),  # state fallback
])
def test_map_status(name, state, want):
    assert map_status({"type": {"name": name, "state": state}}) == want
