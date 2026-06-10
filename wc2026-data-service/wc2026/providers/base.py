from __future__ import annotations

from abc import ABC, abstractmethod

from ..models import MatchDetail, MatchState


class MatchDataProvider(ABC):
    """Abstract live-data source. All provider-specific JSON parsing lives in
    the concrete implementation — nothing upstream sees raw provider shapes."""

    name: str = "abstract"

    @abstractmethod
    async def get_scoreboard(self, date: str) -> list[MatchState]:
        """date: YYYYMMDD (provider-local grouping). Returns normalized states
        for events the provider lists on that date; match_number is 0 when the
        provider event could not be mapped to a bracket match (caller decides)."""

    @abstractmethod
    async def get_match_detail(self, espn_event_id: str, state: MatchState) -> MatchDetail:
        """Fetch detail for one event, merging onto an already-mapped state."""
