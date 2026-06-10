#!/usr/bin/env python3
"""Generate data/static/{bracket,teams,venues}.json from the openfootball raw dataset.

Sources and mapping decisions are documented in SOURCES.md. Deterministic:
re-running on the same raw file produces identical output.
"""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw" / "openfootball-2026.json"
OUT = ROOT / "data" / "static"

# ---------------------------------------------------------------- teams ----
# openfootball display name -> FIFA 3-letter code (primary key of the system)
NAME_TO_FIFA = {
    "Algeria": "ALG", "Argentina": "ARG", "Australia": "AUS", "Austria": "AUT",
    "Belgium": "BEL", "Bosnia & Herzegovina": "BIH", "Brazil": "BRA",
    "Canada": "CAN", "Cape Verde": "CPV", "Colombia": "COL", "Croatia": "CRO",
    "Curaçao": "CUW", "Czech Republic": "CZE", "DR Congo": "COD",
    "Ecuador": "ECU", "Egypt": "EGY", "England": "ENG", "France": "FRA",
    "Germany": "GER", "Ghana": "GHA", "Haiti": "HAI", "Iran": "IRN",
    "Iraq": "IRQ", "Ivory Coast": "CIV", "Japan": "JPN", "Jordan": "JOR",
    "Mexico": "MEX", "Morocco": "MAR", "Netherlands": "NED",
    "New Zealand": "NZL", "Norway": "NOR", "Panama": "PAN", "Paraguay": "PAR",
    "Portugal": "POR", "Qatar": "QAT", "Saudi Arabia": "KSA",
    "Scotland": "SCO", "Senegal": "SEN", "South Africa": "RSA",
    "South Korea": "KOR", "Spain": "ESP", "Sweden": "SWE",
    "Switzerland": "SUI", "Tunisia": "TUN", "Turkey": "TUR",
    "Uruguay": "URU", "USA": "USA", "Uzbekistan": "UZB",
}

# FIFA code -> ISO 3166-1 alpha-2 (flagcdn.com code). Explicit, no guessing.
# Codes that differ from a naive prefix match are the whole reason this map exists:
# GER->de, NED->nl, SUI->ch, KSA->sa, CRO->hr, POR->pt, RSA->za, KOR->kr,
# ALG->dz, CZE->cz, URU->uy, PAR->py, DEN-style traps avoided by being explicit.
# England/Scotland use flagcdn's GB subdivision codes.
FIFA_TO_ISO = {
    "ALG": "dz", "ARG": "ar", "AUS": "au", "AUT": "at", "BEL": "be",
    "BIH": "ba", "BRA": "br", "CAN": "ca", "CIV": "ci", "COD": "cd",
    "COL": "co", "CPV": "cv", "CRO": "hr", "CUW": "cw", "CZE": "cz",
    "ECU": "ec", "EGY": "eg", "ENG": "gb-eng", "ESP": "es", "FRA": "fr",
    "GER": "de", "GHA": "gh", "HAI": "ht", "IRN": "ir", "IRQ": "iq",
    "JOR": "jo", "JPN": "jp", "KOR": "kr", "KSA": "sa", "MAR": "ma",
    "MEX": "mx", "NED": "nl", "NOR": "no", "NZL": "nz", "PAN": "pa",
    "PAR": "py", "POR": "pt", "QAT": "qa", "RSA": "za", "SCO": "gb-sct",
    "SEN": "sn", "SUI": "ch", "SWE": "se", "TUN": "tn", "TUR": "tr",
    "URU": "uy", "USA": "us", "UZB": "uz",
}

