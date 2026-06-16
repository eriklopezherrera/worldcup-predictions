# Lessons Learned

Captured from the initial scaffolding session (2026-06-08).

---

## 1. Local port conflicts with Docker

**What happened:** `docker compose up -d` failed because ports 5432 (postgres) and 6379 (redis) were already occupied by local installations on the dev machine.

**Fix:** Remap Docker's external ports in `docker-compose.yml`:
- postgres: `5433:5432`
- redis: `6380:6379`

**Ripple effect:** The port change must be propagated to every place that hardcodes a connection string:
- `docker-compose.yml`
- `backend/alembic.ini` (`sqlalchemy.url`)
- `backend/app/config.py` (default values)
- `backend/.env.example`
- `claude_docs/06_LOCAL_DEV_SETUP.md` (see lesson 3)

---

## 2. Setuptools flat-layout rejects multiple top-level packages

**What happened:** `uv pip install -e ".[dev]"` failed with:
> Multiple top-level packages discovered in a flat-layout: ['app', 'migrations']

**Fix:** Add an explicit include rule to `backend/pyproject.toml`:
```toml
[tool.setuptools.packages.find]
include = ["app*"]
```
This tells setuptools to only package `app/` as a distribution package. `migrations/` is Alembic tooling, not a Python package to be installed.

---

## 3. Spec docs must stay in sync with actual files — especially for agent workflows

**What happened:** After remapping ports in the project files, `claude_docs/06_LOCAL_DEV_SETUP.md` still referenced the old ports (5432/6379). Any agent reading that doc would regenerate files with the wrong ports, silently breaking the setup.

**Rule:** Whenever a config value changes in an actual project file, check every `claude_docs/` file that references that value and update it in the same step. Agents treat these docs as ground truth.

---

## 4. `redis[asyncio]` extra is obsolete in redis >= 6.x

**What happened:** Installing `redis[asyncio]>=5.0` produced a warning:
> The package `redis==8.0.0` does not have an extra named `asyncio`

**Fix:** asyncio support is built-in as of redis 6+. The dependency in `pyproject.toml` can simply be `redis>=5.0` with no extra.

---

## 5. `alembic.ini` holds its own hardcoded DB URL

`alembic.ini` contains a `sqlalchemy.url` line that is separate from the app's `.env` / pydantic-settings config. It does not automatically pick up `DATABASE_URL` from the environment. When the connection string changes, `alembic.ini` must be updated manually — or `migrations/env.py` should be extended to read `DATABASE_URL` from the environment and override the ini value.

---

## 6. The `version` key in docker-compose.yml is obsolete

Docker Compose v2+ ignores the top-level `version` attribute and emits a warning. It can be removed from `docker-compose.yml` without any functional impact.

---

*Lessons 7–11 captured from the database layer implementation session (2026-06-08).*

---

## 7. `TIMESTAMPTZ` is not a named export from SQLAlchemy's PostgreSQL dialect

**What happened:** `from sqlalchemy.dialects.postgresql import TIMESTAMPTZ` raises `ImportError`. SQLAlchemy does not expose a standalone `TIMESTAMPTZ` alias.

**Fix:** Use `TIMESTAMP(timezone=True)` from `sqlalchemy`:
```python
from sqlalchemy import TIMESTAMP

created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), ...)
```
This renders as `TIMESTAMP WITH TIME ZONE` in PostgreSQL DDL, which is identical to `TIMESTAMPTZ`.

---

## 8. `server_default` for string columns requires SQL-quoted values

**What happened:** Using `server_default="upcoming"` on a `VARCHAR` column would generate `DEFAULT upcoming` in DDL — PostgreSQL interprets unquoted values as column/function references, causing an error or wrong behavior.

**Fix:** Always wrap string literals in `text()` with inner SQL single-quotes:
```python
status: Mapped[str] = mapped_column(String(20), server_default=text("'upcoming'"))
```
For booleans and integers, no inner quotes are needed: `text("true")`, `text("0")`.

---

## 9. `TimestampMixin` only applies to tables that have both `created_at` and `updated_at`

Several tables in this schema diverge from the two-column pattern:
- `teams` — `created_at` only (no `updated_at`)
- `party_members` — `joined_at` only
- `leaderboard_snapshots` — `computed_at` only
- `tournament_teams` — no timestamps at all

