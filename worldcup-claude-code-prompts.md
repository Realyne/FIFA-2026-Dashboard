# Claude Code Prompt Pack — World Cup 2026 Live Data Service for SPA

Run these as **separate Claude Code sessions/tasks in order**. Each phase is independently testable, so you can verify before moving on. Phases 1 and 3 can be completed **before June 11** (no live data needed). Phase 2's parser verification must happen once real matches are live.

Replace anything in `<<angle brackets>>` before running.

---

## Phase 1 — Static foundation: bracket map, FIFA codes, venues

```
Create a new directory `wc2026-data-service` with a Python project (uv or pip + venv, Python 3.12).

Build the static data layer for the FIFA World Cup 2026 (June 11 – July 19, 2026, hosts: USA/Mexico/Canada, 48 teams, 12 groups of 4, top 2 per group + 8 best third-placed teams advance to a Round of 32, 104 matches total).

1. Fetch the public-domain tournament dataset from
   https://raw.githubusercontent.com/openfootball/worldcup.json/master/2026/worldcup.json
   (if the path 404s, browse the repo https://github.com/openfootball/worldcup.json for the 2026 file). Save the raw file to `data/raw/openfootball-2026.json` and commit it so we are not dependent on the remote at runtime.

2. Generate `data/static/bracket.json`: an array of all 104 matches with fields:
   - match_number (1–104, FIFA official numbering)
   - round: "group" | "r32" | "r16" | "qf" | "sf" | "third_place" | "final"
   - group (e.g. "A", null for knockouts)
   - home_slot / away_slot: for group matches the team's FIFA code; for knockout matches a slot descriptor object, e.g. {"type":"group_rank","group":"A","rank":1}, {"type":"third_place_pool","groups":["C","E","F","H"]}, or {"type":"match_winner","match_number":74} / {"type":"match_loser","match_number":...} for the third-place game
   - feeds_into: the match_number this match's winner advances to (null for the final; for semifinal losers also include feeds_into_loser pointing to the third-place match)
   - kickoff_utc (ISO 8601), venue_id
   Derive slot/progression info from the openfootball dataset where present; where the dataset is ambiguous, cross-check against the official FIFA match schedule (search the web) and add a comment in a SOURCES.md noting where each mapping came from. Validate: every r32 match must be fed by group slots, every later knockout match must be fed by exactly two earlier matches, and the graph from match 73→104 must be a valid single-elimination binary tree.

3. Generate `data/static/teams.json`: all 48 teams with
   - fifa_code (3-letter, this is the primary key for the whole system)
   - name, group
   - flag_url: use https://flagcdn.com (map FIFA code → ISO 3166-1 alpha-2; handle the special cases: England/Scotland/Wales if qualified use flagcdn's gb-eng style codes; note any team whose FIFA code differs from ISO, e.g. GER→de, NED→nl, SUI→ch, CRC→cr, KSA→sa, etc. — build an explicit fifa_to_iso map, no guessing)
   - espn_team_id and footballdata_team_id: leave as null placeholders with a TODO; add a script `scripts/resolve_team_ids.py` that fills them by calling
     ESPN: https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world/teams
     football-data.org: GET https://api.football-data.org/v4/competitions/WC/teams with header X-Auth-Token from env FOOTBALL_DATA_TOKEN (skip gracefully if env var unset)
     Match by normalized name with a manual-override map for tricky names (e.g. "Korea Republic" vs "South Korea", "IR Iran" vs "Iran", "Côte d'Ivoire" vs "Ivory Coast").

4. Generate `data/static/venues.json`: the 16 stadiums with id, name, city, country, capacity, tz (IANA timezone). Source from Wikipedia's 2026 FIFA World Cup venues table (search the web); hardcode the result, cite the page in SOURCES.md.

5. Write pytest tests: bracket graph validity, all 48 fifa_codes unique and 3 uppercase letters, every match venue_id exists in venues.json, all kickoff_utc parse and fall within 2026-06-11..2026-07-19.

Do not build any server yet. Output: the three static JSON files, the resolver script, tests passing.
```

---

## Phase 2 — Live data backend: ESPN adapter, Redis cache, SSE fan-out

