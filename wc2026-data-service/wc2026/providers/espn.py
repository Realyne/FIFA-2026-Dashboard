"""ESPN unofficial API adapter.

Endpoints (reverse-engineered, community-documented, no auth):
  scoreboard: {BASE}/{league}/scoreboard?dates=YYYYMMDD
  summary:    {BASE}/{league}/summary?event={id}

Parsing is defensive everywhere: unexpected shapes are logged and the raw
payload is dumped under debug/ instead of crashing the poller.
"""
from __future__ import annotations

import json
import logging
import math
import re
import time
from pathlib import Path
from typing import Any

import httpx

from .. import static_data
from ..config import settings
from ..models import (
    LineupPlayer, MatchDetail, MatchEvent, MatchState, ShootoutKick, SideState, TeamLineup,
    TeamStats,
)
from .base import MatchDataProvider

log = logging.getLogger("wc2026.espn")

BASE = "https://site.api.espn.com/apis/site/v2/sports/soccer"
LEAGUE = "fifa.world"

# ESPN status.type.name -> our Status
STATUS_MAP = {
    "STATUS_SCHEDULED": "upcoming",
    "STATUS_DELAYED": "upcoming",
    "STATUS_POSTPONED": "upcoming",
    "STATUS_IN_PROGRESS": "live",
    "STATUS_FIRST_HALF": "live",
    "STATUS_SECOND_HALF": "live",
    "STATUS_HALFTIME": "ht",
    "STATUS_OVERTIME": "et",
    "STATUS_EXTRA_TIME": "et",
    "STATUS_HALFTIME_ET": "et",
    "STATUS_END_OF_REGULATION": "et",
    "STATUS_SHOOTOUT": "pens",
    "STATUS_PENALTIES": "pens",
    "STATUS_FULL_TIME": "finished",
    "STATUS_FINAL": "finished",
    "STATUS_FULL_TIME_AET": "finished",
    "STATUS_FINAL_AET": "finished",
    "STATUS_FINAL_PEN": "finished",
    "STATUS_ABANDONED": "finished",
    "STATUS_FORFEIT": "finished",
    "STATUS_CANCELED": "finished",
}
STATE_FALLBACK = {"pre": "upcoming", "in": "live", "post": "finished"}

EVENT_TYPE_MAP = {
    "own-goal": "own_goal",
    "penalty---scored": "pen_goal",
    "yellow-card": "yellow",
    "red-card": "red",
    "substitution": "sub",
}


def classify_event(ev: Any) -> str | None:
    """keyEvent -> our EventType. ESPN goal types come in many flavors
    (goal, goal---header, goal---free-kick, ...) so scoringPlay is the
    primary goal signal."""
    kind_raw = (g(ev, "type", "type") or "").lower()
    if kind_raw in EVENT_TYPE_MAP:
        return EVENT_TYPE_MAP[kind_raw]
    if g(ev, "scoringPlay") or kind_raw.startswith("goal"):
        if g(ev, "ownGoal") or "own" in kind_raw:
            return "own_goal"
        if g(ev, "penaltyKick") or "penalty" in kind_raw:
            return "pen_goal"
        return "goal"
    return None  # kickoff, delays, VAR, missed pens, etc.


def g(obj: Any, *path: Any, default: Any = None) -> Any:
    """Safe nested getter: g(d, 'a', 0, 'b') -> d['a'][0]['b'] or default."""
    cur = obj
    for key in path:
        try:
            if isinstance(key, int):
                cur = cur[key]
            else:
                cur = cur.get(key)
        except (TypeError, KeyError, IndexError, AttributeError):
            return default
        if cur is None:
            return default
    return cur