**Rule:** Apply `TimestampMixin` only to tables that truly have both columns. Add inline `mapped_column` definitions for tables that use a different timestamp field or only one column.

---

## 10. `Computed(..., persisted=True)` maps correctly to `GENERATED ALWAYS AS ... STORED`

SQLAlchemy 2.x's `Computed` with `persisted=True` correctly generates a PostgreSQL stored generated column:
```python
from sqlalchemy import Computed

total_points: Mapped[int] = mapped_column(
    Integer,
    Computed("points_result + points_exact", persisted=True),
)
```
Alembic autogenerate detects and emits this correctly. Do not pass this column in ORM constructors — the DB computes it.

---

## 11. `alembic check` is the fast way to verify zero drift after a migration

After running `alembic upgrade head`, run:
```bash
alembic check
```
It exits non-zero and prints detected differences if the models have drifted from the applied migration. "No new upgrade operations detected" confirms the DB and models are in sync. Useful as a final verification step before committing or deploying.

---

*Lessons 12–19 captured from the auth + users implementation session (2026-06-08).*

---

## 12. `pydantic.EmailStr` requires the `email-validator` package at runtime

**What happened:** Using `EmailStr` in a Pydantic v2 model raises `ImportError: email-validator is not installed` at import time, even though `email-validator` is not listed as a Pydantic core dependency.

**Fix:** Either add `email-validator` to `pyproject.toml`, or use plain `str` for email fields. Since Cognito already validates email format before accepting registration, `str` is sufficient for the auth schemas in this project and avoids the extra dependency.

---

## 13. `conftest.py` must import `Base` from `app.models.base`, not `app.database`

**What happened:** The scaffolded `conftest.py` contained `from app.database import Base`, but `database.py` does not import or re-export `Base`. This raises `ImportError` the first time tests are collected.

**Fix:**
```python
from app.models.base import Base
import app.models  # registers all ORM models with Base.metadata
```
Alternatively, `from app.main import app` (already present in conftest) triggers the full import chain transitively, so all models are registered before `Base.metadata.create_all` is called.

---

## 14. Every test client fixture must override `get_redis`, not just `get_db`

**What happened:** After `get_current_user` was updated to depend on `get_redis`, any test that called a protected endpoint would attempt a live Redis connection — even in mock-auth mode — because FastAPI resolves the full dependency graph at request time regardless of code paths taken at runtime.

**Fix:** Add a `MagicMock` redis override alongside the DB override in every test client fixture:
```python
mock_redis = MagicMock()
mock_redis.get = AsyncMock(return_value=None)
mock_redis.set = AsyncMock(return_value=True)
mock_redis.aclose = AsyncMock()
app.dependency_overrides[get_redis] = lambda: mock_redis
```
The shared `client` fixture in `conftest.py` now does this automatically for all tests.

---

## 15. Cognito `REFRESH_TOKEN_AUTH` does not return a new refresh token

**What happened:** The `AuthenticationResult` from `initiate_auth` with `AuthFlow="REFRESH_TOKEN_AUTH"` only contains `AccessToken`, `IdToken`, and `ExpiresIn`. There is no `RefreshToken` key — accessing it raises `KeyError`.

**Fix:** Echo back the original refresh token that was sent in the request body:
```python
return TokenResponse(
    access_token=auth["AccessToken"],
    id_token=auth["IdToken"],
    refresh_token=body.refresh_token,  # Cognito does not rotate the refresh token
    expires_in=auth["ExpiresIn"],
)
```

---

## 16. Use `model_fields_set` to distinguish "omitted" from "explicitly null" in PATCH endpoints

**What happened:** With `display_name: str | None = None` as the default, a missing field and a field sent as `null` are both `None` — there is no way to tell them apart by value alone.

**Fix:** Iterate over `body.model_fields_set` (the set of field names the client actually sent) rather than checking for `None`:
```python
for field in body.model_fields_set:
    setattr(current_user, field, getattr(body, field))
```
This means: omitting a field → no DB write; sending `"display_name": null` → clears the field.

---

## 17. `POST /auth/forgot-password` must always return 200 to prevent user enumeration

**What happened:** Raising `HTTPException(404)` when `UserNotFoundException` is returned by Cognito reveals whether an email address is registered, which is a security vulnerability.

