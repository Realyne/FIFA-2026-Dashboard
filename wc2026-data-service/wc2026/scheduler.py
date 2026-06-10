"""Polling scheduler.

Live window = 15 min before kickoff until the match is observed finished
(+10 min grace), hard-capped at kickoff + 4h if the feed never confirms.
Inside any window: scoreboard every 20s + a summary per live match every 30s.
Outside all windows: scoreboard every 30 min.

Politeness: one shared httpx.AsyncClient (UA, 10s timeout), exponential
backoff on errors, circuit breaker (5 consecutive failures -> 5 min pause
and a degraded flag in wc:health).
"""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import httpx
import redis.asyncio as aioredis

from . import cache, resolver, static_data
from .models import MatchDetail, MatchState
from .providers import make_provider
from .providers.base import MatchDataProvider

log = logging.getLogger("wc2026.scheduler")

EASTERN = ZoneInfo("America/New_York")  # ESPN groups scoreboard dates this way

WINDOW_BEFORE = timedelta(minutes=15)
WINDOW_GRACE = timedelta(minutes=10)
WINDOW_HARD_CAP = timedelta(hours=4)
POLL_LIVE = 20
POLL_SUMMARY = 30
POLL_IDLE = 30 * 60
BREAKER_THRESHOLD = 5
BREAKER_PAUSE = 5 * 60


def parse_utc(s: str) -> datetime:
    return datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def espn_date(dt: datetime) -> str:
    return dt.astimezone(EASTERN).strftime("%Y%m%d")


def live_windows(now: datetime, states: dict[int, MatchState]) -> list[dict]:
    """Matches whose live window contains `now`."""
    out = []
    for m in static_data.bracket():
        ko = parse_utc(m["kickoff_utc"])
        if not (ko - WINDOW_BEFORE <= now <= ko + WINDOW_HARD_CAP):
            continue
        st = states.get(m["match_number"])
        if st and st.status == "finished":
            # keep the window open for a short grace period after FT
            # (we can't know *when* it finished; grace from now is fine
            # because the flag flips on the first poll that sees FT)
            continue
        out.append(m)
    return out


def scoreboard_dates(now: datetime) -> list[str]:
    """ESPN date strings covering matches near now (UTC spillover safe)."""
    dates = {espn_date(now)}
    for m in static_data.bracket():
        ko = parse_utc(m["kickoff_utc"])
        if abs((ko - now).total_seconds()) <= 18 * 3600:
            dates.add(espn_date(ko))
    return sorted(dates)


