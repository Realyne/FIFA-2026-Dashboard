"""Tournament top scorers (Golden Boot), aggregated from match events.

Finished match details are cached forever (TTL_MATCH_FINAL = None), so summing
their goal events gives a complete, live-updating scorer board. Own goals are
NOT credited to the scorer.
"""
from __future__ import annotations

GOAL_TYPES = ("goal", "pen_goal")


def tournament_scorers(details: list[dict | None]) -> list[dict]:
    """details: cached MatchDetail dicts (some may be None/absent).
    Returns scorers sorted by goals desc, then open-play goals desc, then name."""
    tally: dict[str, dict] = {}
    for d in details:
        if not d:
            continue
        for e in d.get("events", []) or []:
            if e.get("type") not in GOAL_TYPES:
                continue
            name = e.get("player_name")
            if not name:
                continue
            code = e.get("fifa_code")
            espn = e.get("player_espn_id")
            key = str(espn) if espn else f"{code}|{name}"
            s = tally.get(key)
            if s is None:
                s = {"player_name": name, "fifa_code": code,
                     "player_espn_id": espn, "goals": 0, "penalties": 0}
                tally[key] = s
            s["goals"] += 1
            if e.get("type") == "pen_goal":
                s["penalties"] += 1
    scorers = list(tally.values())
    scorers.sort(key=lambda s: (-s["goals"], -(s["goals"] - s["penalties"]), s["player_name"]))
    return scorers