# Kit-inspired primary/secondary colors for SPA avatars (cosmetic only).
TEAM_COLORS = {
    "ALG": ("#1f6b4a", "#ffffff"), "ARG": ("#5BA8D6", "#ffffff"),
    "AUS": ("#f6d915", "#1f3a8a"), "AUT": ("#e0202f", "#ffffff"),
    "BEL": ("#e0202f", "#f6d915"), "BIH": ("#1b2a6b", "#f6d915"),
    "BRA": ("#0a8c3a", "#f6d915"), "CAN": ("#e0202f", "#ffffff"),
    "CIV": ("#e8743b", "#0a8c3a"), "COD": ("#1f3a8a", "#e0202f"),
    "COL": ("#f6d915", "#1f3a8a"), "CPV": ("#1b4f9c", "#e0202f"),
    "CRO": ("#c60b1e", "#1f3a8a"), "CUW": ("#1b4f9c", "#f6d915"),
    "CZE": ("#e0202f", "#1b2a6b"), "ECU": ("#f6d915", "#1b2a6b"),
    "EGY": ("#e0202f", "#1a1a1a"), "ENG": ("#e0202f", "#ffffff"),
    "ESP": ("#c60b1e", "#ffc400"), "FRA": ("#1f3a8a", "#e0202f"),
    "GER": ("#1a1a1a", "#e0202f"), "GHA": ("#1a1a1a", "#f6d915"),
    "HAI": ("#1b4f9c", "#e0202f"), "IRN": ("#0a8c3a", "#e0202f"),
    "IRQ": ("#0a6b3a", "#1a1a1a"), "JPN": ("#1b2a6b", "#e0202f"),
    "JOR": ("#e0202f", "#1a1a1a"), "KOR": ("#e0202f", "#1b2a6b"),
    "KSA": ("#0a6b3a", "#ffffff"), "MAR": ("#1f6b4a", "#c1432b"),
    "MEX": ("#0a6b3a", "#c60b1e"), "NED": ("#e8743b", "#1f3a8a"),
    "NOR": ("#e0202f", "#1b2a6b"), "NZL": ("#1a1a1a", "#ffffff"),
    "PAN": ("#e0202f", "#1b2a6b"), "PAR": ("#e0202f", "#1b4f9c"),
    "POR": ("#c1432b", "#0a6b3a"), "QAT": ("#8a1538", "#ffffff"),
    "RSA": ("#0a6b3a", "#f6d915"), "SCO": ("#1b2a6b", "#ffffff"),
    "SEN": ("#0a8c3a", "#f6d915"), "SUI": ("#e0202f", "#ffffff"),
    "SWE": ("#f6d915", "#1b4f9c"), "TUN": ("#e0202f", "#ffffff"),
    "TUR": ("#e0202f", "#ffffff"), "URU": ("#5BA8D6", "#1a1a1a"),
    "USA": ("#1f3a8a", "#e0202f"), "UZB": ("#5BA8D6", "#0a8c3a"),
}

# --------------------------------------------------------------- venues ----
# openfootball "ground" string -> venue. Capacity figures are the
# FIFA-published numbers from the Wikipedia venues table (see SOURCES.md).
VENUES = {
    "att":       {"name": "AT&T Stadium",           "fifa_name": "Dallas Stadium",                "city": "Dallas (Arlington)",            "country": "USA",    "capacity": 94000, "tz": "America/Chicago"},
    "azteca":    {"name": "Estadio Azteca",          "fifa_name": "Mexico City Stadium",           "city": "Mexico City",                   "country": "Mexico", "capacity": 93000, "tz": "America/Mexico_City"},
    "metlife":   {"name": "MetLife Stadium",         "fifa_name": "New York New Jersey Stadium",   "city": "New York/New Jersey (East Rutherford)", "country": "USA", "capacity": 82500, "tz": "America/New_York"},
    "mercedes":  {"name": "Mercedes-Benz Stadium",   "fifa_name": "Atlanta Stadium",               "city": "Atlanta",                       "country": "USA",    "capacity": 75000, "tz": "America/New_York"},
    "arrowhead": {"name": "Arrowhead Stadium",       "fifa_name": "Kansas City Stadium",           "city": "Kansas City",                   "country": "USA",    "capacity": 73000, "tz": "America/Chicago"},
    "nrg":       {"name": "NRG Stadium",             "fifa_name": "Houston Stadium",               "city": "Houston",                       "country": "USA",    "capacity": 72000, "tz": "America/Chicago"},
    "levis":     {"name": "Levi's Stadium",          "fifa_name": "San Francisco Bay Area Stadium","city": "San Francisco Bay Area (Santa Clara)", "country": "USA", "capacity": 71000, "tz": "America/Los_Angeles"},
    "sofi":      {"name": "SoFi Stadium",            "fifa_name": "Los Angeles Stadium",           "city": "Los Angeles (Inglewood)",       "country": "USA",    "capacity": 70000, "tz": "America/Los_Angeles"},
    "lincoln":   {"name": "Lincoln Financial Field", "fifa_name": "Philadelphia Stadium",          "city": "Philadelphia",                  "country": "USA",    "capacity": 69000, "tz": "America/New_York"},
    "lumen":     {"name": "Lumen Field",             "fifa_name": "Seattle Stadium",               "city": "Seattle",                       "country": "USA",    "capacity": 69000, "tz": "America/Los_Angeles"},
    "gillette":  {"name": "Gillette Stadium",        "fifa_name": "Boston Stadium",                "city": "Boston (Foxborough)",           "country": "USA",    "capacity": 65000, "tz": "America/New_York"},
    "hardrock":  {"name": "Hard Rock Stadium",       "fifa_name": "Miami Stadium",                 "city": "Miami (Miami Gardens)",         "country": "USA",    "capacity": 65000, "tz": "America/New_York"},
    "bcplace":   {"name": "BC Place",                "fifa_name": "BC Place Vancouver",            "city": "Vancouver",                     "country": "Canada", "capacity": 54000, "tz": "America/Vancouver"},
    "bbva":      {"name": "Estadio BBVA",            "fifa_name": "Estadio Monterrey",             "city": "Monterrey (Guadalupe)",         "country": "Mexico", "capacity": 53500, "tz": "America/Monterrey"},
    "akron":     {"name": "Estadio Akron",           "fifa_name": "Estadio Guadalajara",           "city": "Guadalajara (Zapopan)",         "country": "Mexico", "capacity": 52000, "tz": "America/Mexico_City"},
    "bmo":       {"name": "BMO Field",               "fifa_name": "Toronto Stadium",               "city": "Toronto",                       "country": "Canada", "capacity": 45000, "tz": "America/Toronto"},
}

