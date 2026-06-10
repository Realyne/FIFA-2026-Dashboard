"""SQLite player directory: persistent cache, written by batch scripts,
read by the API. Wikidata/Wikipedia are NEVER queried per-request."""
from __future__ import annotations

import re
import sqlite3
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = ROOT / "db" / "players.sqlite"

SCHEMA = """
CREATE TABLE IF NOT EXISTS players(
  player_id TEXT PRIMARY KEY,          -- "fra-10-mbappe" (fallback: wikidata qid)
  wikidata_qid TEXT UNIQUE,
  espn_id TEXT,
  name TEXT NOT NULL,
  fifa_code TEXT NOT NULL,             -- national team
  shirt_number INTEGER,
  dob TEXT,
  position TEXT,                       -- GK | DF | MF | FW
  club TEXT,
  club_country TEXT,
  caps INTEGER,
  intl_goals INTEGER,
  past_world_cups TEXT,                -- JSON array of years, e.g. [2018, 2022]
  fifa_profile_url TEXT,               -- outbound link to fifa.com
  fetched_at TEXT,
  source TEXT
);
CREATE TABLE IF NOT EXISTS meta(
  key TEXT PRIMARY KEY,
  value TEXT
);
CREATE INDEX IF NOT EXISTS idx_players_team ON players(fifa_code);
"""


def connect(path: str | Path = DEFAULT_DB) -> sqlite3.Connection:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(p)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def slugify(s: str) -> str:
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")
    return s


def player_id(fifa_code: str, shirt_number: int | None, name: str) -> str:
    last = name.split()[-1] if name.split() else name
    return f"{fifa_code.lower()}-{shirt_number or 0}-{slugify(last)}"
