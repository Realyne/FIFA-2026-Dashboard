#!/usr/bin/env python3
"""Best-effort join of ESPN athlete ids onto the player directory.

Reads cached MatchDetails from Redis (wc:match:*), takes every lineup row
(player_espn_id + name + team side fifa_code) and matches it to players.sqlite
by normalized name within the same national team; falls back to
(shirt_number, last name). Run after the first real lineups publish
(June 11+); safe to re-run any time.
"""
from __future__ import annotations

import asyncio
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from wc2026 import cache  # noqa: E402
from wc2026.config import settings  # noqa: E402
from wc2026.players_db import connect  # noqa: E402


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    return " ".join(s.lower().replace("-", " ").split())


async def collect_lineups() -> list[dict]:
    r = cache.make_redis(settings().redis_url)
    rows = []
    async for key in r.scan_iter("wc:match:*"):
        detail = await cache.get_json(r, key)
        if not detail:
            continue
        for side in ("home", "away"):
            lineup = (detail.get("lineups") or {}).get(side) or {}
            code = lineup.get("fifa_code") or (detail.get(side) or {}).get("fifa_code")
            for p in (lineup.get("starters") or []) + (lineup.get("bench") or []):
                if p.get("player_espn_id") and code:
                    rows.append({"fifa_code": code, "name": p["name"],
                                 "shirt_number": p.get("shirt_number"),
                                 "espn_id": p["player_espn_id"]})
    await r.aclose()
    return rows


def main() -> int:
    lineup_rows = asyncio.run(collect_lineups())
    print(f"{len(lineup_rows)} lineup rows from Redis")
    conn = connect()
    players = conn.execute(
        "SELECT player_id, name, fifa_code, shirt_number FROM players").fetchall()
    by_team_name = {}
    by_team_last = {}
    for p in players:
        by_team_name[(p["fifa_code"], norm(p["name"]))] = p["player_id"]
        last = norm(p["name"]).split()[-1] if p["name"].split() else ""
        by_team_last.setdefault((p["fifa_code"], p["shirt_number"], last), p["player_id"])

    linked = unmatched = 0
    for row in lineup_rows:
        pid = by_team_name.get((row["fifa_code"], norm(row["name"])))
        if pid is None:
            last = norm(row["name"]).split()[-1] if row["name"].split() else ""
            pid = by_team_last.get((row["fifa_code"], row["shirt_number"], last))
        if pid is None:
            unmatched += 1
            print(f"unmatched: {row['fifa_code']} {row['name']!r} #{row['shirt_number']}")
            continue
        conn.execute("UPDATE players SET espn_id=? WHERE player_id=? AND espn_id IS NULL",
                     (row["espn_id"], pid))
        linked += 1
    conn.commit()
    print(f"linked {linked}, unmatched {unmatched}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