GROUND_TO_VENUE = {
    "Atlanta": "mercedes",
    "Boston (Foxborough)": "gillette",
    "Dallas (Arlington)": "att",
    "Guadalajara (Zapopan)": "akron",
    "Houston": "nrg",
    "Kansas City": "arrowhead",
    "Los Angeles (Inglewood)": "sofi",
    "Mexico City": "azteca",
    "Miami (Miami Gardens)": "hardrock",
    "Monterrey (Guadalupe)": "bbva",
    "New York/New Jersey (East Rutherford)": "metlife",
    "Philadelphia": "lincoln",
    "San Francisco Bay Area (Santa Clara)": "levis",
    "Seattle": "lumen",
    "Toronto": "bmo",
    "Vancouver": "bcplace",
}

ROUND_MAP = {
    "Round of 32": "r32",
    "Round of 16": "r16",
    "Quarter-final": "qf",
    "Semi-final": "sf",
    "Match for third place": "third_place",
    "Final": "final",
}


def kickoff_utc(date: str, time_str: str) -> str:
    """'2026-06-11' + '13:00 UTC-6' -> '2026-06-11T19:00:00Z'."""
    m = re.fullmatch(r"(\d{2}):(\d{2}) UTC([+-]\d+)(?::(\d{2}))?", time_str)
    if not m:
        raise ValueError(f"unparseable time: {time_str!r}")
    hh, mm, off_h = int(m.group(1)), int(m.group(2)), int(m.group(3))
    off_m = int(m.group(4) or 0)
    offset = timezone(timedelta(hours=off_h, minutes=off_m if off_h >= 0 else -off_m))
    local = datetime.fromisoformat(date).replace(hour=hh, minute=mm, tzinfo=offset)
    return local.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_slot(token: str):
    """Knockout slot token from openfootball -> slot descriptor object."""
    if re.fullmatch(r"[12][A-L]", token):
        return {"type": "group_rank", "group": token[1], "rank": int(token[0])}
    if token.startswith("3") and "/" in token:
        return {"type": "third_place_pool", "groups": token[1:].split("/")}
    m = re.fullmatch(r"W(\d+)", token)
    if m:
        return {"type": "match_winner", "match_number": int(m.group(1))}
    m = re.fullmatch(r"L(\d+)", token)
    if m:
        return {"type": "match_loser", "match_number": int(m.group(1))}
    raise ValueError(f"unrecognized slot token: {token!r}")