**Fix:** Catch `UserNotFoundException` and return the success message regardless:
```python
except client.exceptions.UserNotFoundException:
    pass  # do not leak whether the account exists
return MessageResponse(message="If that account exists, a password reset email has been sent")
```

---

## 18. Pydantic v2 settings: use `SettingsConfigDict`, not `class Config`

**What happened:** The `class Config` inner-class pattern is Pydantic v1. Pydantic v2 emits a deprecation warning when it is used inside a `BaseSettings` subclass.

**Fix:**
```python
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    ...
    model_config = SettingsConfigDict(env_file=".env")
```

---

## 19. boto3 is synchronous — wrap calls with `asyncio.to_thread` in async endpoints

**What happened:** Calling boto3 `cognito-idp` methods directly in an `async def` endpoint blocks the event loop for the duration of the HTTP round-trip to AWS.

**Fix:** Use `asyncio.to_thread` to run the blocking boto3 call in a thread pool:
```python
response = await asyncio.to_thread(
    client.initiate_auth,
    AuthFlow="USER_PASSWORD_AUTH",
    AuthParameters={"USERNAME": ..., "PASSWORD": ...},
    ClientId=settings.cognito_client_id,
)
```
Exceptions raised inside the thread (including `client.exceptions.*` and `botocore.exceptions.ClientError`) propagate normally to the caller.

---

*Lesson 20 captured from the tournament/match endpoint implementation session (2026-06-08).*

---

## 20. Module-level SQLAlchemy async engine requires `NullPool` in `pytest-asyncio` function-scope mode

**What happened:** With `asyncio_mode = "auto"` and function-scoped event loops (the default), only the first test in a session passed. All subsequent tests failed with either `RuntimeError: Event loop is closed` or `asyncpg.exceptions._base.InterfaceError: cannot perform operation: another operation is in progress`. This happened because `test_engine` was created once at module import time. asyncpg connections in the pool were tied to the first test's event loop; when that loop closed and a new one opened for the next test, the pooled connections became invalid.

**Fix:** Add `poolclass=NullPool` to `create_async_engine` in `conftest.py`:
```python
from sqlalchemy.pool import NullPool

test_engine = create_async_engine(TEST_DATABASE_URL, echo=False, poolclass=NullPool)
```
With `NullPool`, every `async with test_engine.begin()` opens a fresh connection and closes it immediately — no pooling, no event-loop binding between tests.

---

## 21. Return plain dicts from services when responses contain computed fields or JOIN-sourced data

**What happened:** Match responses need fields that aren't ORM attributes (`is_locked`, `actual_result`) and nested sub-objects assembled from JOINs (team rows). Initially it was tempting to return ORM objects and rely on Pydantic's `from_attributes=True` to handle serialization. This approach has two failure modes: (1) SQLAlchemy raises `DetachedInstanceError` when the response serializer accesses lazy-loaded attributes after the session has closed; (2) FastAPI's `jsonable_encoder` does not know how to traverse nested ORM objects from JOIN results that aren't proper relationship attributes.

**Fix:** Have the service build and return a plain Python `dict` with all fields — including computed ones — pre-filled as primitives. Nested sub-objects (teams, predictions) are also plain dicts. The router returns the dict directly; FastAPI validates it against the `response_model` without any ORM interaction:
```python
def _build_match_dict(match, home_team, away_team, prediction) -> dict:
    return {
        "is_locked": match.kickoff_utc <= datetime.now(timezone.utc),
        "actual_result": _compute_actual_result(match),
        "home_team": {"id": home_team.id, "name": home_team.name, ...} if home_team else None,
        "my_prediction": {...} if prediction else None,
        ...
    }
```
This pattern applies any time a response model mixes ORM data, computed fields, and JOIN-assembled sub-objects.

---

## 22. Compare TIMESTAMPTZ columns against `datetime.now(timezone.utc)`, not `datetime.utcnow()`

**What happened:** asyncpg returns `TIMESTAMP WITH TIME ZONE` columns as timezone-aware `datetime` objects (UTC). Comparing them against `datetime.utcnow()` — which returns a naive (timezone-unaware) datetime — raises `TypeError: can't compare offset-naive and offset-aware datetimes`.

