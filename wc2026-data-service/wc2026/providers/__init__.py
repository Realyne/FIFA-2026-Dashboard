from __future__ import annotations

import httpx

from ..config import settings
from .base import MatchDataProvider
from .espn import ESPNProvider
from .footballdata import FootballDataProvider


def make_provider(client: httpx.AsyncClient) -> MatchDataProvider:
    cfg = settings()
    if cfg.data_provider == "footballdata":
        return FootballDataProvider(client, cfg.football_data_token)
    return ESPNProvider(client)
