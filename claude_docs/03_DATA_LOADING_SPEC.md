# Data Loading & Match Results

> This replaces the former `03_SYNC_WORKER_SPEC.md`. The api-football.com
> EventBridge sync was dropped: tournament data now comes from two JSON files
> in the repo, and results are entered manually by an admin. The legacy sync
> code (`sync_worker.py`, `football_api_client.py`, `fixture_sync.py`,
> `score_sync.py`) is still in `backend/app/workers/` but is unused and not
> deployed.

---

## Source Files

| File | Contents |
|---|---|
| `backend/worldcup2026_teams.json` | 48 teams: `{name, short_name, group}` |
| `backend/worldcup2026_matches.json` | 104 matches: `{home_team, away_team, kick_off, venue, stage}` (knockout matches have null teams until the bracket is known) |

These are the source of truth for WC2026. Edit them and re-run the loaders to
change tournament data.

## Loaders (`backend/app/workers/`)

### `populate_wc2026_teams.py`
- Upserts the "FIFA World Cup 2026" tournament row (`external_id=1`)
- Upserts each team (matched **by name** — the JSON has no external IDs)
- Links teams to the tournament in `tournament_teams` with their `group_name`
- Idempotent: safe to re-run

### `populate_wc2026_matches.py`
- Resolves teams by name, derives `group_name` from the home team's group
- **Deletes and re-inserts all matches for the tournament** on each run
  (⚠️ this cascades to predictions — do not re-run after users have predicted)
- Logs `populate.unmatched_teams` if a JSON name doesn't match a team row

Run locally:
```bash
cd backend
python -m app.workers.populate_wc2026_teams
python -m app.workers.populate_wc2026_matches
```

## Ops Lambda (deployed environments)

RDS sits in a private subnet, so deployed DB operations go through the
`worldcup-{env}-ops` Lambda (`app/workers/ops.py`, defined in the CDK
ApiStack). Invoke via `infrastructure/scripts/migrate.sh`:

```bash
./scripts/migrate.sh prod                        # alembic upgrade head
./scripts/migrate.sh prod seed                   # run both populate scripts
./scripts/migrate.sh prod make_admin you@x.com   # grant admin rights
```

Payload contract: `{"action": "migrate" | "seed" | "make_admin", "identifier": "...", "revoke": bool}`.

## Match Results Flow

1. An admin (user with `is_admin=true`) enters the final score via the
   frontend `AdminPage` (`/admin`) → `PUT /admin/matches/{id}/result`
2. `match_service.set_match_result`:
   - sets `home_score`/`away_score`, marks the match `finished`
   - (re-)scores **every** prediction for the match with
     `scoring_service.compute_points` (idempotent, so a wrong score can be
     corrected by submitting again)
   - calls `leaderboard_service.recompute_party_leaderboard(db, party_id,
     tournament_id)` for every party that has a member with a prediction on
     the match

There is no scheduled job anywhere in the system.