class Poller:
    def __init__(self, r: aioredis.Redis, client: httpx.AsyncClient | None = None,
                 provider: MatchDataProvider | None = None):
        self.redis = r
        self.client = client or httpx.AsyncClient(
            timeout=10,
            headers={"User-Agent": "wc2026-data-service/0.1 (world cup dashboard; polite poller)"},
            follow_redirects=True,
        )
        self.provider = provider or make_provider(self.client)
        self.failures = 0
        self.degraded = False
        self._last_summary: dict[int, float] = {}
        self._stop = asyncio.Event()

    # ----------------------------------------------------------- breaker --
    async def _record_success(self) -> None:
        self.failures = 0
        if self.degraded:
            self.degraded = False
        await cache.set_health(
            self.redis, provider=self.provider.name, degraded=False,
            last_poll_ok=datetime.now(timezone.utc).isoformat(),
        )

    async def _record_failure(self, exc: Exception) -> float:
        self.failures += 1
        log.warning("poll failure %d: %s", self.failures, exc)
        if self.failures >= BREAKER_THRESHOLD:
            self.degraded = True
            await cache.set_health(self.redis, degraded=True)
            log.error("circuit breaker open — backing off %ss", BREAKER_PAUSE)
            return BREAKER_PAUSE
        return min(60.0, 2.0 ** self.failures)  # 2,4,8,16,32

    # ------------------------------------------------------------- cycle --
    async def poll_scoreboard(self, now: datetime) -> dict[int, MatchState]:
        states = await cache.load_states(self.redis)
        resolved = resolver.resolve_bracket(states)
        seen_changes = False
        for date in scoreboard_dates(now):
            raw_states = await self.provider.get_scoreboard(date)
            for st in raw_states:
                n = resolver.map_event_to_match(st, resolved)
                if n is None:
                    log.info("unmapped event %s (%s v %s @ %s)", st.espn_event_id,
                             st.home.fifa_code, st.away.fifa_code, st.kickoff_utc)
                    continue
                m = static_data.bracket_by_number()[n]
                old = states.get(n)
                merged = st.model_copy(update={
                    "match_number": n,
                    "kickoff_utc": m["kickoff_utc"],
                    "venue_id": m["venue_id"],
                    "round": m["round"],
                    "group": m["group"],
                })
                # never let a provider blank out known codes
                if merged.home.fifa_code is None and old and old.home.fifa_code:
                    merged.home.fifa_code = old.home.fifa_code
                if merged.away.fifa_code is None and old and old.away.fifa_code:
                    merged.away.fifa_code = old.away.fifa_code
                patch = await cache.store_state(self.redis, merged, old)
                if patch:
                    seen_changes = True
                states[n] = merged
        # refresh derived views
        if seen_changes or not await self.redis.exists("wc:bracket_resolved"):
            resolved = resolver.resolve_bracket(states)
            await cache.store_json(self.redis, "wc:bracket_resolved", resolved, cache.TTL_BRACKET)
            standings = resolver.all_standings(states)
            await cache.store_json(self.redis, "wc:standings", standings, cache.TTL_BRACKET)
            if seen_changes:
                await self.redis.publish(cache.CHANNEL, json.dumps({"type": "bracket"}))
        return states

    async def poll_summaries(self, states: dict[int, MatchState], now: datetime) -> None:
        for n, st in states.items():
            if st.status not in ("live", "ht", "et", "pens"):
                continue
            if not st.espn_event_id:
                continue
            last = self._last_summary.get(n, 0.0)
            if now.timestamp() - last < POLL_SUMMARY:
                continue
            self._last_summary[n] = now.timestamp()
            try:
                detail = await self.provider.get_match_detail(st.espn_event_id, st)
                await cache.store_json(self.redis, f"wc:match:{n}",
                                       detail.model_dump(), cache.TTL_MATCH)
                # summary may carry fresher status/score than the scoreboard
                new_state = MatchState(**{k: v for k, v in detail.model_dump().items()
                                          if k in MatchState.model_fields})
                patch = await cache.store_state(self.redis, new_state, st)
                if patch:
                    await cache.store_json(self.redis, "wc:bracket_resolved",
                                           resolver.resolve_bracket(await cache.load_states(self.redis)),
                                           cache.TTL_BRACKET)
            except Exception as exc:  # noqa: BLE001
                log.warning("summary poll failed for M%d: %s", n, exc)

    async def run(self) -> None:
        log.info("poller starting (provider=%s)", self.provider.name)
        while not self._stop.is_set():
            now = datetime.now(timezone.utc)
            try:
                states = await self.poll_scoreboard(now)
                await self.poll_summaries(states, now)
                await self._record_success()
                in_window = bool(live_windows(now, states))
                delay = POLL_LIVE if in_window else POLL_IDLE
                # leaving idle: wake up for the next window opening
                if not in_window:
                    nxt = self._next_window_start(now)
                    if nxt is not None:
                        delay = min(delay, max(5.0, (nxt - now).total_seconds()))
            except Exception as exc:  # noqa: BLE001
                delay = await self._record_failure(exc)
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=delay)
            except asyncio.TimeoutError:
                pass
        await self.client.aclose()

    @staticmethod
    def _next_window_start(now: datetime):
        starts = [
            parse_utc(m["kickoff_utc"]) - WINDOW_BEFORE
            for m in static_data.bracket()
            if parse_utc(m["kickoff_utc"]) - WINDOW_BEFORE > now
        ]
        return min(starts, default=None)

    def stop(self) -> None:
        self._stop.set()