def dump_debug(kind: str, payload: Any, note: str) -> None:
    try:
        d = Path(settings().debug_dir)
        d.mkdir(parents=True, exist_ok=True)
        path = d / f"{kind}_{int(time.time())}.json"
        path.write_text(json.dumps({"note": note, "payload": payload}, indent=1)[:2_000_000])
        log.warning("unknown shape (%s): %s — raw saved to %s", kind, note, path)
    except Exception:  # never let debug dumping kill the poller
        log.exception("failed to write debug dump")


def parse_minute(display: str | None, clock_value: float | None = None) -> str | None:
    """ESPN clocks look like "67'" or "90'+3'". Normalize to "67" / "90+3"."""
    if display:
        cleaned = display.replace("'", "").strip()
        if re.fullmatch(r"\d+(\+\d+)?", cleaned):
            return cleaned
    if clock_value:
        try:
            return str(max(1, math.ceil(float(clock_value) / 60)))
        except (TypeError, ValueError):
            return None
    return None


def map_status(status_obj: Any) -> str:
    name = g(status_obj, "type", "name")
    if name in STATUS_MAP:
        return STATUS_MAP[name]
    state = g(status_obj, "type", "state")
    mapped = STATE_FALLBACK.get(state)
    if mapped is None:
        dump_debug("status", status_obj, f"unmapped status name={name!r} state={state!r}")
        return "upcoming"
    if name:  # known state but unknown detailed name — log once, keep going
        log.warning("unmapped ESPN status name %r; using state fallback %r", name, mapped)
    return mapped


def to_int(v: Any) -> int | None:
    try:
        return int(v)
    except (TypeError, ValueError):
        try:
            return int(float(v))
        except (TypeError, ValueError):
            return None


def to_float(v: Any) -> float | None:
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


