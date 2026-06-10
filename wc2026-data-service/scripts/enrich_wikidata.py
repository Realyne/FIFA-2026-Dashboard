#!/usr/bin/env python3
"""Enrich db/players.sqlite from Wikidata (offline/batch — never per-request).

Per player: QID, DOB sanity-check, national-team caps (P1350) and goals
(P1351) taken from the P54 statement for the NATIONAL team (never a club),
and past World Cup participations (P1344).

Wikimedia etiquette: batched VALUES queries (~40 labels), descriptive
User-Agent, sleep between requests, retry with backoff on 429/5xx.
Idempotent + resumable: rows enriched within REFRESH_DAYS (default 7) are
skipped. Unresolved players are listed in db/wikidata_review.txt.

Usage: enrich_wikidata.py [--db PATH] [--batch 40] [--limit N]
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from wc2026 import static_data  # noqa: E402
from wc2026.players_db import connect  # noqa: E402

SPARQL = "https://query.wikidata.org/sparql"
UA = "wc2026-dashboard/0.1 (https://github.com/wc2026-dashboard; zangjiucheng@gmail.com) httpx"
REFRESH_DAYS = int(os.environ.get("REFRESH_DAYS", "7"))
REVIEW_FILE = Path(__file__).resolve().parent.parent / "db" / "wikidata_review.txt"

# fifa_code -> keywords a national-team label must contain (lowercased check)
TEAM_KEYWORD_OVERRIDES = {
    "USA": ["united states"],
    "KOR": ["south korea", "korea republic"],
    "CIV": ["ivory coast", "côte d'ivoire"],
    "CZE": ["czech"],
    "BIH": ["bosnia"],
    "COD": ["dr congo", "democratic republic of the congo", "congo dr"],
    "CPV": ["cape verde", "cabo verde"],
    "KSA": ["saudi arabia"],
    "RSA": ["south africa"],
    "TUR": ["turkey", "türkiye"],
    "NED": ["netherlands"],
}


def team_keywords(fifa_code: str) -> list[str]:
    if fifa_code in TEAM_KEYWORD_OVERRIDES:
        return TEAM_KEYWORD_OVERRIDES[fifa_code]
    name = static_data.team_by_code()[fifa_code]["name"]
    return [name.lower()]


def is_national_team_label(label: str, fifa_code: str) -> bool:
    l = label.lower()
    if "national" not in l and "olympic" not in l:
        return False
    if "under-" in l or "u-2" in l or "u-1" in l or "youth" in l or "olympic" in l \
            or "women" in l or " b team" in l:
        return False
    return any(kw in l for kw in team_keywords(fifa_code))


def run_query(client: httpx.Client, query: str, retries: int = 4) -> list[dict]:
    for attempt in range(retries):
        r = client.get(SPARQL, params={"query": query, "format": "json"})
        if r.status_code == 429 or r.status_code >= 500:
            wait = float(r.headers.get("Retry-After", 2 ** (attempt + 1)))
            time.sleep(wait)
            continue
        r.raise_for_status()
        return r.json()["results"]["bindings"]
    raise RuntimeError("SPARQL retries exhausted")


def quote_label(name: str) -> str:
    return '"' + name.replace("\\", "").replace('"', "") + '"@en'


def resolve_batch(client: httpx.Client, names: list[str]) -> list[dict]:
    """One row per (player-candidate, P54 statement)."""
    values = " ".join(quote_label(n) for n in names)
    query = f"""
SELECT ?p ?name ?dob ?teamLabel ?caps ?goals WHERE {{
  VALUES ?name {{ {values} }}
  {{ ?p rdfs:label ?name . }} UNION {{ ?p skos:altLabel ?name . }}
  ?p wdt:P106 wd:Q937857 .
  OPTIONAL {{ ?p wdt:P569 ?dob . }}
  OPTIONAL {{
    ?p p:P54 ?stmt .
    ?stmt ps:P54 ?team .
    OPTIONAL {{ ?stmt pq:P1350 ?caps . }}
    OPTIONAL {{ ?stmt pq:P1351 ?goals . }}
    ?team rdfs:label ?teamLabel . FILTER(LANG(?teamLabel)='en')
  }}
}}"""
    return run_query(client, query)


def participations_batch(client: httpx.Client, qids: list[str]) -> dict[str, list[int]]:
    values = " ".join(f"wd:{q}" for q in qids)
    query = f"""
