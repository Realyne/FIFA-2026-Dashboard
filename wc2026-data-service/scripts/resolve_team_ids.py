#!/usr/bin/env python3
"""Fill espn_team_id / footballdata_team_id in data/static/teams.json.

ESPN: https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world/teams (no auth)
football-data.org: GET /v4/competitions/WC/teams with X-Auth-Token from
FOOTBALL_DATA_TOKEN (skipped gracefully when unset).

Matching is by normalized name with a manual override map for names the two
providers spell differently.
"""
from __future__ import annotations

import json
import os
import sys
import unicodedata
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
TEAMS_PATH = ROOT / "data" / "static" / "teams.json"
UA = "wc2026-data-service/0.1 (+https://github.com/; contact: ops)"

# provider name -> our openfootball name (after normalization)
NAME_OVERRIDES = {
    # ESPN / football-data spellings -> ours
    "south korea": "south korea", "korea republic": "south korea",
    "ir iran": "iran", "iran": "iran",
    "cote divoire": "ivory coast", "ivory coast": "ivory coast",
    "czechia": "czech republic", "czech republic": "czech republic",
    "bosnia and herzegovina": "bosnia & herzegovina",
    "bosnia herzegovina": "bosnia & herzegovina",
    "bosnia-herzegovina": "bosnia & herzegovina",
    "united states": "usa", "usa": "usa", "united states of america": "usa",
    "turkiye": "turkey", "turkey": "turkey",
    "cabo verde": "cape verde", "cape verde islands": "cape verde",
    "dr congo": "dr congo", "congo dr": "dr congo",
    "democratic republic of the congo": "dr congo",
    "netherlands": "netherlands", "holland": "netherlands",
    "saudi arabia": "saudi arabia", "ksa": "saudi arabia",
    "curacao": "curaçao",
}


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.lower().replace("'", "").replace(".", "").strip()
    return " ".join(s.split())


def our_key(provider_name: str) -> str:
    n = norm(provider_name)
    return NAME_OVERRIDES.get(n, n)


def main() -> int:
    teams = json.loads(TEAMS_PATH.read_text())
    by_name = {norm(t["name"]): t for t in teams}
    # curaçao normalizes to curacao; index both
    by_name.update({our_key(t["name"]): t for t in teams})

    client = httpx.Client(timeout=15, headers={"User-Agent": UA})

    # ---- ESPN -----------------------------------------------------------
    r = client.get("https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world/teams")
    r.raise_for_status()
    espn_teams = r.json()["sports"][0]["leagues"][0]["teams"]
    matched = 0
    for entry in espn_teams:
        t = entry["team"]
        key = our_key(t["displayName"])
        target = by_name.get(key)
        if target is None:
            print(f"ESPN unmatched: {t['displayName']!r} (id={t['id']})", file=sys.stderr)
            continue
        target["espn_team_id"] = str(t["id"])
        matched += 1
    print(f"ESPN: matched {matched}/{len(espn_teams)}")

    # ---- football-data.org ----------------------------------------------
    token = os.environ.get("FOOTBALL_DATA_TOKEN")
    if not token:
        print("FOOTBALL_DATA_TOKEN unset; skipping football-data.org")
    else:
        r = client.get(
            "https://api.football-data.org/v4/competitions/WC/teams",
            headers={"X-Auth-Token": token},
        )
        r.raise_for_status()
        fd_teams = r.json().get("teams", [])
        matched = 0
        for t in fd_teams:
            key = our_key(t.get("name", ""))
            target = by_name.get(key) or by_name.get(our_key(t.get("shortName", "")))
            if target is None:
                print(f"football-data unmatched: {t.get('name')!r} (id={t.get('id')})", file=sys.stderr)
                continue
            target["footballdata_team_id"] = t["id"]
            matched += 1
        print(f"football-data: matched {matched}/{len(fd_teams)}")

    missing = [t["fifa_code"] for t in teams if not t["espn_team_id"]]
    if missing:
        print(f"WARNING: no espn_team_id for: {missing}", file=sys.stderr)

    TEAMS_PATH.write_text(json.dumps(teams, indent=1, ensure_ascii=False) + "\n")
    print(f"wrote {TEAMS_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
