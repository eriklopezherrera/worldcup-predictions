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