class ESPNProvider(MatchDataProvider):
    name = "espn"

    def __init__(self, client: httpx.AsyncClient, league: str = LEAGUE):
        self.client = client
        self.league = league

    # ------------------------------------------------------------ fetch --
    async def get_scoreboard(self, date: str) -> list[MatchState]:
        r = await self.client.get(f"{BASE}/{self.league}/scoreboard", params={"dates": date})
        r.raise_for_status()
        return self.parse_scoreboard(r.json())

    async def get_match_detail(self, espn_event_id: str, state: MatchState) -> MatchDetail:
        r = await self.client.get(f"{BASE}/{self.league}/summary", params={"event": espn_event_id})
        r.raise_for_status()
        return self.parse_summary(r.json(), state)

    # ------------------------------------------------------------ parse --
    def parse_scoreboard(self, data: Any) -> list[MatchState]:
        out: list[MatchState] = []
        events = g(data, "events", default=[]) or []
        if not isinstance(events, list):
            dump_debug("scoreboard", data, "events is not a list")
            return out
        for ev in events:
            try:
                st = self._parse_event(ev)
                if st is not None:
                    out.append(st)
            except Exception as exc:  # noqa: BLE001 — single bad event must not kill the batch
                dump_debug("scoreboard_event", ev, f"event parse failed: {exc}")
        return out

    def _parse_event(self, ev: Any) -> MatchState | None:
        comp = g(ev, "competitions", 0)
        if comp is None:
            dump_debug("event", ev, "no competitions[0]")
            return None
        espn_to_fifa = static_data.espn_id_to_fifa()
        sides: dict[str, SideState] = {}
        for c in g(comp, "competitors", default=[]) or []:
            ha = g(c, "homeAway")
            if ha not in ("home", "away"):
                continue
            sides[ha] = SideState(
                fifa_code=espn_to_fifa.get(str(g(c, "team", "id"))),
                score=to_int(g(c, "score")),
                pen_score=to_int(g(c, "shootoutScore")),
            )
        status_obj = g(ev, "status") or g(comp, "status") or {}
        status = map_status(status_obj)
        minute = None
        if status in ("live", "et", "pens"):
            minute = parse_minute(g(status_obj, "displayClock"), g(status_obj, "clock"))
        # pen_score only meaningful for shootouts; ESPN reports 0 otherwise
        if status not in ("pens", "finished"):
            for s in sides.values():
                s.pen_score = None
        # match_number/kickoff/venue are filled by the mapper; carry ESPN's
        # kickoff so the mapper can match on it.
        return MatchState(
            match_number=0,
            espn_event_id=str(g(ev, "id", default="")) or None,
            status=status,
            minute_display=minute,
            home=sides.get("home", SideState()),
            away=sides.get("away", SideState()),
            kickoff_utc=self._norm_date(g(ev, "date")) or "",
            venue_id="",
            round="",
        )

    @staticmethod
    def _norm_date(date_str: str | None) -> str | None:
        if not date_str:
            return None
        # ESPN: "2026-06-11T19:00Z" -> "2026-06-11T19:00:00Z"
        m = re.fullmatch(r"(\d{4}-\d{2}-\d{2}T\d{2}:\d{2})(?::(\d{2}))?Z", date_str)
        if not m:
            return date_str
        return f"{m.group(1)}:{m.group(2) or '00'}Z"

    # ---- summary --------------------------------------------------------
    def parse_summary(self, data: Any, state: MatchState) -> MatchDetail:
        detail = MatchDetail(**state.model_dump())

        # fresher status/score may ride along in header.competitions[0]
        id_to_ha: dict[str, str] = {}
        comp = g(data, "header", "competitions", 0)
        if comp is not None:
            espn_to_fifa = static_data.espn_id_to_fifa()
            for c in g(comp, "competitors", default=[]) or []:
                ha = g(c, "homeAway")
                if ha not in ("home", "away"):
                    continue
                team_id = g(c, "team", "id")
                if team_id is not None:
                    id_to_ha[str(team_id)] = ha
                side: SideState = getattr(detail, ha)
                score = to_int(g(c, "score"))
                if score is not None:
                    side.score = score
                pen = to_int(g(c, "shootoutScore"))
                if pen is not None:
                    side.pen_score = pen
                if side.fifa_code is None:
                    side.fifa_code = espn_to_fifa.get(str(g(c, "team", "id")))
            status_obj = g(comp, "status")
            if status_obj:
                detail.status = map_status(status_obj)
                if detail.status in ("live", "et", "pens"):
                    detail.minute_display = parse_minute(
                        g(status_obj, "displayClock"), g(status_obj, "clock")
                    ) or detail.minute_display
            if detail.status not in ("pens", "finished"):
                detail.home.pen_score = None
                detail.away.pen_score = None

        detail.events = self._parse_key_events(data)
        detail.lineups = self._parse_rosters(data)
        detail.stats = self._parse_boxscore(data)
        detail.shootout = self._parse_shootout(data, id_to_ha)
        return detail

    def _parse_shootout(self, data: Any, id_to_ha: dict[str, str]) -> dict[str, list[ShootoutKick]]:
        """ESPN's top-level `shootout` array -> ordered kicks per side.
        Each team block: {id, team, shots:[{player, shotNumber, didScore}]}."""
        out: dict[str, list[ShootoutKick]] = {}
        for team in g(data, "shootout", default=[]) or []:
            ha = id_to_ha.get(str(g(team, "id")))
            if ha not in ("home", "away"):
                continue
            kicks = []
            for s in g(team, "shots", default=[]) or []:
                pid = g(s, "playerId")
                kicks.append(ShootoutKick(
                    shot_number=to_int(g(s, "shotNumber")),
                    player_name=g(s, "player"),
                    player_espn_id=str(pid) if pid is not None else None,
                    scored=bool(g(s, "didScore")),
                ))
            if kicks:
                out[ha] = sorted(kicks, key=lambda k: k.shot_number or 0)
        return out

    def _team_fifa(self, espn_team_id: Any) -> str | None:
        return static_data.espn_id_to_fifa().get(str(espn_team_id))

    def _parse_key_events(self, data: Any) -> list[MatchEvent]:
        out: list[MatchEvent] = []
        for ev in g(data, "keyEvents", default=[]) or []:
            try:
                kind = classify_event(ev)
                if kind is None:
                    continue
                participants = g(ev, "participants", default=[]) or []
                p0 = g(participants, 0, "athlete") or {}
                p1 = g(participants, 1, "athlete") or {}
                minute = parse_minute(g(ev, "clock", "displayValue"), g(ev, "clock", "value"))
                me = MatchEvent(
                    minute=minute or "0",
                    type=kind,
                    fifa_code=self._team_fifa(g(ev, "team", "id")),
                    player_name=p0.get("displayName"),
                    player_espn_id=str(p0["id"]) if p0.get("id") is not None else None,
                )
                if kind == "sub":
                    # ESPN order: participants[0] comes on, [1] goes off
                    me.sub_off_player = p1.get("displayName")
                elif kind in ("goal", "pen_goal"):
                    me.assist_name = p1.get("displayName")
                out.append(me)
            except Exception as exc:  # noqa: BLE001
                dump_debug("key_event", ev, f"key event parse failed: {exc}")
        return out

    def _parse_rosters(self, data: Any) -> dict[str, TeamLineup]:
        out: dict[str, TeamLineup] = {}
        rosters = g(data, "rosters", default=[]) or []
        for team_block in rosters:
            try:
                ha = g(team_block, "homeAway")
                if ha not in ("home", "away"):
                    continue
                lineup = TeamLineup(
                    fifa_code=self._team_fifa(g(team_block, "team", "id")),
                    formation=g(team_block, "formation"),
                )
                roster = g(team_block, "roster", default=[]) or []
                if not roster:
                    continue  # lineups not announced yet
                for p in roster:
                    athlete = g(p, "athlete") or {}
                    lp = LineupPlayer(
                        shirt_number=to_int(g(p, "jersey")),
                        name=athlete.get("displayName") or athlete.get("fullName") or "?",
                        position=g(p, "position", "abbreviation"),
                        player_espn_id=str(athlete["id"]) if athlete.get("id") is not None else None,
                    )
                    (lineup.starters if g(p, "starter") else lineup.bench).append(lp)
                out[ha] = lineup
            except Exception as exc:  # noqa: BLE001
                dump_debug("roster", team_block, f"roster parse failed: {exc}")
        return out

    _STAT_FIELDS = {
        "possessionPct": ("possession_pct", to_float),
        "totalShots": ("shots", to_int),
        "shotsOnTarget": ("shots_on_target", to_int),
        "wonCorners": ("corners", to_int),
        "foulsCommitted": ("fouls", to_int),
        "offsides": ("offsides", to_int),
    }

    def _parse_boxscore(self, data: Any) -> dict[str, TeamStats]:
        out: dict[str, TeamStats] = {}
        teams_blocks = g(data, "boxscore", "teams", default=[]) or []
        if len(teams_blocks) != 2:
            return out
        # boxscore.teams[] has no homeAway flag; order matches header order
        # (away first historically varies) — match via team id instead.
        comp = g(data, "header", "competitions", 0)
        id_to_ha = {}
        for c in g(comp, "competitors", default=[]) or []:
            id_to_ha[str(g(c, "team", "id"))] = g(c, "homeAway")
        for block in teams_blocks:
            try:
                ha = id_to_ha.get(str(g(block, "team", "id")))
                if ha not in ("home", "away"):
                    continue
                ts = TeamStats()
                for stat in g(block, "statistics", default=[]) or []:
                    name = g(stat, "name")
                    if name in self._STAT_FIELDS:
                        field, conv = self._STAT_FIELDS[name]
                        setattr(ts, field, conv(g(stat, "displayValue")))
                out[ha] = ts
            except Exception as exc:  # noqa: BLE001
                dump_debug("boxscore", block, f"boxscore parse failed: {exc}")
        return out
