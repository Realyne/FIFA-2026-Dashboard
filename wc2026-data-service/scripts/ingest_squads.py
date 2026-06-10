#!/usr/bin/env python3
"""Ingest the 48 final squads into db/players.sqlite.

Source: Wikipedia "2026 FIFA World Cup squads" (squads were finalized
June 2, 2026). openfootball's 2026 dataset carries no squad files, so the
wikitext `{{nat fs g player|...}}` templates are the primary source; they
give shirt number, position, name, DOB, caps, goals and club in one place.

Usage: ingest_squads.py [--db db/players.sqlite] [--cache page.wikitext]
Idempotent: upserts on player_id.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from wc2026 import static_data  # noqa: E402
from wc2026.players_db import connect, player_id  # noqa: E402

UA = "wc2026-dashboard/0.1 (https://github.com/wc2026-dashboard; zangjiucheng@gmail.com) httpx"
PAGE = "2026 FIFA World Cup squads"

# Wikipedia squad-section heading -> our team name (only divergences listed)
HEADING_OVERRIDES = {
    "United States": "USA",
    "South Korea": "South Korea",
    "Korea Republic": "South Korea",
    "Ivory Coast": "Ivory Coast",
    "Côte d'Ivoire": "Ivory Coast",
    "Bosnia and Herzegovina": "Bosnia & Herzegovina",
    "Turkey": "Turkey", "Türkiye": "Turkey",
    "Czechia": "Czech Republic",
    "Cape Verde": "Cape Verde", "Cabo Verde": "Cape Verde",
}

PLAYER_OPEN = "{{nat fs g player"
DOB_RE = re.compile(r"birth date and age2\s*\|\d{4}\|\d{1,2}\|\d{1,2}\|(\d{4})\|(\d{1,2})\|(\d{1,2})")
LINK_RE = re.compile(r"\[\[(?:[^]|]*\|)?([^]|]+)\]\]")


def fetch_wikitext(client: httpx.Client) -> str:
    r = client.get(
        "https://en.wikipedia.org/w/api.php",
        params={"action": "parse", "page": PAGE, "prop": "wikitext", "format": "json"},
    )
    r.raise_for_status()
    return r.json()["parse"]["wikitext"]["*"]


def clean(s: str) -> str:
    s = LINK_RE.sub(r"\1", s)
    s = re.sub(r"\{\{[^}]*\}\}", "", s)  # strip leftover templates (captain tags etc.)
    s = re.sub(r"<[^>]+>", "", s)
    return s.strip()


def player_template_bodies(text: str):
    """Yield the parameter body of each {{nat fs g player|...}} with balanced
    braces (the age param embeds a {{birth date and age2|...}} template, so a
    lazy regex would truncate at its closing braces)."""
    i = 0
    while True:
        start = text.find(PLAYER_OPEN, i)
        if start == -1:
            return
        depth = 0
        j = start
        while j < len(text) - 1:
            pair = text[j:j + 2]
            if pair == "{{":
                depth += 1
                j += 2
            elif pair == "}}":
                depth -= 1
                j += 2
                if depth == 0:
                    break
            else:
                j += 1
        body = text[start + len(PLAYER_OPEN):j - 2].lstrip("|")
        yield body
        i = j


def parse_kv(body: str) -> dict[str, str]:
    """Split template params on top-level pipes (links/templates may nest |)."""
    out: dict[str, str] = {}
    depth = 0
    cur = []
    parts = []
    for ch in body:
        if ch in "[{":
            depth += 1
        elif ch in "]}":
            depth -= 1
        if ch == "|" and depth == 0:
            parts.append("".join(cur)); cur = []
        else:
            cur.append(ch)
    parts.append("".join(cur))
    for p in parts:
        if "=" in p:
            k, v = p.split("=", 1)
            out[k.strip()] = v.strip()
    return out


def parse_squads(wikitext: str) -> list[dict]:
    name_to_code = {t["name"]: t["fifa_code"] for t in static_data.teams()}
    for heading, ours in HEADING_OVERRIDES.items():
        if ours in name_to_code:
            name_to_code[heading] = name_to_code[ours]
        else:
            code = next((t["fifa_code"] for t in static_data.teams() if t["name"] == ours), None)
            if code:
                name_to_code[heading] = code

    players: list[dict] = []
    current_code: str | None = None
    for line_block in re.split(r"\n(?====)", wikitext):
        m = re.match(r"===\s*([^=]+?)\s*===", line_block)
        if m:
            heading = clean(m.group(1))
            current_code = name_to_code.get(heading)
            if current_code is None and heading not in ("Group", ):
                # unknown subsection (e.g. notes); keep last team only for
                # known team headings
                if re.match(r"^[A-Z]", heading) and len(heading) < 40:
                    print(f"unmatched team heading: {heading!r}", file=sys.stderr)
        if current_code is None:
            continue
        for body in player_template_bodies(line_block):
            kv = parse_kv(body)
            name = clean(kv.get("name", ""))
            if not name:
                continue
            dob = None
            dm = DOB_RE.search(kv.get("age", ""))
            if dm:
                dob = f"{dm.group(1)}-{int(dm.group(2)):02d}-{int(dm.group(3)):02d}"
            def num(field):
                v = re.sub(r"[^\d]", "", kv.get(field, ""))
                return int(v) if v else None
            players.append({
                "fifa_code": current_code,
                "shirt_number": num("no"),
                "position": clean(kv.get("pos", "")) or None,
                "name": name,
                "dob": dob,
                "caps": num("caps"),
                "intl_goals": num("goals"),
                "club": clean(kv.get("club", "")) or None,
                "club_country": clean(kv.get("clubnat", "")) or None,
            })
    return players


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=None)
    ap.add_argument("--cache", default=None, help="read/write wikitext cache file")
    args = ap.parse_args()

    cache = Path(args.cache) if args.cache else None
    if cache and cache.exists():
        wikitext = cache.read_text()
    else:
        with httpx.Client(timeout=30, headers={"User-Agent": UA}) as client:
            wikitext = fetch_wikitext(client)
        if cache:
            cache.write_text(wikitext)

    players = parse_squads(wikitext)
    per_team: dict[str, int] = {}
    for p in players:
        per_team[p["fifa_code"]] = per_team.get(p["fifa_code"], 0) + 1
    print(f"parsed {len(players)} players across {len(per_team)} teams")
    short = {k: v for k, v in per_team.items() if v < 23}
    if short:
        print(f"WARNING: suspiciously small squads: {short}", file=sys.stderr)
    if len(per_team) != 48:
        missing = {t["fifa_code"] for t in static_data.teams()} - set(per_team)
        print(f"WARNING: missing squads for {missing}", file=sys.stderr)

    conn = connect(args.db) if args.db else connect()
    now = datetime.now(timezone.utc).isoformat()
    for p in players:
        pid = player_id(p["fifa_code"], p["shirt_number"], p["name"])
        search_url = f"https://www.fifa.com/en/search?q={quote(p['name'])}"
        conn.execute(
            """INSERT INTO players(player_id, name, fifa_code, shirt_number, dob,
                 position, club, club_country, caps, intl_goals,
                 fifa_profile_url, fetched_at, source)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(player_id) DO UPDATE SET
                 name=excluded.name, shirt_number=excluded.shirt_number,
                 dob=excluded.dob, position=excluded.position,
                 club=excluded.club, club_country=excluded.club_country,
                 caps=COALESCE(excluded.caps, players.caps),
                 intl_goals=COALESCE(excluded.intl_goals, players.intl_goals),
                 fifa_profile_url=COALESCE(players.fifa_profile_url, excluded.fifa_profile_url)
            """,
            (pid, p["name"], p["fifa_code"], p["shirt_number"], p["dob"],
             p["position"], p["club"], p["club_country"], p["caps"],
             p["intl_goals"], search_url, now, "wikipedia_squads"),
        )
    conn.execute("INSERT OR REPLACE INTO meta(key, value) VALUES('squads_ingested_at', ?)", (now,))
    conn.commit()
    total = conn.execute("SELECT COUNT(*) FROM players").fetchone()[0]
    print(f"db now holds {total} players")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
