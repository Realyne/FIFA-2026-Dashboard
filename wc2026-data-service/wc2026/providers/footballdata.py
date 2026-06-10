"""football-data.org v4 failover adapter (competition WC).

Stub by design: enable by paying for the livescore tier, setting
FOOTBALL_DATA_TOKEN and DATA_PROVIDER=footballdata. Scoreboard works on the
free schema; per-match detail (events/lineups) is intentionally minimal —
the SPA degrades to score-only when this provider is active.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta

import httpx

from .. import static_data
from ..models import MatchDetail, MatchState, SideState
from .base import MatchDataProvider

log = logging.getLogger("wc2026.footballdata")

BASE = "https://api.football-data.org/v4"

STATUS_MAP = {
    "SCHEDULED": "upcoming", "TIMED": "upcoming", "POSTPONED": "upcoming",
    "IN_PLAY": "live", "PAUSED": "ht", "EXTRA_TIME": "et",
    "PENALTY_SHOOTOUT": "pens", "FINISHED": "finished",
    "SUSPENDED": "live", "CANCELLED": "finished", "AWARDED": "finished",
}


class FootballDataProvider(MatchDataProvider):
    name = "footballdata"

    def __init__(self, client: httpx.AsyncClient, token: str | None):
        if not token:
            raise RuntimeError("DATA_PROVIDER=footballdata requires FOOTBALL_DATA_TOKEN")
        self.client = client
        self.token = token

    def _headers(self) -> dict:
        return {"X-Auth-Token": self.token}

    async def get_scoreboard(self, date: str) -> list[MatchState]:
        day = datetime.strptime(date, "%Y%m%d").date()
        r = await self.client.get(
            f"{BASE}/competitions/WC/matches",
            params={
                "dateFrom": day.isoformat(),
                "dateTo": (day + timedelta(days=1)).isoformat(),
            },
            headers=self._headers(),
        )
        r.raise_for_status()
        out: list[MatchState] = []
        fd_to_fifa = {
            t["footballdata_team_id"]: t["fifa_code"]
            for t in static_data.teams() if t.get("footballdata_team_id")
        }
        for m in r.json().get("matches", []):
            try:
                ft = m.get("score", {}).get("fullTime", {})
                pens = m.get("score", {}).get("penalties") or {}
                status = STATUS_MAP.get(m.get("status"), "upcoming")
                out.append(MatchState(
                    match_number=0,
                    espn_event_id=None,
                    status=status,
                    minute_display=str(m.get("minute")) if m.get("minute") else None,
                    home=SideState(
                        fifa_code=fd_to_fifa.get(m.get("homeTeam", {}).get("id")),
                        score=ft.get("home"),
                        pen_score=pens.get("home"),
                    ),
                    away=SideState(
                        fifa_code=fd_to_fifa.get(m.get("awayTeam", {}).get("id")),
                        score=ft.get("away"),
                        pen_score=pens.get("away"),
                    ),
                    kickoff_utc=(m.get("utcDate") or "").replace(".000Z", "Z"),
                    venue_id="",
                    round="",
                ))
            except Exception:  # noqa: BLE001
                log.exception("football-data match parse failed: %r", m)
        return out

    async def get_match_detail(self, espn_event_id: str, state: MatchState) -> MatchDetail:
        # TODO when failover is purchased: fetch /v4/matches/{id} for events.
        return MatchDetail(**state.model_dump())
