"""Redis helpers: state store, response caches, pub/sub diffs.

Keys:
  wc:states              hash  match_number -> MatchState JSON (no TTL)
  wc:match:{n}           str   MatchDetail JSON (TTL 90s live; finished matches
                               are kept forever so past timelines stay visible)
  wc:scoreboard:{date}   str   scoreboard response JSON (TTL 60s)
  wc:bracket_resolved    str   resolved bracket JSON (TTL 300s)
  wc:standings           str   standings JSON (TTL 300s)
  wc:health              hash  provider / last_poll_ok / degraded
  wc:updates             pub/sub channel (JSON patches)
"""
from __future__ import annotations

import json
from typing import Any

import redis.asyncio as aioredis

from .models import MatchState

STATES_KEY = "wc:states"
CHANNEL = "wc:updates"

TTL_SCOREBOARD = 60
TTL_MATCH = 90
TTL_MATCH_FINAL = None  # finished: no expiry — recap/history pages need it forever
TTL_BRACKET = 300


def make_redis(url: str) -> aioredis.Redis:
    if url.startswith("fakeredis://"):
        # dev/test mode: in-process Redis, no server needed (pub/sub included)
        import fakeredis.aioredis
        return fakeredis.aioredis.FakeRedis(decode_responses=True)
    return aioredis.from_url(url, decode_responses=True)


async def load_states(r: aioredis.Redis) -> dict[int, MatchState]:
    raw = await r.hgetall(STATES_KEY)
    out: dict[int, MatchState] = {}
    for k, v in raw.items():
        try:
            out[int(k)] = MatchState.model_validate_json(v)
        except Exception:  # noqa: BLE001 — drop corrupt entries
            continue
    return out


def diff_states(old: MatchState | None, new: MatchState) -> dict[str, Any] | None:
    """Shallow diff of changed fields; None when nothing visible changed."""
    if old is None:
        return new.model_dump()
    od, nd = old.model_dump(), new.model_dump()
    changed = {k: v for k, v in nd.items() if od.get(k) != v}
    return changed or None


async def store_state(r: aioredis.Redis, new: MatchState,
                      old: MatchState | None) -> dict | None:
    """Write a MatchState; publish + return the patch if it changed."""
    changed = diff_states(old, new)
    if changed is None:
        return None
    await r.hset(STATES_KEY, str(new.match_number), new.model_dump_json())
    patch = {"type": "match", "match_number": new.match_number,
             "changed": changed, "state": new.model_dump()}
    await r.publish(CHANNEL, json.dumps(patch))
    return patch


async def store_json(r: aioredis.Redis, key: str, value: Any, ttl: int | None) -> None:
    await r.set(key, json.dumps(value), ex=ttl)  # ex=None -> no expiry


async def get_json(r: aioredis.Redis, key: str) -> Any | None:
    raw = await r.get(key)
    return json.loads(raw) if raw else None


async def set_health(r: aioredis.Redis, **fields: Any) -> None:
    await r.hset("wc:health", mapping={k: json.dumps(v) for k, v in fields.items()})


async def get_health(r: aioredis.Redis) -> dict:
    raw = await r.hgetall("wc:health")
    out = {}
    for k, v in raw.items():
        try:
            out[k] = json.loads(v)
        except json.JSONDecodeError:
            out[k] = v
    return out
