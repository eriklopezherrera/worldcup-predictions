# Data Sync Worker — Fixtures & Scores

## Overview
A separate Lambda function (not the API Lambda) that runs on a schedule via EventBridge.
It fetches match data from **api-football.com** and keeps the local DB in sync.

Lambda entry point: `backend/app/workers/sync_worker.handler`

### Module Structure
The implementation is split across four files under `backend/app/workers/`:

| File | Purpose |
|---|---|
| `sync_worker.py` | Lambda handler — routes to fixture or score sync |
| `football_api_client.py` | Async `httpx` client, `STATUS_MAP`, exponential backoff |
| `fixture_sync.py` | `sync_fixtures(db, api_client, league_id, season)` |
| `score_sync.py` | `sync_scores(db, api_client, league_ids, seasons)` |
| `seed.py` | Dev-only: seeds DB with hardcoded WC 2026 fixture data |

---

## External API: api-football.com

### Base URL
`https://v3.football.api-sports.io`

### Auth Header
`x-apisports-key: <FOOTBALL_API_KEY>` (stored in AWS Secrets Manager)

### Key Endpoints Used

#### Get Fixtures for a League/Season
```
GET /fixtures?league={league_id}&season={year}
```
Returns all fixtures including status, scores, team IDs, venue, date.

**FIFA World Cup 2026 league ID:** `1` (FIFA World Cup on api-football)

#### Get Live/Recent Scores
```
GET /fixtures?league=1&season=2026&status=FT    # finished today
GET /fixtures?league=1&season=2026&live=all     # currently live
```

#### Get Teams for League
```
GET /teams?league=1&season=2026
```

---

## Sync Strategy

### Schedule (EventBridge cron rules)

| Phase | Schedule | What it does |
|---|---|---|
| Pre-tournament | Daily at 06:00 UTC | Sync all fixtures (teams, dates, venues) |
| During tournament | Every 3 minutes | Sync live scores + update finished matches |
| Post-tournament | Disabled | Nothing |

The CDK `sync_stack.py` creates two EventBridge rules pointing at the same Lambda, differentiated by the event payload `{"sync_type": "fixtures"}` or `{"sync_type": "scores"}`.

In practice, the same function handles both — the schedule just determines frequency.

### Lambda Entry Point
```python
# backend/app/workers/sync_worker.py

def handler(event, context):
    """EventBridge rule triggers this with payload: {"sync_type": "fixtures"|"scores"}"""
    sync_type = event.get("sync_type", "scores")

    if sync_type == "fixtures":
        asyncio.run(_run_fixture_sync())   # creates DB session + API client, loops over league_ids × seasons
    elif sync_type == "scores":
        asyncio.run(_run_score_sync())
    else:
        return {"status": "error", "reason": f"Unknown sync_type: {sync_type!r}"}

    return {"status": "ok", "sync_type": sync_type}
```

The private helpers `_run_fixture_sync()` / `_run_score_sync()` instantiate `FootballApiClient` and
`AsyncSessionLocal` as context managers, then call the functions in `fixture_sync.py` / `score_sync.py`.

---

## `sync_fixtures()` Logic

Signature: `sync_fixtures(db: AsyncSession, api_client: FootballApiClient, league_id: int, season: int) -> dict`
Defined in: `backend/app/workers/fixture_sync.py`

1. Look up the `Tournament` row by `external_id == league_id` and `season == str(season)` — returns an error dict if not found (the tournament must be pre-created via seed or manual insert)
2. Call `api_client.get_teams(league_id, season)` → upsert each into `teams` via `pg_insert(...).on_conflict_do_update(index_elements=["external_id"])`; re-fetch all IDs in one bulk query to build an `external_id → UUID` map
3. Call `api_client.get_fixtures(league_id, season)` → upsert each into `matches` via `on_conflict_do_update(index_elements=["external_id"])`, resolving `home_team_id`/`away_team_id` from the team map
   - `stage` and `match_day` resolved by `_map_stage(round_name)` (see Stage Mapping below)
   - `status` mapped via `STATUS_MAP` (see below)
4. Upsert `tournament_teams` rows for all synced teams via `on_conflict_do_nothing()`
5. Return `{"fixtures": N, "teams": N}`

### Stage Mapping (`_map_stage`)
Defined in `fixture_sync.py`. Maps the api-football `league.round` string to our `stage` enum and `match_day` integer:

| API round string | stage | match_day |
|---|---|---|
| `"Group Stage - N"` | `group_stage` | N (integer) |
| `"Round of 16"` | `round_of_16` | `None` |
| `"Quarter-finals"` | `quarter_final` | `None` |
| `"Semi-finals"` | `semi_final` | `None` |
| `"3rd Place Final"` | `third_place` | `None` |
| `"Final"` | `final` | `None` |

### API Status Mapping (`STATUS_MAP`)
Defined in `backend/app/workers/football_api_client.py` and imported wherever needed.

