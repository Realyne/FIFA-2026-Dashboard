# wc2026-data-service

Live data backend for the World Cup 2026 dashboard SPA. Polls ESPN's
unofficial API (football-data.org as paid failover), normalizes everything to
FIFA 3-letter codes and official match numbers 1–104, caches in Redis, and
fans out updates to browsers over SSE.

```
ESPN ──poll──> Poller ──normalize──> Redis (states/cache, pub/sub wc:updates)
                                        │
SPA  <──ETag'd JSON── FastAPI handlers ─┘   (handlers never call ESPN)
SPA  <──SSE patches── /api/wc/stream <── Redis pub/sub
```

## Quick start (local)

```bash
uv venv && uv pip install -e ".[dev]"
docker compose up redis -d          # or any Redis on localhost:6379
uvicorn wc2026.main:app --reload    # API + poller on :8000
pytest                              # 54 tests, no network needed
```

Full stack via Docker: `docker compose up --build`.

## Static data pipeline (Phase 1)

- `scripts/build_static.py` — regenerates `data/static/{bracket,teams,venues}.json`
  from `data/raw/openfootball-2026.json` (committed; see SOURCES.md). Validates
  the knockout graph before writing.
- `scripts/resolve_team_ids.py` — fills `espn_team_id` (done, 48/48) and
  `footballdata_team_id` (needs `FOOTBALL_DATA_TOKEN`).

## API

All endpoints are GET, read from Redis/static only, send `ETag` +
`Cache-Control` and support `If-None-Match` → 304.

| Endpoint | Payload | max-age |
|---|---|---|
| `/api/wc/bracket` | all 104 matches with `home`/`away` `{fifa_code, label, provisional, score, pen_score}` resolved live (slots like “Winner M101” / “1st Group A” until known), `status`, `minute_display` | 30s |
| `/api/wc/standings` | `{A..L: {complete, rows:[{fifa_code, played, won, drawn, lost, gf, ga, gd, points}]}}` | 30s |
| `/api/wc/matches?date=YYYY-MM-DD` | scoreboard of `MatchState` (UTC date filter; omit for all) | 20s |
| `/api/wc/matches/{match_number}` | `MatchDetail`: state + `events[]` + `lineups{home,away}` + `stats{home,away}` | 30s |
| `/api/wc/teams` | 48 teams: `fifa_code`, `name`, `group`, `flag_url` (flagcdn), colors, provider ids | 1h |
| `/api/wc/venues` | 16 stadiums: id, name, FIFA name, city, country, capacity, IANA tz | 1h |
| `/api/wc/players?team=FRA` | squad list (Phase 3) | 1h |
| `/api/wc/players/{player_id}` | profile incl. caps, intl goals, past World Cups, fifa.com link | 1h |
| `/api/wc/stream` | SSE, see below | — |
| `/healthz` | `{ok, provider, degraded, last_poll_ok, redis}` | — |

### MatchState / MatchDetail

```jsonc
{
  "match_number": 1,            // 1..104, our primary key
  "espn_event_id": "760415",
  "status": "live",             // upcoming | live | ht | et | pens | finished
  "minute_display": "90+3",     // stoppage preserved; render verbatim
  "home": {"fifa_code": "MEX", "score": 1, "pen_score": null},
  "away": {"fifa_code": "RSA", "score": 0, "pen_score": null},
  "kickoff_utc": "2026-06-11T19:00:00Z",
  "venue_id": "azteca", "round": "group", "group": "A",
  // MatchDetail adds:
  "events":  [{"minute": "28", "type": "goal", "player_name": "…",
               "player_espn_id": "…", "fifa_code": "MEX",
               "assist_name": null, "sub_off_player": null}],
  "lineups": {"home": {"formation": "4-2-3-1",
                       "starters": [{"shirt_number": 1, "name": "…",
                                     "position": "G", "player_espn_id": "…"}],
                       "bench": []}},
  "stats":   {"home": {"possession_pct": 65.7, "shots": 27,
                       "shots_on_target": 12, "corners": 14,
                       "fouls": 9, "offsides": 2}}
}
```

### SSE stream (`/api/wc/stream`)

`text/event-stream`; a comment keepalive frame (`: keepalive`) every 25s.
Each event is one JSON object on a `data:` line:

```jsonc
{"type": "match", "match_number": 1,
 "changed": {"status": "live", "minute_display": "12"},  // diffed fields only
 "state": { /* full MatchState, authoritative */ }}

{"type": "bracket"}   // bracket resolution changed -> refetch /api/wc/bracket
```

EventSource consumer contract: apply `state` into a store keyed by
`match_number`; on `{"type":"bracket"}` refetch the bracket; on connection
drop, reconnect with backoff and refetch `/api/wc/matches` for the current
day to resync. Data ticks arrive every 20–30s during live windows — the SPA's
1s render loop should read from its local store, never poll the backend.

## Polling behavior

- Live window = kickoff−15min → status `finished` (+10min grace), hard cap
  kickoff+4h. Inside any window: scoreboard every 20s, summary per live match
  every 30s. Outside: scoreboard every 30min (and it wakes for the next window).
- Single shared `httpx.AsyncClient`, descriptive User-Agent, 10s timeout,
  exponential backoff, circuit breaker: 5 consecutive failures → 5 min pause +
  `degraded: true` on `/healthz`.
- Unknown ESPN shapes never crash the poller: payloads are dumped to `debug/`
  with a warning and the field comes back null.

## Deployment (Docker behind Nginx on EC2)

`docker compose up --build -d` then proxy through Nginx:

```nginx
# /api/wc/ -> uvicorn (incl. SSE)
location /api/wc/ {
    proxy_pass http://127.0.0.1:8000;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}

# SSE endpoint needs buffering off and a long read timeout
location /api/wc/stream {
    proxy_pass http://127.0.0.1:8000;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header Connection "";
    proxy_buffering off;
    proxy_cache off;
    proxy_read_timeout 1h;
    chunked_transfer_encoding off;
}

location /healthz { proxy_pass http://127.0.0.1:8000; }
```

## June 11 checklist (first live match, 19:00Z)

1. `python scripts/capture_fixtures.py --league fifa.world` during MEX–RSA →
   real live fixtures land in `tests/fixtures/`.
2. `pytest tests/test_espn_parser.py` — fix `ESPNProvider` against any drift
   (check `debug/` for dumped unknown shapes).
3. After lineups publish: `python scripts/link_espn_ids.py` to join lineup
   `player_espn_id`s to the player directory.

## Failover insurance

If ESPN breaks mid-tournament: buy football-data.org livescore tier (~€12/mo),
set `FOOTBALL_DATA_TOKEN`, run `scripts/resolve_team_ids.py`, set
`DATA_PROVIDER=footballdata`, restart. Scoreboard/score flow continues
(events/lineups degrade gracefully); nothing else changes.

## Player directory (Phase 3)

- `scripts/ingest_squads.py` — 48 squads from Wikipedia "2026 FIFA World Cup
  squads" into SQLite (`db/players.sqlite`).
- `scripts/enrich_wikidata.py` — batch SPARQL: QIDs, DOB, national-team caps
  and goals, past World Cups. Idempotent; refreshes rows older than
  `REFRESH_DAYS` (default 7). Wikidata is CC0; the SPA shows
  "Career data from Wikidata".
- `scripts/link_espn_ids.py` — best-effort name+team join of ESPN lineup ids.
- No player photos are hosted or hotlinked: cards show initials avatars and
  link out to `fifa_profile_url` (fifa.com search URL).