**Fix:** Always use `datetime.now(timezone.utc)` for "current time" comparisons against TIMESTAMPTZ columns:
```python
from datetime import datetime, timezone

is_locked = match.kickoff_utc <= datetime.now(timezone.utc)
```
Note: `CLAUDE.md` uses `datetime.utcnow()` as shorthand in prose; the actual implementation must use the timezone-aware form. `datetime.utcnow()` is also deprecated in Python 3.12+.

---

*Lessons 23–26 captured from the predictions system implementation session (2026-06-08).*

---

## 23. Schema filenames in this project are singular, not plural

**What happened:** `02_BACKEND_API_SPEC.md` referred to `schemas/predictions.py` (plural). All other schema files in the project use singular names: `user.py`, `auth.py`, `match.py`, `tournament.py`. The actual file was created as `prediction.py` to match the convention, and the spec was corrected.

**Rule:** Always use the singular form for schema filenames in `backend/app/schemas/`. Upcoming work will follow the same pattern: `party.py`, `leaderboard.py`, etc. When the spec and the existing file convention disagree, the existing convention wins.

---

## 24. In FastAPI, register literal routes before parametric routes of the same method

**What happened:** The predictions router has both `GET /predictions/summary` and a future-possible `GET /predictions/{match_id}`. FastAPI matches routes in registration order. If a parametric route like `GET /{id}` is registered before a literal `GET /summary`, FastAPI tries to parse `"summary"` as a UUID, fails validation, and returns 422 instead of matching the intended literal route.

**Fix:** Always register literal paths before parametric paths **of the same HTTP method** within a router:
```python
@router.get("/summary")        # literal — registered first
@router.get("")                # list
@router.put("/{match_id}")     # parametric PUT — different method, no conflict with GET /summary
```
This applies even when the conflict doesn't exist yet. Adding `GET /{match_id}` later would silently break `GET /summary` if ordering is wrong.

---

## 25. SQLAlchemy 2.x `case()` for conditional COUNT in aggregate queries

**What happened:** Needed to count rows matching a condition (e.g., predictions where `points_exact > 0`) inside a single aggregate query alongside `SUM` and total `COUNT`.

**Fix:** Use `func.count(case((condition, value)))` with no `else_`. When the condition is false, `case` returns `NULL`; `COUNT` ignores `NULL`s, so only matching rows are counted:
```python
from sqlalchemy import case, func

func.count(case((Prediction.points_exact > 0, 1))).label("exact_scores")
```
The positional tuple syntax `case((condition, result), ...)` is the SQLAlchemy 2.x searched-case form. Do not use the legacy `case([...])` list form — it was removed in 2.x.

---

## 26. `func.sum()` returns NULL on an empty result set — use `func.coalesce`

**What happened:** When a user has no predictions, `SELECT SUM(total_points) FROM predictions WHERE user_id = ?` returns a single row with `NULL`, not `0`. Accessing `row.total_points` without guarding returns `None`, which breaks a `PredictionSummary` schema expecting `int`.

**Fix:** Wrap every `func.sum()` in a `func.coalesce(..., 0)` in queries that may have no matching rows:
```python
func.coalesce(func.sum(Prediction.total_points), 0).label("total_points")
```
Note: `func.count()` does **not** have this problem — it returns `0` for empty sets, not `NULL`. Only `SUM`, `AVG`, `MIN`, and `MAX` return `NULL` on empty input.

---

*Lessons 27–33 captured from the parties and leaderboard implementation session (2026-06-08).*

---

## 27. httpx `ASGITransport` does NOT trigger ASGI lifespan events

**What happened:** Added a `lifespan` context manager to `main.py` that connects to the database to create global parties. Concern: would it fire during tests and try to connect to the wrong DB?

**Answer:** No. `httpx.AsyncClient(transport=ASGITransport(app=app))` sends HTTP requests to the ASGI app but never sends a `lifespan.startup` event. Only Starlette's `TestClient` (sync) and explicit ASGI lifespan wrappers trigger startup/shutdown.

**Rule:** Startup code in a FastAPI `lifespan` function is safe to have — it will run under uvicorn/Lambda but will be silently skipped in the existing httpx-based test suite. Still wrap it in `try/except` in case the DB is unavailable.

---

## 28. System-created records with NOT NULL FK to `users.id` require a dedicated system user