```python
STATUS_MAP = {
    "NS": "scheduled",    # Not Started
    "1H": "live",
    "HT": "live",
    "2H": "live",
    "ET": "live",
    "BT": "live",
    "P": "live",          # Penalties in progress
    "FT": "finished",
    "AET": "finished",    # After Extra Time
    "PEN": "finished",    # After Penalties
    "PST": "postponed",
    "CANC": "cancelled",
    "SUSP": "cancelled",
}
```

---

## `sync_scores()` Logic

Signature: `sync_scores(db: AsyncSession, api_client: FootballApiClient, league_ids: list[int], seasons: list[int]) -> dict`
Defined in: `backend/app/workers/score_sync.py`

1. For each `(league_id, season)` pair, fetch:
   - `api_client.get_fixtures(league_id, season, status="FT")` — all finished matches (no date filter; intentionally broad so the worker catches up if it was down)
   - `api_client.get_live_fixtures(league_id, season)` — currently live matches
   - Deduplicate by `fixture.id` (live matches may overlap with FT)
2. Bulk-load all matching `Match` rows from the DB in one query (`external_id.in_(...)`)
3. For each match, update `home_score`, `away_score`, `home_score_ht`, `away_score_ht`, `status` via ORM
4. For `status == "finished"` matches with a non-null score:
   - Query predictions where `scored_at IS NULL`
   - Call `scoring_service.compute_points()` → set `points_result`, `points_exact`, `scored_at`
   - Track match ID in `scored_match_ids`
5. After commit, find all `(party_id, tournament_id)` pairs where any member had predictions on scored matches, then call `leaderboard_service.recompute_party_leaderboard(db, party_id, tournament_id)` for each
6. Return `{"scored_matches": N}`

**Note:** Redis cache invalidation (originally listed as step 4) is **not yet implemented** — the current leaderboard implementation stores snapshots in the `leaderboard_snapshots` table and does not use Redis for leaderboard caching. This step should be added if Redis-backed caching is introduced later.

---

## Leaderboard Recomputation

**This logic is already implemented** in `backend/app/services/leaderboard_service.py` as
`recompute_party_leaderboard(db, party_id, tournament_id)`.
The sync worker must call that function — do **not** duplicate the SQL inline.

```python
# Inside sync_scores(), after scoring all predictions for a batch of matches:
from app.services.leaderboard_service import recompute_party_leaderboard

for party_id in affected_party_ids:
    await recompute_party_leaderboard(db, party_id, tournament_id)
```

The function runs the following upsert (shown here for reference only):
```sql
-- Implemented in leaderboard_service.recompute_party_leaderboard
INSERT INTO leaderboard_snapshots (party_id, user_id, tournament_id, total_points, exact_scores, predictions_made, rank, computed_at)
SELECT 
    pm.party_id,
    p.user_id,
    m.tournament_id,
    COALESCE(SUM(p.total_points), 0) AS total_points,
    COALESCE(SUM(CASE WHEN p.points_exact > 0 THEN 1 ELSE 0 END), 0) AS exact_scores,
    COUNT(p.id) AS predictions_made,
    RANK() OVER (PARTITION BY pm.party_id ORDER BY SUM(p.total_points) DESC, SUM(CASE WHEN p.points_exact > 0 THEN 1 ELSE 0 END) DESC) AS rank,
    now() AS computed_at
FROM party_members pm
JOIN predictions p ON p.user_id = pm.user_id
JOIN matches m ON m.id = p.match_id
WHERE pm.party_id = :party_id
  AND m.tournament_id = :tournament_id
  AND p.scored_at IS NOT NULL
GROUP BY pm.party_id, p.user_id, m.tournament_id
ON CONFLICT (party_id, user_id, tournament_id)
DO UPDATE SET
    total_points = EXCLUDED.total_points,
    exact_scores = EXCLUDED.exact_scores,
    predictions_made = EXCLUDED.predictions_made,
    rank = EXCLUDED.rank,
    computed_at = EXCLUDED.computed_at;
```

Note: the original spec-level SQL filtered by `tournament_id` only (all parties). The implemented version adds a `party_id` filter so each party can be recomputed independently — this is the correct call pattern for the sync worker.

---

## Rate Limiting & Error Handling

- api-football free tier: 100 requests/day. Pro tier: varies by plan.
- All API calls wrapped in exponential backoff (max 3 retries, starting at 1s)
- Log all sync runs to CloudWatch Logs with structured JSON
- If API returns non-2xx or rate limit (429), log error and exit cleanly (EventBridge will retry on next schedule)
- Never fail silently — always log the error reason

## Environment Variables (sync worker)
```
DATABASE_URL=...
FOOTBALL_API_KEY=...         # fetched from Secrets Manager at cold start
FOOTBALL_LEAGUE_IDS=1        # comma-separated league IDs to sync
FOOTBALL_SEASONS=2026        # comma-separated seasons
ENVIRONMENT=prod
```

## Supported Tournaments (scalability)
The worker reads `FOOTBALL_LEAGUE_IDS` and `FOOTBALL_SEASONS` from env, so adding a new tournament (e.g., Copa América, UEFA Euro) is just a config change — no code change needed.
