#!/usr/bin/env python3
"""Capture real ESPN payloads into tests/fixtures/ (and debug/ for inspection).

Usage:
  capture_fixtures.py [--league fifa.world] [--date YYYYMMDD] [--event ESPN_EVENT_ID]

Run this on June 11 against the first live World Cup match, then re-run the
parser tests; fix ESPNProvider against any shape drift it reveals.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "tests" / "fixtures"
UA = "wc2026-data-service/0.1 fixture-capture"
BASE = "https://site.api.espn.com/apis/site/v2/sports/soccer"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--league", default="fifa.world")
    ap.add_argument("--date", default=datetime.now(timezone.utc).strftime("%Y%m%d"))
    ap.add_argument("--event", default=None, help="ESPN event id for summary; default: first event on the scoreboard")
    args = ap.parse_args()

    FIXTURES.mkdir(parents=True, exist_ok=True)
    client = httpx.Client(timeout=15, headers={"User-Agent": UA})

    sb_url = f"{BASE}/{args.league}/scoreboard?dates={args.date}"
    sb = client.get(sb_url)
    sb.raise_for_status()
    sb_data = sb.json()
    sb_path = FIXTURES / f"scoreboard_{args.league.replace('.', '_')}_{args.date}.json"
    sb_path.write_text(json.dumps(sb_data, indent=1) + "\n")
    print(f"saved {sb_path} ({len(sb_data.get('events', []))} events)")

    event_id = args.event
    if event_id is None:
        events = sb_data.get("events", [])
        if not events:
            print("no events on scoreboard; pass --event explicitly")
            return 1
        event_id = events[0]["id"]

    su_url = f"{BASE}/{args.league}/summary?event={event_id}"
    su = client.get(su_url)
    su.raise_for_status()
    su_path = FIXTURES / f"summary_{args.league.replace('.', '_')}_{event_id}.json"
    su_path.write_text(json.dumps(su.json(), indent=1) + "\n")
    print(f"saved {su_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