**What happened:** `parties.created_by` is `NOT NULL REFERENCES users(id)`. The global party is created at startup by the app, not by a real user, so there is no `user_id` to pass.

**Fix:** At startup, `get_or_create` a system user with a reserved, never-loginable `cognito_sub`:
```python
User(cognito_sub="__SYSTEM__", username="__system__", email="system@worldcup.internal")
```
This satisfies the FK constraint and is clearly identifiable as non-human. The `__SYSTEM__` `cognito_sub` will never match a real Cognito token, so `get_current_user` will never return it.

---

## 29. A UNIQUE `invite_code` column means only one record can hold a given code

**What happened:** The spec says the global party should have `invite_code = "GLOBAL"`. But `invite_code` has a `UNIQUE` constraint, so if two tournaments each need a global party, the second INSERT would fail.

**Fix:** Use `"GLOBAL"` for the first active tournament's global party and check before inserting. If `"GLOBAL"` is already taken, fall back to a derived code (e.g. `f"GL{str(tournament.id).replace('-', '')[:8].upper()}"[:10]`). Always query for the existing code before committing.

**Broader rule:** Whenever a spec gives a "canonical" unique value (like `"GLOBAL"`), code defensively: check if it's taken before using it, and have a deterministic fallback.

---

## 30. `pg_insert(...).on_conflict_do_nothing()` for idempotent many-to-many inserts

**What happened:** Auto-joining a user to global parties on first login could race or be called twice. A plain `db.add(PartyMember(...))` would raise `IntegrityError` on a duplicate composite primary key.

**Fix:** Use the PostgreSQL-dialect upsert with no update action:
```python
from sqlalchemy.dialects.postgresql import insert as pg_insert

stmt = (
    pg_insert(PartyMember)
    .values(party_id=party.id, user_id=user.id, role="member")
    .on_conflict_do_nothing()
)
await db.execute(stmt)
```
This generates `INSERT ... ON CONFLICT DO NOTHING`, which is a no-op if the row already exists. Use this pattern anywhere you need idempotent inserts into a table with a unique or PK constraint.

---

## 31. Import services lazily inside `lifespan` to avoid circular imports at module load

**What happened:** `main.py` sits at the top of the import chain — it imports routers, which import services. If a service also imported something from `main.py` (even transitively), a module-level `from app.services import party_service` at the top of `main.py` would cause a circular import error at startup.

**Fix:** Import the service inside the `lifespan` function body, not at module level:
```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.services import party_service   # deferred import
    async with AsyncSessionLocal() as db:
        await party_service.ensure_global_parties(db)
    yield
```
The deferred import runs after all modules are fully loaded, so circular dependency chains are resolved by the time the function executes.

---

## 32. Use `text("col_alias DESC")` in `order_by()` to reference SELECT-level labels

**What happened:** In the live leaderboard query, `ORDER BY` needed to sort by `SUM(total_points)` and `SUM(CASE ...)`, both of which were already labeled in the `SELECT` list. Duplicating the full expression in `order_by()` is verbose and can confuse SQLAlchemy's query compiler.

**Fix:** PostgreSQL allows ordering by column aliases defined in the same `SELECT`. Reference them with `text()`:
```python
.order_by(text("total_points DESC"), text("exact_scores DESC"))
```
This is clean, unambiguous, and avoids re-expressing the aggregate. Use the exact label name assigned in the `SELECT`.

---

## 33. Python RANK() tiebreaker for live leaderboard computation

**What happened:** The sync worker spec uses `RANK() OVER (PARTITION BY ... ORDER BY ...)` in its upsert SQL. The live fallback path computes the leaderboard from raw predictions without writing to `leaderboard_snapshots`, so the window function isn't available — ranks must be computed in Python.

**Fix:** Sort query results by the same criteria used in `ORDER BY`, then assign ranks in a single pass:
```python
prev_pts = prev_exact = None
current_rank = 0
for i, row in enumerate(rows):
    if row.total_points != prev_pts or row.exact_scores != prev_exact:
        current_rank = i + 1          # jump to 1-based position on change
    prev_pts, prev_exact = row.total_points, row.exact_scores
    entries.append({..., "rank": current_rank})
```
This implements SQL `RANK()` semantics exactly: tied rows share a rank, and the next distinct group jumps to its 1-based position (skipping numbers), e.g. 1, 1, 3.