```
In `wc2026-data-service`, build a FastAPI backend that serves World Cup live data to my SPA. My SPA is at <<your SPA origin, e.g. https://realyne.com>> — configure CORS for it. Deployment target is Docker behind Nginx on EC2; Redis is available at REDIS_URL.

Architecture requirements:

1. Provider adapter pattern. Define an abstract `MatchDataProvider` with methods:
   - get_scoreboard(date) -> list[MatchState]
   - get_match_detail(match_id) -> MatchDetail
   Implement `ESPNProvider` as the primary (free, unofficial) and a stub `FootballDataProvider` (football-data.org v4, competition code WC, X-Auth-Token header) as a failover that I can enable later by paying for their livescore tier. Provider selection via env var DATA_PROVIDER=espn|footballdata. All ESPN-specific JSON parsing must live inside ESPNProvider only.

2. ESPN endpoints (unofficial, no auth):
   - Scoreboard: https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world/scoreboard?dates=YYYYMMDD
   - Match summary: https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world/summary?event={espn_event_id}
   IMPORTANT: these are reverse-engineered and the soccer summary shape is community-documented, not official. Write the parsers defensively: every field access goes through safe getters, unknown shapes log a warning with the raw JSON saved to `debug/` instead of crashing, and parsers are covered by tests using fixture files. Create `scripts/capture_fixtures.py` that fetches a real scoreboard + one summary and saves them under `tests/fixtures/` — I will run this on June 11 against the first live match and we will fix the parsers against reality then. For now, build fixtures from any recent international soccer match ESPN covers (e.g. slug fifa.friendly or a recent eng.1 match) so the parser structure is real.

3. Normalized domain models (Pydantic), keyed on FIFA 3-letter codes via data/static/teams.json:
   - MatchState: match_number, espn_event_id, status ("upcoming"|"live"|"ht"|"et"|"pens"|"finished"), minute_display (string, must preserve stoppage like "90+3"), home/away {fifa_code, score, pen_score|null}, kickoff_utc, venue_id
   - MatchDetail: MatchState + events[] (minute, type goal|own_goal|pen_goal|yellow|red|sub, player_name, player_espn_id, fifa_code of team, sub_off_player for subs, assist_name|null) + lineups (per team: formation|null, starters[] and bench[] with shirt_number, name, position, player_espn_id) + stats (possession_pct, shots, shots_on_target, corners, fouls, offsides — all nullable)

4. Polling scheduler (asyncio task in the app, or APScheduler):
   - Reads bracket.json kickoff times. Defines a "live window" = 15 min before kickoff until status finished (+10 min grace).
   - Inside a live window: poll scoreboard every 20s; for each live match poll its summary every 30s. Outside any window: poll scoreboard once every 30 min only.
   - Be a polite client: single shared httpx.AsyncClient, User-Agent set, timeout 10s, exponential backoff on errors, circuit breaker (after 5 consecutive failures, back off 5 min and set a degraded flag).
   - Write every normalized result to Redis: keys wc:scoreboard (TTL 60s), wc:match:{match_number} (TTL 90s), wc:bracket_resolved (TTL 5 min — bracket.json with slots resolved to actual FIFA codes as results come in). Also publish a Redis pub/sub message on channel wc:updates whenever a watched value changes (diff before publish).

5. Public API for the SPA (FastAPI, all responses served FROM REDIS/static only — handlers never call ESPN directly):
   - GET /api/wc/bracket            -> resolved bracket (static + live resolution)
   - GET /api/wc/matches?date=      -> scoreboard
   - GET /api/wc/matches/{match_number} -> MatchDetail
   - GET /api/wc/teams, /api/wc/venues  -> static
   - GET /api/wc/stream             -> SSE endpoint. Subscribes to Redis pub/sub wc:updates and forwards JSON patches (match_number + changed fields). Include a 25s keepalive comment frame. Document the event format in README for my SPA's EventSource consumer. My UI re-renders every second client-side; it only needs data ticks every 20–30s.
   - ETag/Cache-Control headers on the GET endpoints (short max-age matching Redis TTLs).

6. Ops: Dockerfile (multi-stage, uvicorn), docker-compose.yml with redis for local dev, .env.example (REDIS_URL, DATA_PROVIDER, FOOTBALL_DATA_TOKEN optional, ALLOWED_ORIGINS), GET /healthz reporting provider status + last successful poll timestamp + degraded flag, structured logging. README section: Nginx location block for proxying /api/wc/ including SSE config (proxy_buffering off, proxy_read_timeout 1h).

7. Tests: parser tests on fixtures (incl. a "90+3" minute case, a shootout case, missing-lineups case), scheduler window logic tests (freeze time), API tests with fakeredis.
```

---

## Phase 3 — Player directory: Wikidata caps/goals → SQLite, FIFA profile links

