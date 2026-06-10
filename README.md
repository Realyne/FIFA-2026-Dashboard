# World Cup 2026 Live Dashboard · Realyne 2026

Public, live-data dashboard for the FIFA World Cup 2026 (June 11 – July 19,
2026 · USA/Canada/Mexico · 48 teams · 104 matches). Built for
**[Realyne](https://realyne.com) 2026** — deployed at `wc2026.realyne.com`.

Two parts:

| Part | What | Stack |
|---|---|---|
| `/` (this dir) | SPA — landing, groups, bracket, match pages, 1,246-player directory | no-build React 18 (CDN UMD + Babel standalone), hash routing |
| `wc2026-data-service/` | Live data backend — ESPN polling, Redis cache, SSE fan-out, player DB | Python 3.12, FastAPI, Redis, SQLite |

The SPA never talks to ESPN/Wikidata directly: it loads `/api/wc/*` once,
then receives 20–30s data ticks over a single SSE connection
(`/api/wc/stream`). All data sources and licensing decisions are documented
in `wc2026-data-service/SOURCES.md`; the API contract is in
`wc2026-data-service/README.md`.

## Run locally

```bash
# backend (in-process fake Redis, real ESPN polling)
cd wc2026-data-service
uv venv && uv pip install -e ".[dev]"
REDIS_URL=fakeredis:// .venv/bin/uvicorn wc2026.main:app --port 8000

# frontend
cd ..
python3 -m http.server 5173
open http://localhost:5173
```

The SPA auto-targets `http://<host>:8000` when served from a dev port; set
`window.WC_API_BASE` before `data.js` loads to override.

## Deploy (realyne-cloud + Nginx)

One command from your laptop (SSH alias `realyne-cloud` must exist):

```bash
./deploy/deploy.sh
```

This rsyncs the SPA + `wc2026-data-service`, builds Docker on the host,
and installs an Nginx site. Defaults:

| Setting | Value |
|---|---|
| Host | `realyne-cloud` (`HOST=…`) |
| Domain | `wc2026.realyne.com` (`DOMAIN=…`) |
| API port | `127.0.0.1:8100` (`API_PORT=…`) — Nginx proxies `/api/wc/` |
| SPA root | `/var/www/wc2026-dashboard/www` (Nginx can't read `~/…`) |

Point DNS at the server, then enable TLS:

```bash
./deploy/deploy.sh --ssl
```

Manual / other hosts: `cd wc2026-data-service && docker compose up --build -d`
(API on :8000 + Redis). Serve this directory's static files from Nginx and
proxy `/api/wc/` using the location blocks in `wc2026-data-service/README.md`
(SSE needs `proxy_buffering off` + long `proxy_read_timeout`). Same-origin
means no CORS config needed; otherwise set `ALLOWED_ORIGINS`.

### Before kickoff (June 11, 19:00 UTC)

- [ ] During MEX–RSA: `python scripts/capture_fixtures.py --league fifa.world`
      then `pytest tests/test_espn_parser.py` — fix parser drift against the
      first real live payloads (`debug/` collects unknown shapes).
- [ ] After first lineups: `python scripts/link_espn_ids.py` (joins ESPN
      lineup ids → player profiles for lineup→profile deep links).
- [ ] Weekly: `python scripts/enrich_wikidata.py` (refreshes caps/goals).
- [ ] If ESPN breaks: buy football-data.org livescore (~€12/mo), set
      `FOOTBALL_DATA_TOKEN` + `DATA_PROVIDER=footballdata`, restart.