---

*Lessons 34–35 captured from the spec maintenance session (2026-06-09).*

---

## 34. The leaderboard recomputation SQL in the spec is a global batch; the implementation is per-party

**What happened:** The SQL in `03_SYNC_WORKER_SPEC.md` had no `party_id` filter:
```sql
WHERE m.tournament_id = :tournament_id
  AND p.scored_at IS NOT NULL
```
This was designed as a single query that recomputes all parties for a tournament at once.

The implemented `leaderboard_service.recompute_party_leaderboard(db, party_id, tournament_id)` adds `AND pm.party_id = :party_id`, so it processes one party at a time. The spec was updated to match.

**Rule:** The sync worker must loop over `affected_party_ids` and call `recompute_party_leaderboard` once per party — it cannot pass only `tournament_id` and expect all parties to update. When implementing `sync_worker.py`, use this pattern:
```python
for party_id in affected_party_ids:
    await recompute_party_leaderboard(db, party_id, tournament_id)
```

---

## 35. When updating spec docs, the sync worker spec is a secondary consumer of service interfaces

**What happened:** After implementing `leaderboard_service.py`, the review of `02_BACKEND_API_SPEC.md` caught the API-layer changes, but `03_SYNC_WORKER_SPEC.md` also referenced the same leaderboard logic — as raw SQL that was now encapsulated in the service. An agent implementing the sync worker from that spec alone would have duplicated the SQL rather than called the service.

**Rule:** After implementing a service, check every spec file that references the same domain — not just the API spec. For this project, `03_SYNC_WORKER_SPEC.md` is a secondary consumer of anything in `services/` that touches scoring or leaderboards. Update it to reference the service function and mark the SQL as "reference only."

---

*Lesson 36 captured from the prod debugging session (2026-06-10).*

---

## 36. Vite loads `.env.local` in all modes — mock-auth env vars can leak into production builds

**What happened:** `.env.local` contained `VITE_MOCK_AUTH=true` and `VITE_DEV_USER_ID=00000000-0000-0000-0000-000000000001` for local development. The deploy script regenerates `.env.production` with real infra URLs but does not define `VITE_MOCK_AUTH`. Because Vite loads `.env.local` in every mode — including `vite build --mode production` — these vars bled into the prod bundle. The frontend entered mock-auth mode, skipped Cognito entirely, and sent the dev UUID as the Bearer token to the production API, which returned 401 for every request.

**Two fixes applied:**

1. **Gate `MOCK_AUTH` on `import.meta.env.DEV`** in `frontend/src/lib/devAuth.ts`:
   ```ts
   export const MOCK_AUTH = import.meta.env.DEV && import.meta.env.VITE_MOCK_AUTH === 'true'
   ```
   `import.meta.env.DEV` is statically `false` in production builds, so Vite dead-code-eliminates the entire mock path from the bundle. This makes it impossible for mock auth to ship regardless of env-file layering.

2. **Rename `.env.local` → `.env.development.local`** — Vite only loads `*.development.*` files in dev mode (`npm run dev`), so local mock settings are never visible to production builds. Local dev is unaffected.

**Rule:** Never put mock-auth vars in `.env.local`; use `.env.development.local`. Always gate dev-only feature flags on `import.meta.env.DEV` as a second line of defence.

---

*Lessons 37–41 captured from the "show all players on the leaderboard" session (2026-06-10).*

---

## 37. Leaderboards must be member-driven (LEFT JOIN), not prediction-driven (INNER JOIN)

**What happened:** Both the live (`_live_leaderboard`) and snapshot (`recompute_party_leaderboard`) computations started `FROM ... JOIN predictions ... WHERE p.scored_at IS NOT NULL`. The inner join meant a member only appeared once they had a *scored* prediction. Before any match was scored, the board was completely empty — even members who had joined or made (unscored) predictions vanished.

**Fix:** Start `FROM party_members` and `LEFT JOIN` predictions, putting the `scored_at IS NOT NULL` and tournament filters in the **JOIN condition, not a WHERE clause** (a `WHERE` on the right side of an outer join silently turns it back into an inner join). Coalesce sums to 0:
```python
.outerjoin(Prediction, (Prediction.user_id == PartyMember.user_id) & Prediction.scored_at.is_not(None))
```

