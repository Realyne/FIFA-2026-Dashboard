"""Public API for the SPA. Handlers serve from Redis + static data only —
they never call the upstream provider directly."""
from __future__ import annotations

import asyncio
import contextlib
import hashlib
import json
import logging
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from . import cache, resolver, static_data
from .config import settings
from .players_db import connect as players_connect
from .scheduler import Poller

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
log = logging.getLogger("wc2026.api")

SSE_KEEPALIVE = 25


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    cfg = settings()
    app.state.redis = cache.make_redis(cfg.redis_url)
    app.state.poller = None
    if cfg.poll_enabled:
        app.state.poller = Poller(app.state.redis)
        app.state.poll_task = asyncio.create_task(app.state.poller.run())
    yield
    if app.state.poller:
        app.state.poller.stop()
        with contextlib.suppress(Exception):
            await asyncio.wait_for(app.state.poll_task, timeout=5)
    await app.state.redis.aclose()


app = FastAPI(title="WC2026 Data Service", lifespan=lifespan)

cfg = settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=cfg.origins,
    allow_methods=["GET"],
    allow_headers=["*"],
)


def etag_response(request: Request, payload, max_age: int) -> Response:
    body = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
    tag = '"' + hashlib.md5(body.encode()).hexdigest()[:16] + '"'
    headers = {"ETag": tag, "Cache-Control": f"public, max-age={max_age}"}
    if request.headers.get("if-none-match") == tag:
        return Response(status_code=304, headers=headers)
    return Response(content=body, media_type="application/json", headers=headers)


async def _states(request: Request):
    return await cache.load_states(request.app.state.redis)


# ------------------------------------------------------------------ static --
@app.get("/api/wc/teams")
async def get_teams(request: Request):
    return etag_response(request, static_data.teams(), 3600)


@app.get("/api/wc/venues")
async def get_venues(request: Request):
    return etag_response(request, static_data.venues(), 3600)


# ----------------------------------------------------------------- bracket --
@app.get("/api/wc/bracket")
async def get_bracket(request: Request):
    r = request.app.state.redis
    resolved = await cache.get_json(r, "wc:bracket_resolved")
    if resolved is None:
        resolved = resolver.resolve_bracket(await _states(request))
        await cache.store_json(r, "wc:bracket_resolved", resolved, cache.TTL_BRACKET)
    return etag_response(request, resolved, 30)


@app.get("/api/wc/standings")
async def get_standings(request: Request):
    r = request.app.state.redis
    standings = await cache.get_json(r, "wc:standings")
    if standings is None:
        standings = resolver.all_standings(await _states(request))
        await cache.store_json(r, "wc:standings", standings, cache.TTL_BRACKET)
    return etag_response(request, standings, 30)


# ----------------------------------------------------------------- matches --
@app.get("/api/wc/matches")
async def get_matches(request: Request, date: str | None = None):
    """Scoreboard. date=YYYY-MM-DD (UTC day of kickoff); default: all matches."""
    states = await _states(request)
    out = []
    for m in static_data.bracket():
        if date and not m["kickoff_utc"].startswith(date):
            continue
        st = states.get(m["match_number"])
        if st is not None:
            out.append(st.model_dump())
        else:
            home = m["home_slot"] if isinstance(m["home_slot"], str) else None
            away = m["away_slot"] if isinstance(m["away_slot"], str) else None
            out.append({
                "match_number": m["match_number"], "espn_event_id": None,
                "status": "upcoming", "minute_display": None,
                "home": {"fifa_code": home, "score": None, "pen_score": None},
                "away": {"fifa_code": away, "score": None, "pen_score": None},
                "kickoff_utc": m["kickoff_utc"], "venue_id": m["venue_id"],
                "round": m["round"], "group": m["group"],
            })
    return etag_response(request, out, 20)