SELECT ?p ?eventLabel WHERE {{
  VALUES ?p {{ {values} }}
  ?p wdt:P1344 ?event .
  ?event rdfs:label ?eventLabel . FILTER(LANG(?eventLabel)='en')
}}"""
    out: dict[str, list[int]] = {}
    for row in run_query(client, query):
        qid = row["p"]["value"].rsplit("/", 1)[-1]
        label = row["eventLabel"]["value"]
        m = re.match(r"^(\d{4}) FIFA World Cup$", label)
        if m:
            year = int(m.group(1))
            if year < 2026:
                out.setdefault(qid, []).append(year)
    return {q: sorted(set(years)) for q, years in out.items()}


def pick_candidate(rows: list[dict], fifa_code: str, squad_dob: str | None) -> dict | None:
    """rows: SPARQL bindings for one name. Choose the QID whose P54 includes
    the right national team; extract caps/goals from THAT statement only."""
    by_qid: dict[str, dict] = {}
    for row in rows:
        qid = row["p"]["value"].rsplit("/", 1)[-1]
        ent = by_qid.setdefault(qid, {"qid": qid, "dob": None, "nat": None})
        if "dob" in row and not ent["dob"]:
            ent["dob"] = row["dob"]["value"][:10]
        team_label = row.get("teamLabel", {}).get("value", "")
        if team_label and is_national_team_label(team_label, fifa_code):
            caps = row.get("caps", {}).get("value")
            goals = row.get("goals", {}).get("value")
            cur = ent.get("nat")
            # keep the statement with the most data
            if cur is None or (cur["caps"] is None and caps is not None):
                ent["nat"] = {
                    "team_label": team_label,
                    "caps": int(float(caps)) if caps is not None else None,
                    "goals": int(float(goals)) if goals is not None else None,
                }
    candidates = [e for e in by_qid.values() if e["nat"]]
    if not candidates:
        return None
    if len(candidates) > 1 and squad_dob:
        dob_match = [e for e in candidates if e["dob"] == squad_dob]
        if dob_match:
            candidates = dob_match
    return candidates[0]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=None)
    ap.add_argument("--batch", type=int, default=40)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--sleep", type=float, default=1.5)
    args = ap.parse_args()

    conn = connect(args.db) if args.db else connect()
    cutoff = (datetime.now(timezone.utc) - timedelta(days=REFRESH_DAYS)).isoformat()
    rows = conn.execute(
        """SELECT player_id, name, fifa_code, dob FROM players
           WHERE NOT (source='wikidata' AND fetched_at > ?)
           ORDER BY fifa_code, shirt_number""",
        (cutoff,),
    ).fetchall()
    if args.limit:
        rows = rows[: args.limit]
    print(f"{len(rows)} players to enrich (REFRESH_DAYS={REFRESH_DAYS})")

    client = httpx.Client(timeout=60, headers={"User-Agent": UA})
    unresolved: list[str] = []
    mismatched_dob: list[str] = []
    resolved = 0

    for i in range(0, len(rows), args.batch):
        chunk = rows[i:i + args.batch]
        names = sorted({r["name"] for r in chunk})
        try:
            bindings = resolve_batch(client, names)
        except Exception as exc:  # noqa: BLE001
            print(f"batch {i // args.batch} failed: {exc}", file=sys.stderr)
            time.sleep(10)
            continue
        by_name: dict[str, list[dict]] = {}
        for b in bindings:
            by_name.setdefault(b["name"]["value"], []).append(b)

        qid_updates: dict[str, dict] = {}
        for r in chunk:
            cand = pick_candidate(by_name.get(r["name"], []), r["fifa_code"], r["dob"])
            if cand is None:
                unresolved.append(f"{r['player_id']}\t{r['name']}\t{r['fifa_code']}")
                continue
            if r["dob"] and cand["dob"] and cand["dob"] != r["dob"]:
                mismatched_dob.append(
                    f"{r['player_id']}\t{r['name']}\tsquad={r['dob']}\twikidata={cand['dob']}")
            qid_updates[r["player_id"]] = cand
            resolved += 1

        # past World Cups for this chunk's QIDs
        parts: dict[str, list[int]] = {}
        qids = sorted({c["qid"] for c in qid_updates.values()})
        if qids:
            try:
                time.sleep(args.sleep)
                parts = participations_batch(client, qids)
            except Exception as exc:  # noqa: BLE001
                print(f"participations batch failed: {exc}", file=sys.stderr)

        now = datetime.now(timezone.utc).isoformat()
        for pid, cand in qid_updates.items():
            conn.execute(
                """UPDATE players SET
                     wikidata_qid=?,
                     caps=COALESCE(?, caps),
                     intl_goals=COALESCE(?, intl_goals),
                     past_world_cups=?,
                     fetched_at=?, source='wikidata'
                   WHERE player_id=?""",
                (cand["qid"], cand["nat"]["caps"], cand["nat"]["goals"],
                 json.dumps(parts.get(cand["qid"], [])), now, pid),
            )
        conn.commit()
        done = min(i + args.batch, len(rows))
        print(f"  {done}/{len(rows)} processed, {resolved} resolved")
        time.sleep(args.sleep)

    REVIEW_FILE.parent.mkdir(exist_ok=True)
    with REVIEW_FILE.open("w") as f:
        f.write("# unresolved players (no Wikidata QID with matching national team)\n")
        f.write("\n".join(unresolved) + "\n")
        if mismatched_dob:
            f.write("\n# DOB mismatches (accepted, review)\n")
            f.write("\n".join(mismatched_dob) + "\n")
    conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('wikidata_enriched_at',?)",
                 (datetime.now(timezone.utc).isoformat(),))
    conn.commit()
    print(f"done: {resolved} resolved, {len(unresolved)} unresolved "
          f"(see {REVIEW_FILE.name}), {len(mismatched_dob)} dob mismatches")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
