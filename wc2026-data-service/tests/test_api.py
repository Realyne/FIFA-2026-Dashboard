"""API endpoint tests with fakeredis (no poller, no network)."""
import json

import fakeredis.aioredis
import httpx
import pytest
import pytest_asyncio

from wc2026 import cache
from wc2026.main import app
from wc2026.models import MatchState, SideState
from wc2026 import static_data


@pytest_asyncio.fixture
async def client():
    app.state.redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    await app.state.redis.aclose()


async def seed_live_m1(r):
    m1 = static_data.bracket_by_number()[1]
    st = MatchState(
        match_number=1, espn_event_id="760415", status="live", minute_display="33",
        home=SideState(fifa_code="MEX", score=1), away=SideState(fifa_code="RSA", score=0),
        kickoff_utc=m1["kickoff_utc"], venue_id=m1["venue_id"], round="group", group="A",
    )
    await cache.store_state(r, st, None)
    return st


async def test_teams_and_venues(client):
    r = await client.get("/api/wc/teams")
    assert r.status_code == 200
    teams = r.json()
    assert len(teams) == 48
    assert r.headers["etag"]
    # conditional request
    r2 = await client.get("/api/wc/teams", headers={"If-None-Match": r.headers["etag"]})
    assert r2.status_code == 304

    v = await client.get("/api/wc/venues")
    assert len(v.json()) == 16


async def test_matches_by_date_static_fallback(client):
    r = await client.get("/api/wc/matches", params={"date": "2026-06-11"})
    assert r.status_code == 200
    day = r.json()
    # only the opener falls on June 11 in UTC (the other two spill past 00Z)
    assert {m["match_number"] for m in day} == {1}
    assert all(m["status"] == "upcoming" for m in day)
    d12 = (await client.get("/api/wc/matches", params={"date": "2026-06-12"})).json()
    assert len(d12) >= 2


async def test_matches_reflect_redis_state(client):
    await seed_live_m1(app.state.redis)
    r = await client.get("/api/wc/matches", params={"date": "2026-06-11"})
    m1 = next(m for m in r.json() if m["match_number"] == 1)
    assert m1["status"] == "live"
    assert m1["home"]["score"] == 1
    assert m1["minute_display"] == "33"


async def test_match_detail_fallbacks(client):
    r = await client.get("/api/wc/matches/1")
    assert r.status_code == 200
    d = r.json()
    assert d["home"]["fifa_code"] == "MEX"
    assert d["events"] == [] and d["lineups"] == {}

    r404 = await client.get("/api/wc/matches/999")
    assert r404.status_code == 404


async def test_match_detail_from_redis(client):
    await seed_live_m1(app.state.redis)
    detail = {"match_number": 1, "status": "live", "events": [
        {"minute": "12", "type": "goal", "player_name": "Raúl Jiménez",
         "fifa_code": "MEX", "player_espn_id": "1", "sub_off_player": None,
         "assist_name": None}]}
    await cache.store_json(app.state.redis, "wc:match:1", detail, 90)
    r = await client.get("/api/wc/matches/1")
    assert r.json()["events"][0]["player_name"] == "Raúl Jiménez"


async def test_bracket_resolves_from_states(client):
    await seed_live_m1(app.state.redis)
    r = await client.get("/api/wc/bracket")
    assert r.status_code == 200
    bracket = r.json()
    assert len(bracket) == 104
    m1 = bracket[0]
    assert m1["status"] == "live"
    assert m1["home"]["fifa_code"] == "MEX"
    m104 = bracket[-1]
    assert m104["home"]["label"] == "Winner M101"


async def test_standings_endpoint(client):
    r = await client.get("/api/wc/standings")
    assert r.status_code == 200
    s = r.json()
    assert set(s.keys()) == set("ABCDEFGHIJKL")
    assert len(s["A"]["rows"]) == 4


async def test_healthz(client):
    r = await client.get("/healthz")
    assert r.status_code == 200
    body = r.json()
    assert body["redis"] is True


async def test_sse_stream_emits_patches(client):
    """Drive the SSE generator directly (ASGITransport can't stream an
    infinite response); publish a patch and expect it framed on the wire."""
    import asyncio

    from wc2026.main import stream

    class FakeRequest:
        def __init__(self):
            self.app = app

        async def is_disconnected(self):
            return False

    resp = await stream(FakeRequest())
    agen = resp.body_iterator
    first = await asyncio.wait_for(agen.__anext__(), timeout=5)
    assert first.startswith(": connected")

    await seed_live_m1(app.state.redis)
    frame = None
    for _ in range(5):
        frame = await asyncio.wait_for(agen.__anext__(), timeout=5)
        if frame.startswith("data:"):
            break
    assert frame and frame.startswith("data:")
    patch = json.loads(frame[5:].strip())
    assert patch["type"] == "match"
    assert patch["match_number"] == 1
    assert patch["state"]["home"]["score"] == 1
    await agen.aclose()