@app.get("/api/wc/matches/{match_number}")
async def get_match(request: Request, match_number: int):
    m = static_data.bracket_by_number().get(match_number)
    if m is None:
        raise HTTPException(404, "no such match")
    r = request.app.state.redis
    detail = await cache.get_json(r, f"wc:match:{match_number}")
    if detail is None:
        states = await _states(request)
        st = states.get(match_number)
        if st is not None:
            detail = {**st.model_dump(), "events": [], "lineups": {}, "stats": {}, "shootout": {}}
        else:
            home = m["home_slot"] if isinstance(m["home_slot"], str) else None
            away = m["away_slot"] if isinstance(m["away_slot"], str) else None
            detail = {
                "match_number": match_number, "espn_event_id": None,
                "status": "upcoming", "minute_display": None,
                "home": {"fifa_code": home, "score": None, "pen_score": None},
                "away": {"fifa_code": away, "score": None, "pen_score": None},
                "kickoff_utc": m["kickoff_utc"], "venue_id": m["venue_id"],
                "round": m["round"], "group": m["group"],
                "events": [], "lineups": {}, "stats": {}, "shootout": {},
            }
    return etag_response(request, detail, 30)


# --------------------------------------------------------------------- SSE --
@app.get("/api/wc/stream")
async def stream(request: Request):
    """SSE stream of JSON patches published on wc:updates.

    Event format (one JSON object per `data:` line):
      {"type":"match","match_number":N,"changed":{...},"state":{...MatchState}}
      {"type":"bracket"}   -> client should refetch /api/wc/bracket
    A `: keepalive` comment frame is sent every 25s.
    """
    r = request.app.state.redis

    async def gen():
        pubsub = r.pubsub()
        await pubsub.subscribe(cache.CHANNEL)
        yield ": connected\n\n"
        try:
            while True:
                if await request.is_disconnected():
                    break
                msg = await pubsub.get_message(ignore_subscribe_messages=True,
                                               timeout=SSE_KEEPALIVE)
                if msg is None:
                    yield ": keepalive\n\n"
                elif msg.get("type") == "message":
                    yield f"data: {msg['data']}\n\n"
        finally:
            await pubsub.unsubscribe(cache.CHANNEL)
            await pubsub.aclose()

    return StreamingResponse(gen(), media_type="text/event-stream", headers={
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no",
    })


# ----------------------------------------------------------------- players --
PLAYER_COLS = ("player_id", "name", "fifa_code", "shirt_number", "dob",
               "position", "club", "club_country", "caps", "intl_goals",
               "past_world_cups", "fifa_profile_url", "espn_id", "wikidata_qid")


def _player_row(row) -> dict:
    d = {k: row[k] for k in PLAYER_COLS}
    d["past_world_cups"] = json.loads(d["past_world_cups"]) if d["past_world_cups"] else []
    return d


def _players_query(sql: str, params: tuple) -> list[dict]:
    conn = players_connect(settings().db_path)
    try:
        return [_player_row(r) for r in conn.execute(sql, params)]
    finally:
        conn.close()


@app.get("/api/wc/players")
async def get_players(request: Request, team: str | None = None):
    r = request.app.state.redis
    key = f"wc:players:{(team or 'all').upper()}"
    rows = await cache.get_json(r, key)
    if rows is None:
        if team:
            rows = _players_query(
                "SELECT * FROM players WHERE fifa_code=? ORDER BY shirt_number",
                (team.upper(),))
        else:
            rows = _players_query(
                "SELECT * FROM players ORDER BY fifa_code, shirt_number", ())
        await cache.store_json(r, key, rows, 3600)
    return etag_response(request, rows, 3600)


@app.get("/api/wc/players/{player_id}")
async def get_player(request: Request, player_id: str):
    r = request.app.state.redis
    key = f"wc:player:{player_id}"
    row = await cache.get_json(r, key)
    if row is None:
        rows = _players_query("SELECT * FROM players WHERE player_id=?", (player_id,))
        if not rows:
            raise HTTPException(404, "no such player")
        row = rows[0]
        await cache.store_json(r, key, row, 3600)
    return etag_response(request, row, 3600)


# ------------------------------------------------------------------ health --
@app.get("/healthz")
async def healthz(request: Request):
    r = request.app.state.redis
    redis_ok = True
    health = {}
    try:
        health = await cache.get_health(r)
    except Exception:  # noqa: BLE001
        redis_ok = False
    return {
        "ok": redis_ok and not health.get("degraded", False),
        "provider": health.get("provider", settings().data_provider),
        "degraded": health.get("degraded", False),
        "last_poll_ok": health.get("last_poll_ok"),
        "redis": redis_ok,
        "time": datetime.now(timezone.utc).isoformat(),
    }
