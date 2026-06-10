"""Normalized domain models. FIFA 3-letter codes key everything."""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel

Status = Literal["upcoming", "live", "ht", "et", "pens", "finished"]
EventType = Literal["goal", "own_goal", "pen_goal", "yellow", "red", "sub"]


class SideState(BaseModel):
    fifa_code: Optional[str] = None  # None while a knockout slot is unresolved
    score: Optional[int] = None
    pen_score: Optional[int] = None


class MatchState(BaseModel):
    match_number: int
    espn_event_id: Optional[str] = None
    status: Status = "upcoming"
    minute_display: Optional[str] = None  # preserves stoppage, e.g. "90+3"
    home: SideState = SideState()
    away: SideState = SideState()
    kickoff_utc: str
    venue_id: str
    round: str
    group: Optional[str] = None


class MatchEvent(BaseModel):
    minute: str  # "90+3" preserved verbatim
    type: EventType
    player_name: Optional[str] = None
    player_espn_id: Optional[str] = None
    fifa_code: Optional[str] = None
    sub_off_player: Optional[str] = None
    assist_name: Optional[str] = None


class LineupPlayer(BaseModel):
    shirt_number: Optional[int] = None
    name: str
    position: Optional[str] = None
    player_espn_id: Optional[str] = None


class TeamLineup(BaseModel):
    fifa_code: Optional[str] = None
    formation: Optional[str] = None
    starters: list[LineupPlayer] = []
    bench: list[LineupPlayer] = []


class TeamStats(BaseModel):
    possession_pct: Optional[float] = None
    shots: Optional[int] = None
    shots_on_target: Optional[int] = None
    corners: Optional[int] = None
    fouls: Optional[int] = None
    offsides: Optional[int] = None


class MatchDetail(MatchState):
    events: list[MatchEvent] = []
    lineups: dict[str, TeamLineup] = {}  # "home" / "away"
    stats: dict[str, TeamStats] = {}     # "home" / "away"
