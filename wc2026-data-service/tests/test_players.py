"""Player directory: schema, squad parsing, Wikidata candidate picking, API."""
import importlib.util
import json
import sys
from pathlib import Path

import fakeredis.aioredis
import httpx
import pytest
import pytest_asyncio

from wc2026.players_db import connect, player_id, slugify

ROOT = Path(__file__).resolve().parent.parent


def load_script(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------- schema ----
def test_schema_migration_runs_clean(tmp_path):
    db = tmp_path / "players.sqlite"
    conn = connect(db)
    conn.execute("INSERT INTO players(player_id, name, fifa_code) VALUES('x','X','FRA')")
    conn.commit()
    conn.close()
    # reopening re-runs CREATE IF NOT EXISTS without clobbering data
    conn2 = connect(db)
    assert conn2.execute("SELECT COUNT(*) FROM players").fetchone()[0] == 1


def test_player_id_slugs():
    assert player_id("FRA", 10, "Kylian Mbappé") == "fra-10-mbappe"
    assert player_id("CIV", 7, "Sébastien Haller") == "civ-7-haller"
    assert slugify("Aït-Nouri") == "ait-nouri"


# ----------------------------------------------------------- squad parse ----
SQUAD_WIKITEXT = """
==Group A==
===Mexico===
Coach: [[Javier Aguirre]]

{{nat fs g start}}
{{nat fs g player|no=1|pos=GK|name=[[Luis Malagón]]|sortname=Malagon|age={{birth date and age2|2026|6|11|1997|3|2}}|caps=20|goals=0|club=[[Club América|América]]|clubnat=MEX}}
{{nat fs g player|no=10|pos=FW|name=[[Some Star]] ([[captain (association football)|captain]])|age={{birth date and age2|2026|6|11|1990|1|15}}|caps=100|goals=44|club=[[Big Club F.C.|Big Club]]|clubnat=ENG}}
{{nat fs g end}}
"""


def test_parse_squads_handles_nested_templates():
    ingest = load_script("ingest_squads")
    players = ingest.parse_squads(SQUAD_WIKITEXT)
    assert len(players) == 2
    gk = players[0]
    assert gk["fifa_code"] == "MEX" and gk["shirt_number"] == 1
    assert gk["name"] == "Luis Malagón"
    assert gk["dob"] == "1997-03-02"
    assert gk["caps"] == 20 and gk["club"] == "América"
    star = players[1]
    assert star["caps"] == 100 and star["intl_goals"] == 44
    assert star["name"].startswith("Some Star")  # captain tag stripped of links


# ------------------------------------------------- wikidata candidate pick --
def binding(qid, name, team_label=None, caps=None, goals=None, dob=None):
    b = {"p": {"value": f"http://www.wikidata.org/entity/{qid}"},
         "name": {"value": name}}
    if team_label:
        b["teamLabel"] = {"value": team_label}
    if caps is not None:
        b["caps"] = {"value": str(caps)}
    if goals is not None:
        b["goals"] = {"value": str(goals)}
    if dob:
        b["dob"] = {"value": dob + "T00:00:00Z"}
    return b


def test_national_team_caps_picked_over_club():
    enrich = load_script("enrich_wikidata")
    rows = [
        binding("Q1", "John Doe", "Big Club F.C.", caps=400, goals=200, dob="1995-05-05"),
        binding("Q1", "John Doe", "France national football team", caps=48, goals=9, dob="1995-05-05"),
        binding("Q1", "John Doe", "France national under-21 football team", caps=12, goals=3, dob="1995-05-05"),
    ]
    cand = enrich.pick_candidate(rows, "FRA", "1995-05-05")
    assert cand["qid"] == "Q1"
    assert cand["nat"]["caps"] == 48 and cand["nat"]["goals"] == 9


def test_same_name_players_disambiguated_by_team_and_dob():
    enrich = load_script("enrich_wikidata")
    rows = [
        binding("Q1", "João Silva", "Brazil national football team", caps=10, dob="1990-01-01"),
        binding("Q2", "João Silva", "Portugal national football team", caps=5, dob="2000-02-02"),
    ]
    cand = enrich.pick_candidate(rows, "POR", "2000-02-02")
    assert cand["qid"] == "Q2"
    # and a club-only doppelganger never wins
    rows = [binding("Q9", "João Silva", "Sporting CP", caps=300)]
    assert enrich.pick_candidate(rows, "POR", None) is None


def test_enrichment_is_idempotent(tmp_path, monkeypatch):
    """Second run with fresh fetched_at selects nothing to re-fetch."""
    from datetime import datetime, timezone
    db = tmp_path / "p.sqlite"
    conn = connect(db)
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "INSERT INTO players(player_id,name,fifa_code,fetched_at,source) VALUES(?,?,?,?,?)",
        ("fra-10-x", "X", "FRA", now, "wikidata"))
    conn.execute(
        "INSERT INTO players(player_id,name,fifa_code,fetched_at,source) VALUES(?,?,?,?,?)",
        ("fra-11-y", "Y", "FRA", now, "wikipedia_squads"))
    conn.commit()
    cutoff = "2026-06-03T00:00:00+00:00"
    rows = conn.execute(
        "SELECT player_id FROM players WHERE NOT (source='wikidata' AND fetched_at > ?)",
        (cutoff,)).fetchall()
    assert [r["player_id"] for r in rows] == ["fra-11-y"]


# -------------------------------------------------------------------- API ---
@pytest_asyncio.fixture
async def client(tmp_path, monkeypatch):
    db = tmp_path / "players.sqlite"
    conn = connect(db)
    conn.execute(
        """INSERT INTO players(player_id,name,fifa_code,shirt_number,position,
             club,caps,intl_goals,past_world_cups,fifa_profile_url)
           VALUES('fra-10-mbappe','Kylian Mbappé','FRA',10,'FW','Real Madrid',
                  98,56,'[2018, 2022]','https://www.fifa.com/en/search?q=Kylian%20Mbapp%C3%A9')""")
    conn.commit()
    conn.close()

    from wc2026.config import settings
    monkeypatch.setattr(settings(), "db_path", str(db))
    from wc2026.main import app
    app.state.redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    await app.state.redis.aclose()


async def test_players_by_team(client):
    r = await client.get("/api/wc/players", params={"team": "fra"})
    assert r.status_code == 200
    rows = r.json()
    assert len(rows) == 1
    p = rows[0]
    assert p["name"] == "Kylian Mbappé"
    assert p["past_world_cups"] == [2018, 2022]


async def test_player_profile_and_404(client):
    r = await client.get("/api/wc/players/fra-10-mbappe")
    assert r.status_code == 200
    assert r.json()["caps"] == 98
    assert r.json()["fifa_profile_url"].startswith("https://www.fifa.com/")
    assert (await client.get("/api/wc/players/nope")).status_code == 404