**Rule:** Any "show everyone, with zeros for those who haven't acted yet" board must anchor on the population table (members), not the activity table (predictions). Filters that should not drop rows belong in the `ON` clause.

---

## 38. The real root cause of the empty global board: `ensure_global_parties` only covered `active` tournaments

**What happened:** After fixing the queries (lesson 37) and adding a server-side global endpoint (lesson 39), the global board was *still* empty. A read-only diagnostic against prod RDS showed there was **no global party at all** — only the user-created party existed. The WC2026 tournament had `status = "upcoming"`, but `ensure_global_parties` filtered `WHERE status == "active"`, so it never created a global party. With nothing to resolve, the board was correctly empty.

**Fix:** Cover upcoming tournaments too — a global board is useful before kickoff:
```python
select(Tournament).where(Tournament.status.in_(("upcoming", "active")))
```

**Rule:** A "global"/tournament-wide aggregate depends on a seed record (the global party) existing. Before assuming a read-path bug, verify the seed data actually exists for the relevant entity *state*. `upcoming` is a first-class state in this project, not a pre-launch placeholder.

---

## 39. A global/tournament-wide board should resolve its party server-side, with no membership gate

**What happened:** The first attempt resolved the global party client-side via `useParties()` (the caller's own membership list) and reused `GET /parties/{id}/leaderboard`, which gates on `_assert_member`. Two failure modes: the global party might not be in the user's list, and even if it were, a non-member gets 403.

**Fix:** Added `GET /tournaments/{id}/leaderboard` that resolves the tournament's global party in the service layer and returns its board with **no membership assertion** (every user is auto-joined anyway). Returns `party_id=null` + empty entries rather than 404 when no global party exists, so the UI shows its empty state cleanly. `LeaderboardResponse.party_id` was made `Optional` to allow this.

**Rule:** Don't make the client discover server-owned singletons (like "the global party") from its own scoped data. Resolve them server-side and don't reuse a membership-gated endpoint for a board everyone is meant to see.

---

## 40. Auto-join-on-signup leaves a backfill gap for records created later

**What happened:** `auto_join_global_parties` only runs when a user is first created (`get_current_user` auto-provision path). Any user who signed up *before* the global party existed would never be a member of it — so even after the party was created, existing users were missing from the global board.

**Fix:** Make `ensure_global_parties` (startup, idempotent) also backfill: join every existing non-system user to every global party, via `pg_insert(...).on_conflict_do_nothing()`. Confirmed in prod the global party went from 0 → 4 members on the next cold start.

**Rule:** Any "auto-join at creation time" rule needs a companion idempotent backfill for the population that predates the joinable thing. Run it at startup so it self-heals on every deploy. (Lambda runs the `lifespan` startup hook on each cold start; a code deploy forces a cold start, so the backfill runs on the first post-deploy request.)

---

## 41. Inspecting private-subnet RDS in prod: add a temporary read-only action to the ops Lambda

**What happened:** RDS is in a private subnet with no direct access (per CLAUDE.md), and there was no JWT handy to hit the API. To find out whether the global party existed, I needed to see the actual prod data. CloudWatch logs only showed request lifecycle, not app state.

**Technique:** Temporarily add a `diagnose` action to `app/workers/ops.py` (the ops Lambda already lives in the VPC and uses `AsyncSessionLocal`), deploy *only* the API stack (`cdk deploy worldcup-prod-api`, ~25-40s, no frontend rebuild), invoke it, read the JSON, then **revert the action and redeploy** to strip it from prod. Keep the diagnostic out of any commit.

**Gotchas:**
- Git-Bash mangles `/aws/lambda/...` log-group paths into Windows mount paths (`C:/Program Files/Git/aws/...`). Use PowerShell for `aws logs` calls.
- PowerShell mangles inline single-quoted JSON payloads. Write the payload to a temp file and pass `--payload file://...` instead.
- The ops Lambda has its own handler and does **not** run the API's `lifespan` startup hook, so it reads the DB the API startup wrote to — a clean separate read path.

**Rule:** For one-off prod data inspection behind a private subnet, the ops Lambda is the right tool. Treat the diagnostic as scaffolding: never commit it, and always redeploy to remove it from the live function once done.