```
In `wc2026-data-service`, add the player directory subsystem. Storage: SQLite (file db/players.sqlite) used as a persistent cache — Wikidata is queried offline/batch, NEVER per-request.

1. SQLite schema (use sqlite3 stdlib or SQLAlchemy, your call, but keep it simple):
   players(
     player_id TEXT PRIMARY KEY,        -- our stable id: slugified "fifa_code-shirtnumber-lastname" fallback to wikidata qid
     wikidata_qid TEXT UNIQUE NULL,
     espn_id TEXT NULL,
     name TEXT, fifa_code TEXT,         -- national team
     dob TEXT, position TEXT, club TEXT, club_country TEXT,
     caps INTEGER NULL, intl_goals INTEGER NULL,
     past_world_cups TEXT NULL,         -- JSON array of years, e.g. [2018, 2022]
     fifa_profile_url TEXT NULL,        -- outbound link to fifa.com, see step 4
     fetched_at TEXT, source TEXT
   )
   plus a meta(key, value) table for sync bookkeeping.

2. Squad ingestion: script `scripts/ingest_squads.py` that loads the 48 squads. Primary source: the openfootball 2026 dataset squads if present; otherwise parse the Wikipedia page "2026 FIFA World Cup squads" (search the web for it; squads are finalized early June 2026). Populate name, fifa_code, shirt number, position, club, dob where available.

3. Wikidata enrichment: script `scripts/enrich_wikidata.py`:
   - For each player, resolve a Wikidata QID: SPARQL against https://query.wikidata.org/sparql searching by label + P54 (member of sports team = the national team) to disambiguate same-name players. Batch queries (VALUES blocks of ~50), sleep between requests, set a descriptive User-Agent per Wikimedia policy, retry on 429.
   - Pull: P569 date of birth (sanity-check against squad dob), caps and goals for the NATIONAL TEAM specifically (qualifiers P1350 matches played / P1351 goals scored on the P54 statement for the national team — be careful to take the national-team statement, not club statements), and participation in past World Cups (P1344 participant-in pointing to 2014/2018/2022 World Cup items, where present).
   - Write results to SQLite with fetched_at. Players with no QID found: leave nulls, log to a review file. Treat Wikidata data as CC0; still add an attribution line in the SPA footer ("Career data from Wikidata").
   - Idempotent + resumable: skip rows fetched within REFRESH_DAYS (default 7). Caps barely change mid-tournament; a weekly re-run is enough.

4. FIFA profile links (photos decision): we do NOT host or hotlink any player photos. Instead each profile card links out to the player's page on FIFA's official site. Investigate the current URL pattern on https://www.fifa.com (likely a player or tournament squad page; inspect a few examples by browsing). If stable per-player URLs exist, store them in fifa_profile_url; if the pattern is unreliable, fall back to storing a fifa.com site-search URL of the form https://www.fifa.com/search?q={urlencoded player name}. Either way it's an outbound <a> link only — that keeps us 100% clear of image licensing. In the SPA the visual stays our initials/flag-color avatar.

5. API endpoints (read from SQLite, cache hot responses in Redis TTL 1h):
   - GET /api/wc/players?team={fifa_code}   -> squad list (directory page)
   - GET /api/wc/players/{player_id}        -> full profile incl. caps, intl_goals, past_world_cups, fifa_profile_url
   - Join point: MatchDetail lineups include player_espn_id; add a best-effort name+team matcher script `scripts/link_espn_ids.py` that fills players.espn_id after lineups appear in real matches, so the SPA can deep-link from a lineup row to a profile.

6. Tests: schema migration runs clean, enrichment is idempotent, a mocked SPARQL response parses into the right columns, national-team caps are picked over club stats in a crafted ambiguous fixture.
```

---

## Phase 4 — SPA integration contract (run inside your SPA repo)

```
My backend (FastAPI on <<backend base URL>>) exposes the World Cup API documented in <<paste the README API section from Phase 2/3>>. In this SPA (<<your framework, e.g. React 18 + Vite + TS>>):

1. Create a typed API client module for all /api/wc/* endpoints (generate TS types matching the Pydantic models).
2. Create a `useWorldCupLive()` hook: opens one EventSource to /api/wc/stream, maintains a normalized match store (by match_number), applies incoming JSON patches, exposes per-match selectors. Reconnect with backoff on drop; on reconnect, refetch /api/wc/matches for the day to resync. The existing 1s render loop reads from this store; do not add any client-side polling of the backend beyond the SSE + resync.
3. Bracket graph: consume /api/wc/bracket — nodes are matches, edges from feeds_into. Unresolved slots render the slot descriptor (e.g. "Winner M74", "1st Group A").
4. Player cards: avatar = initials over team flag color, name links to fifa_profile_url in a new tab with rel="noopener noreferrer". Footer attribution: "Career data from Wikidata".
5. Status badge mapping: upcoming/live/ht/et/pens/finished; minute_display rendered verbatim (it already contains "90+3" formatting).
```

---

## Run-order checklist

- [ ] **Now:** Phase 1 (static), Phase 3 steps 1–4 (squads + Wikidata can run as soon as squads are final), Phase 2 build with placeholder fixtures
- [ ] **June 11, first match:** run `scripts/capture_fixtures.py` against the live game → fix ESPN parsers against real shapes → run `scripts/link_espn_ids.py` after first lineups publish
- [ ] **Failover insurance:** if ESPN breaks mid-tournament, buy football-data.org livescore tier (€12/mo), set FOOTBALL_DATA_TOKEN + DATA_PROVIDER=footballdata, finish the stub adapter — nothing else changes
