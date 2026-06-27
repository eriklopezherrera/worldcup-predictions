# Update Instructions — "Ongoing" tournament status fix

Branch: `knockout-updates`

## What changed
The live **FIFA World Cup 2026** tournament was displayed as **"Upcoming"** because its
`tournaments.status` column was still `upcoming`. This fix makes it display as
**"Ongoing" / "En curso"**.

Three parts:

1. **Frontend labels** — the `active` status badge was relabeled
   - `frontend/src/i18n/locales/en.json`: `"active": "Live"` → `"Ongoing"`
   - `frontend/src/i18n/locales/es.json`: `"active": "En vivo"` → `"En curso"`
2. **Seed/populate defaults** — WC2026 now seeds as `active` instead of `upcoming`
   - `backend/app/workers/populate_wc2026_teams.py`
   - `backend/app/workers/seed.py`
3. **Database row** — the existing WC2026 tournament must be flipped from
   `upcoming` → `active` (a data change; code alone does not touch the live row).

> Note: changing the `active` label affects **every** tournament in the `active`
> state, not just WC2026 (statuses are `active | upcoming | finished`).

## Applying to production

> Deploy order matters: ship the code first, then apply the DB change.

### 1. Deploy frontend + backend code

```bash
# from repo root, on the merged branch
infrastructure/scripts/deploy.sh prod
```

This two-pass deploy rebuilds the Vite frontend (picking up the new locale
strings) and updates the Lambda code (including the ops worker). The deployed
api/ops stack must be updated **before** running any migration, because the
migration runs inside the ops Lambda's deployed code.

### 2. Flip the live tournament row to `active`

**Do NOT run the ops `seed` action to do this.** `populate_wc2026_matches`
performs a `DELETE` of all matches for the tournament before re-inserting, which
would wipe every entered result, score, and knockout `predictions_open` flag in
prod.

This is done by a one-line, idempotent `UPDATE`. RDS is in a private subnet, so it
goes through the ops Lambda. The ops Lambda has no generic-SQL action, so it ships
as an Alembic **data migration**, which is already included on this branch:

`backend/migrations/versions/d4e5f6a7b8c9_set_wc2026_status_active.py`

```python
def upgrade() -> None:
    op.execute(
        "UPDATE tournaments SET status = 'active' "
        "WHERE external_id = 1 AND status = 'upcoming'"
    )
```

It only touches the `tournaments` row (targeted by `external_id = 1`), so no
match/result data is affected, and the guard makes it a safe no-op if already
applied. Apply it against prod (after step 1's deploy has completed, so the ops
Lambda is running the new code that contains this migration):

```bash
infrastructure/scripts/migrate.sh prod migrate
```

### 3. Verify

- Open the prod app → Tournaments list → WC2026 should show the green
  **"Ongoing"** badge (switch the language menu to Spanish to confirm
  **"En curso"**).
- Or confirm the row directly via the ops/migrate path / RDS query:
  `SELECT name, status FROM tournaments WHERE external_id = 1;` → `active`.

## Local (already applied)
The local DB row was already updated:
```sql
UPDATE tournaments SET status = 'active' WHERE season = '2026';
```

---

# Update Instructions — Knockout-stage scoring

Branch: `knockout-updates` · commit `8a606bc` · already deployed to the **dev** env
(https://d24y5m6nfdyrmr.cloudfront.net).

## What changed
Knockout matches (Round of 32 → Final) are scored differently from the group
stage: **1 pt** correct result, **2 pts** exact score, **2 pts** picking the team
that advances (still 5 max/match). Group stage is unchanged (2 / 3).

- Scores compare against the **end-of-extra-time** result; a penalty shootout is
  recorded as a **draw** and only resolves who advanced.
- Decisive predictions infer the advancing pick from the predicted winner;
  predicted **draws** require the user (and the admin entering the result) to
  choose who goes through on penalties.
- New DB columns: `matches.winner_team_id`, `matches.decided_by`,
  `predictions.predicted_advancing_team_id`, `predictions.points_advancing`; the
  `predictions.total_points` generated column is redefined to
  `points_result + points_exact + points_advancing`.
- Migration: `backend/migrations/versions/e5f6a7b8c9d0_knockout_advancing_scoring.py`
- Frontend: advancing-team picker for knockout draws, admin winner/`decided_by`
  controls, advanced-team display on finished cards, and a dismissible
  knockout-scoring explainer on the home + predictions pages (en/es).

## Applying to production

> **Ordering matters more than last time.** The new API code references the new
> columns, so once the api/ops Lambda is updated it will error against the old
> schema until the migration runs. Deploy api → migrate **immediately** →
> frontend, to keep that window to ~1 minute. Pick a quiet moment.
>
> The api and ops Lambdas share one code asset, so there is no way to ship the
> migration to the ops Lambda without also updating the api Lambda — hence the
> small unavoidable window. The migration itself is additive and safe.

### Recommended sequence (minimal downtime)

```bash
# from repo root, on the merged branch, with AWS_PROFILE=worldcup

# 0. Build the frontend once so `cdk synth` has the FrontendStack asset.
( cd frontend && npm run build )

# 1. Deploy ONLY the api/ops stack (new backend code + the migration file).
( cd infrastructure && source .venv/Scripts/activate \
  && cdk deploy worldcup-prod-api --context env=prod --require-approval never --profile worldcup )

# 2. Run the migration immediately (closes the old-schema window).
infrastructure/scripts/migrate.sh prod migrate

# 3. Full deploy — redeploys api (no-op) and rebuilds/ships the frontend with
#    the new locale strings and UI.
infrastructure/scripts/deploy.sh prod
```

> `migrate.sh prod migrate` runs `alembic upgrade head`, so it applies **all**
> pending migrations. If the "Ongoing" status fix (`d4e5f6a7b8c9`) above has not
> been deployed to prod yet, this same step applies it too (it's a guarded no-op
> if already applied).

### Simpler alternative (slightly longer window)

If you'd rather not run the api stack separately, just run `deploy.sh prod` then
`migrate.sh prod migrate`. The breakage window then spans the frontend
second-pass build/deploy (~2–3 min) instead of ~1 min. Same end state.

## Caveat — existing knockout predictions
No backfill is performed. Any knockout prediction already saved before this
deploy has `predicted_advancing_team_id = NULL`, so it simply earns 0 of the 2
advancing points when scored (the result/exact points are unaffected). Per the
plan this is acceptable because R32 predictions are locked; if you want those
players to get an advancing pick, reopen the stage so they can re-save before
kickoff.

## Verify
- Open the prod app → a knockout match → entering a **draw** shows the
  "who advances?" picker and blocks save until picked; a **decisive** score shows
  no picker.
- As admin → enter a knockout result → advancing control auto-locks to the
  leading side for decisive scores, requires a pick for draws; regulation /
  extra-time / penalties chips set `decided_by`.
- The dismissible knockout-scoring explainer shows on the home + predictions
  pages.
- Confirm schema if you like:
  `SELECT column_name FROM information_schema.columns WHERE table_name='predictions' AND column_name IN ('points_advancing','predicted_advancing_team_id');`

## Cost note (dev)
The dev env is left running (~$32/mo). Tear it down when done testing:
`infrastructure/scripts/destroy.sh dev`.
