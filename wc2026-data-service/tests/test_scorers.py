"""Tournament top-scorer aggregation."""
import asyncio
import json

from wc2026.scorers import tournament_scorers


def ev(t, name, code, espn=None):
    return {"type": t, "player_name": name, "fifa_code": code, "player_espn_id": espn}


def detail(events):
    return {"events": events}


def test_empty_and_none_details():
    assert tournament_scorers([]) == []
    assert tournament_scorers([None, {}, {"events": []}]) == []


def test_counts_goals_and_penalties_excludes_own_goals():
    details = [
        detail([ev("goal", "Vinícius Júnior", "BRA", "252107"),
                ev("pen_goal", "Vinícius Júnior", "BRA", "252107")]),
        detail([ev("own_goal", "Vinícius Júnior", "BRA", "252107")]),  # not credited
        detail([ev("goal", "Harry Kane", "ENG", "1")]),
    ]
    s = tournament_scorers(details)
    vini = next(x for x in s if x["player_name"] == "Vinícius Júnior")
    assert vini["goals"] == 2 and vini["penalties"] == 1
    kane = next(x for x in s if x["player_name"] == "Harry Kane")
    assert kane["goals"] == 1 and kane["penalties"] == 0


def test_same_player_across_matches_merges_by_espn_id():
    details = [detail([ev("goal", "Kane", "ENG", "1")]),
               detail([ev("goal", "Kane", "ENG", "1")])]
    s = tournament_scorers(details)
    assert len(s) == 1 and s[0]["goals"] == 2


class _StubRedis:
    """Records how the aggregator reads Redis (guards against per-key fan-out
    that exhausts the connection pool -> 500)."""
    def __init__(self, data):
        self.data = data
        self.mget_calls = 0
        self.get_calls = 0

    async def mget(self, keys):
        self.mget_calls += 1
        return [self.data.get(k) for k in keys]

    async def get(self, key):
        self.get_calls += 1
        return self.data.get(key)


def test_aggregate_reads_with_a_single_mget():
    from wc2026 import main
    r = _StubRedis({"wc:match:6": json.dumps(
        {"events": [{"type": "goal", "player_name": "Kane", "fifa_code": "ENG", "player_espn_id": "1"}]})})
    res = asyncio.run(main._aggregate_scorers(r))
    assert r.mget_calls == 1 and r.get_calls == 0  # batched, not 104 concurrent GETs
    assert res and res[0]["player_name"] == "Kane" and res[0]["goals"] == 1


def test_sort_open_play_breaks_goal_ties():
    # both on 3 goals; A scored all from open play, B has 2 penalties -> A first
    details = [
        detail([ev("goal", "A", "X"), ev("goal", "A", "X"), ev("goal", "A", "X")]),
        detail([ev("pen_goal", "B", "Y"), ev("pen_goal", "B", "Y"), ev("goal", "B", "Y")]),
    ]
    s = tournament_scorers(details)
    assert [x["player_name"] for x in s] == ["A", "B"]
    assert s[0]["goals"] == 3 and s[1]["penalties"] == 2
