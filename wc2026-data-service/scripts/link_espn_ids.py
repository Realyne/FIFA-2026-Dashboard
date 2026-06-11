#!/usr/bin/env python3
"""Best-effort join of ESPN athlete ids onto the player directory.

Reads cached MatchDetails from Redis (wc:match:*), takes every lineup row
(player_espn_id + name + team side fifa_code) and matches it to players.sqlite
by normalized name within the same national team; falls back to
(shirt_number, last name). Run after the first real lineups publish
(June 11+); safe to re-run any time.

When Redis has no lineups (e.g. dev runs with fakeredis://, which is
process-local), falls back to fetching today's summaries straight from
ESPN; --date YYYYMMDD overrides which scoreboard day is fetched.
"""
from __future__ import annotations

import argparse
import asyncio
import sys
import unicodedata
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from wc2026 import cache  # noqa: E402
from wc2026.config import settings  # noqa: E402
from wc2026.players_db import connect  # noqa: E402
from wc2026.providers.espn import ESPNProvider  # noqa: E402


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


async def fetch_lineups_from_espn(date: str) -> list[dict]:
    rows = []
    async with httpx.AsyncClient(
        timeout=20,
        headers={"User-Agent": "wc2026-dashboard (zangjiucheng@gmail.com)"},
    ) as client:
        prov = ESPNProvider(client)
        for state in await prov.get_scoreboard(date):
            detail = await prov.get_match_detail(state.espn_event_id, state)
            for side in ("home", "away"):
                lineup = (detail.lineups or {}).get(side)
                code = getattr(state, side).fifa_code
                if not lineup or not code:
                    continue
                for p in lineup.starters + lineup.bench:
                    if p.player_espn_id:
                        rows.append({"fifa_code": code, "name": p.name,
                                     "shirt_number": p.shirt_number,
                                     "espn_id": p.player_espn_id})
    return rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=None,
                    help="YYYYMMDD scoreboard day for the ESPN fallback (default: today US/Eastern)")
    args = ap.parse_args()

    lineup_rows = asyncio.run(collect_lineups())
    print(f"{len(lineup_rows)} lineup rows from Redis")
    if not lineup_rows:
        date = args.date or datetime.now(ZoneInfo("America/New_York")).strftime("%Y%m%d")
        print(f"falling back to ESPN summaries for {date}")
        lineup_rows = asyncio.run(fetch_lineups_from_espn(date))
        print(f"{len(lineup_rows)} lineup rows from ESPN")
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