def build():
    raw = json.loads(RAW.read_text())
    matches_raw = raw["matches"]

    group_raw = [m for m in matches_raw if m.get("group")]
    ko_raw = [m for m in matches_raw if not m.get("group")]

    # -- teams ---------------------------------------------------------
    team_group: dict[str, str] = {}
    for m in group_raw:
        g = m["group"].replace("Group ", "")
        for name in (m["team1"], m["team2"]):
            team_group[name] = g
    unknown = set(team_group) - set(NAME_TO_FIFA)
    if unknown:
        raise SystemExit(f"team names missing from NAME_TO_FIFA: {unknown}")

    teams = []
    for name, group in sorted(team_group.items(), key=lambda kv: (kv[1], kv[0])):
        code = NAME_TO_FIFA[name]
        iso = FIFA_TO_ISO[code]
        c1, c2 = TEAM_COLORS[code]
        teams.append({
            "fifa_code": code,
            "name": name,
            "group": group,
            "iso2": iso,
            "flag_url": f"https://flagcdn.com/w80/{iso}.png",
            "flag_url_svg": f"https://flagcdn.com/{iso}.svg",
            "color_primary": c1,
            "color_secondary": c2,
            # Filled by scripts/resolve_team_ids.py (TODO: run before kickoff)
            "espn_team_id": None,
            "footballdata_team_id": None,
        })

    # -- group matches: official numbers 1-72 are chronological --------
    group_sorted = sorted(
        group_raw,
        key=lambda m: (kickoff_utc(m["date"], m["time"]), m["group"], m["team1"]),
    )
    bracket = []
    for i, m in enumerate(group_sorted, start=1):
        bracket.append({
            "match_number": i,
            "round": "group",
            "group": m["group"].replace("Group ", ""),
            "home_slot": NAME_TO_FIFA[m["team1"]],
            "away_slot": NAME_TO_FIFA[m["team2"]],
            "feeds_into": None,
            "kickoff_utc": kickoff_utc(m["date"], m["time"]),
            "venue_id": GROUND_TO_VENUE[m["ground"]],
        })

    # -- knockout matches 73-104 ----------------------------------------
    # openfootball numbers 73-102 explicitly; third place and final carry
    # no num field -> official numbers 103 / 104.
    def ko_num(m):
        if "num" in m:
            return m["num"]
        return 103 if m["round"] == "Match for third place" else 104

    ko_entries = []
    for m in sorted(ko_raw, key=ko_num):
        ko_entries.append({
            "match_number": ko_num(m),
            "round": ROUND_MAP[m["round"]],
            "group": None,
            "home_slot": parse_slot(m["team1"]),
            "away_slot": parse_slot(m["team2"]),
            "feeds_into": None,  # filled below
            "kickoff_utc": kickoff_utc(m["date"], m["time"]),
            "venue_id": GROUND_TO_VENUE[m["ground"]],
        })

    by_num = {e["match_number"]: e for e in ko_entries}
    for e in ko_entries:
        for slot in (e["home_slot"], e["away_slot"]):
            if slot["type"] == "match_winner":
                by_num[slot["match_number"]]["feeds_into"] = e["match_number"]
            elif slot["type"] == "match_loser":
                by_num[slot["match_number"]]["feeds_into_loser"] = e["match_number"]

    bracket.extend(ko_entries)

    # -- validation ------------------------------------------------------
    errs = []
    if len(bracket) != 104:
        errs.append(f"expected 104 matches, got {len(bracket)}")
    if [m["match_number"] for m in bracket] != list(range(1, 105)):
        errs.append("match numbers are not 1..104")

    for e in ko_entries:
        kinds = {e["home_slot"]["type"], e["away_slot"]["type"]}
        if e["round"] == "r32":
            if not kinds <= {"group_rank", "third_place_pool"}:
                errs.append(f"M{e['match_number']}: r32 not fed by group slots: {kinds}")
        elif e["round"] == "third_place":
            if kinds != {"match_loser"}:
                errs.append(f"M{e['match_number']}: third place must be fed by losers")
        else:
            if kinds != {"match_winner"}:
                errs.append(f"M{e['match_number']}: must be fed by two match winners")

    # single-elimination binary tree over 73..104 (third place excluded)
    final = next(e for e in ko_entries if e["round"] == "final")
    third = next(e for e in ko_entries if e["round"] == "third_place")
    if final["feeds_into"] is not None:
        errs.append("final must not feed into anything")
    fed_count: dict[int, int] = {}
    for e in ko_entries:
        if e is final or e is third:
            continue
        if e["feeds_into"] is None:
            errs.append(f"M{e['match_number']} feeds nothing")
        elif not (e["match_number"] < e["feeds_into"] <= 104):
            errs.append(f"M{e['match_number']} feeds invalid M{e['feeds_into']}")
        else:
            fed_count[e["feeds_into"]] = fed_count.get(e["feeds_into"], 0) + 1
    for e in ko_entries:
        if e["round"] in ("r16", "qf", "sf", "final") and fed_count.get(e["match_number"]) != 2:
            errs.append(f"M{e['match_number']} fed by {fed_count.get(e['match_number'], 0)} matches, want 2")
    for sf in (e for e in ko_entries if e["round"] == "sf"):
        if sf.get("feeds_into_loser") != third["match_number"]:
            errs.append(f"M{sf['match_number']}: semifinal loser must feed third place")

    if len(teams) != 48:
        errs.append(f"expected 48 teams, got {len(teams)}")
    for m in bracket:
        if m["venue_id"] not in VENUES:
            errs.append(f"M{m['match_number']}: unknown venue {m['venue_id']}")

    if errs:
        for e in errs:
            print("VALIDATION:", e, file=sys.stderr)
        raise SystemExit(1)

    # -- write -----------------------------------------------------------
    OUT.mkdir(parents=True, exist_ok=True)
    venues_out = [{"id": vid, **v} for vid, v in VENUES.items()]
    (OUT / "bracket.json").write_text(json.dumps(bracket, indent=1, ensure_ascii=False) + "\n")
    (OUT / "teams.json").write_text(json.dumps(teams, indent=1, ensure_ascii=False) + "\n")
    (OUT / "venues.json").write_text(json.dumps(venues_out, indent=1, ensure_ascii=False) + "\n")
    print(f"wrote {len(bracket)} matches, {len(teams)} teams, {len(venues_out)} venues -> {OUT}")


if __name__ == "__main__":
    build()
