"""Static tournament data (bracket / teams / venues) loaded once at startup."""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATIC = ROOT / "data" / "static"


@lru_cache
def bracket() -> list[dict]:
    return json.loads((STATIC / "bracket.json").read_text())


@lru_cache
def teams() -> list[dict]:
    return json.loads((STATIC / "teams.json").read_text())


@lru_cache
def venues() -> list[dict]:
    return json.loads((STATIC / "venues.json").read_text())


@lru_cache
def bracket_by_number() -> dict[int, dict]:
    return {m["match_number"]: m for m in bracket()}


@lru_cache
def team_by_code() -> dict[str, dict]:
    return {t["fifa_code"]: t for t in teams()}


@lru_cache
def espn_id_to_fifa() -> dict[str, str]:
    return {t["espn_team_id"]: t["fifa_code"] for t in teams() if t.get("espn_team_id")}


@lru_cache
def group_matches() -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    for m in bracket():
        if m["round"] == "group":
            out.setdefault(m["group"], []).append(m)
    return out
