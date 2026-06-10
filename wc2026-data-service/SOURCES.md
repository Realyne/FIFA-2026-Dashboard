# Data sources & mapping decisions

## bracket.json
- **Primary source:** openfootball public-domain dataset, fetched 2026-06-09 from
  https://raw.githubusercontent.com/openfootball/worldcup.json/master/2026/worldcup.json
  and committed at `data/raw/openfootball-2026.json`. It contains all 104 matches,
  knockout slot tokens (`1E`, `2A`, `3A/B/C/D/F`, `W74`, `L101`) and official match
  numbers 73–102 for the knockout rounds.
- **Match numbers 1–72 (group stage):** the raw dataset does not carry official
  numbers for group matches; we assign them chronologically (kickoff UTC, then
  group, then home team) which matches FIFA's schedule-ordered numbering. These
  numbers are this system's stable primary key; live-data mapping to ESPN events
  is done by team codes + date, never by match number, so an off-by-one against
  FIFA's printed schedule for simultaneous kickoffs would be harmless.
- **Match numbers 103/104:** the raw file omits `num` for the third-place match
  and final; official numbering continues 103 (third place, Miami) and
  104 (final, MetLife) per the FIFA match schedule.
- **Kickoff times:** converted from the dataset's local-time-with-offset strings
  (e.g. `19:00 UTC-6`) to UTC ISO 8601.
- **Validation:** the build (`scripts/build_static.py`) refuses to write output
  unless every R32 match is fed by group slots, every later knockout match by
  exactly two earlier matches, semifinal losers feed match 103, and the winner
  graph 73→104 forms a single-elimination binary tree spanning all matches.

## teams.json
- 48 teams and group assignments derived from the group matches in the raw
  dataset (12 groups × 4, verified by tests).
- **FIFA codes:** explicit `NAME_TO_FIFA` map in `scripts/build_static.py`
  (openfootball uses display names like "South Korea", "DR Congo").
- **Flags:** https://flagcdn.com via an explicit `FIFA_TO_ISO` (ISO 3166-1
  alpha-2) map — no derivation from the FIFA code. Notable divergences:
  GER→de, NED→nl, SUI→ch, KSA→sa, CRO→hr, POR→pt, RSA→za, KOR→kr, ALG→dz,
  CZE→cz, URU→uy, PAR→py, CIV→ci, COD→cd, CUW→cw, CPV→cv. England and
  Scotland use flagcdn's GB subdivision codes `gb-eng` / `gb-sct`.
- **espn_team_id:** resolved 48/48 on 2026-06-09 by `scripts/resolve_team_ids.py`
  against `site.api.espn.com/.../fifa.world/teams` with normalized-name matching
  plus a manual override map (Korea Republic/South Korea, IR Iran/Iran,
  Côte d'Ivoire/Ivory Coast, Türkiye/Turkey, Czechia, Cabo Verde, …).
- **footballdata_team_id:** left `null`; the resolver fills it when
  `FOOTBALL_DATA_TOKEN` is set (failover provider, see Phase 2).
- **color_primary/secondary:** kit-inspired colors for the SPA's initials
  avatars; cosmetic, hand-authored.

## venues.json
- The 16 stadiums, FIFA tournament names, and capacities are from the venues
  table of https://en.wikipedia.org/wiki/2026_FIFA_World_Cup (fetched
  2026-06-09; that table states capacities "based on information published by
  FIFA", e.g. AT&T 94,000 / Azteca 93,000 / MetLife 82,500 / BMO 45,000).
- Venue ids are our slugs; `GROUND_TO_VENUE` in `scripts/build_static.py` maps
  openfootball ground strings (e.g. "Dallas (Arlington)") to them.
- IANA timezones hand-assigned per host city (America/New_York, America/Chicago,
  America/Los_Angeles, America/Mexico_City, America/Monterrey, America/Toronto,
  America/Vancouver).

## Player data (Phase 3)
- Squads: Wikipedia "2026 FIFA World Cup squads" (squads final June 2026);
  parsed by `scripts/ingest_squads.py`.
- Caps / international goals / past World Cups: Wikidata SPARQL
  (https://query.wikidata.org/sparql), CC0. The SPA footer carries
  "Career data from Wikidata" attribution.
- Player photos: none hosted or hotlinked. Profile cards link out to
  fifa.com (stored in `fifa_profile_url`, falling back to a fifa.com search
  URL); the visual stays an initials/flag-color avatar.

## Live data (Phase 2)
- Primary: ESPN unofficial endpoints (`site.api.espn.com/.../fifa.world/
  scoreboard|summary`). Reverse-engineered, community-documented; parsers are
  defensive and fixture-tested, with raw payload capture via
  `scripts/capture_fixtures.py` for re-verification against the first live
  match on June 11.
- Failover: football-data.org v4, competition `WC` (livescore tier required).
