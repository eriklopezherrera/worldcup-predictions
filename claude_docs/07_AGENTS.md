# Claude Code Agent Plan

## How to Use These Agents

Each agent below is a self-contained Claude Code session with a specific, scoped mission.
Run them in the order listed. Each agent builds on the previous one's output.

Feed each agent:
1. This file (`07_AGENTS.md`) for context on where it fits
2. The specific spec files listed under "Context files"
3. The prompt below

---

## Agent 1: Project Scaffold & Local Dev

**Mission:** Create the complete repository skeleton with all config files, package files, docker-compose, and a working local dev environment. No business logic yet.

**Context files to feed:** `00_PROJECT_OVERVIEW.md`, `06_LOCAL_DEV_SETUP.md`

**Prompt:**
```
You are scaffolding a new full-stack project. Using the PROJECT_OVERVIEW and LOCAL_DEV_SETUP docs, create the complete folder structure for a project called `worldcup-predictions`.

Do the following:
1. Create the full directory tree from the repository structure in the overview doc
2. Create `docker-compose.yml` exactly as specified in the local dev doc
3. Create `backend/pyproject.toml` with all dependencies listed in the dev doc
4. Create `backend/.env.example` with all env vars from the dev doc (values as placeholders)
5. Create `backend/app/__init__.py` and `backend/app/main.py` with a minimal FastAPI app that returns `{"status": "ok"}` at GET `/health`
6. Set up Alembic: run `alembic init migrations` and configure `env.py` for async SQLAlchemy
7. Create `frontend/package.json` with all dependencies from the frontend spec, `vite.config.ts` with vite-plugin-pwa configured, `tailwind.config.ts`, `tsconfig.json`, and `frontend/.env.example`
8. Create `frontend/src/main.tsx` and `frontend/src/App.tsx` as minimal stubs
9. Create a root `README.md` with setup instructions

After creating all files, verify the backend starts: `docker compose up -d && cd backend && uvicorn app.main:app --reload`
```

---

## Agent 2: Database Models & Migrations

**Mission:** Implement all SQLAlchemy models and the initial Alembic migration.

**Context files to feed:** `01_DATABASE_SCHEMA.md`, `06_LOCAL_DEV_SETUP.md`

**Prompt:**
```
You are implementing the database layer for a World Cup predictions app.

Using the DATABASE_SCHEMA doc, do the following:
1. Create `backend/app/models/base.py` — SQLAlchemy 2.x declarative base with UUID PK mixin and timestamp mixin
2. Create individual model files:
   - `backend/app/models/tournament.py` — Tournament, Team, TournamentTeam
   - `backend/app/models/match.py` — Match
   - `backend/app/models/user.py` — User
   - `backend/app/models/party.py` — Party, PartyMember
   - `backend/app/models/prediction.py` — Prediction
   - `backend/app/models/leaderboard.py` — LeaderboardSnapshot
   - `backend/app/models/__init__.py` — import all models
3. Create `backend/app/database.py` — async SQLAlchemy engine, session factory, `get_db` dependency
4. Update `backend/migrations/env.py` to import all models for autogenerate detection
5. Generate the initial migration: `alembic revision --autogenerate -m "initial schema"`
6. Verify migration runs cleanly against the local docker postgres: `alembic upgrade head`
7. Verify all indexes and constraints from the schema doc are present in the generated migration file

Use SQLAlchemy 2.x `mapped_column` / `Mapped` syntax throughout. All PKs are UUIDs.
```

---

## Agent 3: Auth & User Endpoints

**Mission:** Implement Cognito auth flow and user endpoints.

**Context files to feed:** `02_BACKEND_API_SPEC.md`, `01_DATABASE_SCHEMA.md`

**Prompt:**
```
You are implementing authentication for a FastAPI app backed by AWS Cognito.

Using the BACKEND_API_SPEC doc (auth and users sections), do the following:
1. Create `backend/app/config.py` — pydantic-settings Settings class with all env vars
2. Create `backend/app/dependencies.py`:
   - `get_db` — yields async DB session
   - `get_redis` — yields Redis client
   - `get_current_user` — validates Cognito JWT, fetches/creates user in DB, returns User ORM object
   - Implement mock auth mode: if `MOCK_AUTH=true`, accept `X-Dev-User-Id` header and return that user (for local dev without Cognito)
3. Create `backend/app/routers/auth.py` — all 6 auth endpoints using boto3 cognito-idp client
4. Create `backend/app/routers/users.py` — GET /me, PATCH /me, GET /{user_id}
5. Create Pydantic schemas in `backend/app/schemas/auth.py` and `backend/app/schemas/user.py`
6. Register both routers in `backend/app/main.py`
7. Write tests in `backend/tests/test_auth.py`:
   - Test mock auth mode works
   - Test GET /users/me returns current user
   - Test PATCH /users/me updates display_name

The Cognito JWT validation must:
- Fetch JWKs from the Cognito URL and cache them in Redis for 1 hour
- Validate signature, expiry, and `aud` claim
- Extract `sub`, `email`, `cognito:username` claims
```

---

## Agent 4: Tournament & Match Endpoints

**Mission:** Implement tournament and match read endpoints.

**Context files to feed:** `02_BACKEND_API_SPEC.md`, `01_DATABASE_SCHEMA.md`

**Prompt:**
```
You are implementing tournament and match endpoints for a World Cup predictions FastAPI app.

Using the BACKEND_API_SPEC doc (tournaments and matches sections), do the following:
1. Create `backend/app/schemas/tournament.py` and `backend/app/schemas/match.py` — all request/response schemas
2. Create `backend/app/services/match_service.py` — async functions:
   - `get_tournament(db, tournament_id)` → Tournament with teams
   - `get_matches(db, tournament_id, filters)` → list of matches with current user's prediction attached
   - `get_match(db, match_id, user_id)` → single match with prediction
3. Create `backend/app/routers/tournaments.py` — all tournament endpoints
4. Create `backend/app/routers/matches.py` — all match endpoints
5. Register routers in main.py
6. Write tests in `backend/tests/test_matches.py`:
   - Test GET /tournaments returns list
   - Test GET /tournaments/{id}/matches returns matches grouped correctly
   - Test match response includes `is_locked` field based on kickoff time

Each match response must include:
- Match details (teams, kickoff, stage, venue)
- Current user's prediction (or null if none made)
- `is_locked: bool` (kickoff_utc <= now())
- `actual_result: str | null` ("home_win"|"away_win"|"draw"|null) — only after match finishes
```

---

## Agent 5: Predictions Endpoints

**Mission:** Implement prediction CRUD with lock enforcement and scoring logic.

**Context files to feed:** `02_BACKEND_API_SPEC.md`, `00_PROJECT_OVERVIEW.md`

**Prompt:**
```
You are implementing the predictions system for a World Cup predictions app.

Using the BACKEND_API_SPEC doc (predictions section), do the following:
1. Create `backend/app/services/scoring_service.py`:
   - `compute_points(predicted_home, predicted_away, actual_home, actual_away) -> tuple[int, int]`
   - Returns (points_result, points_exact) — see scoring system in PROJECT_OVERVIEW
   - Include unit tests for all cases: correct exact, correct direction only, wrong
2. Create `backend/app/schemas/prediction.py` — PredictionCreate, PredictionResponse
3. Create `backend/app/services/prediction_service.py`:
   - `upsert_prediction(db, user_id, match_id, home, away)` — upserts, checks lock, raises HTTP 423 if locked
   - `get_user_predictions(db, user_id, filters)` — all predictions with match info
   - `get_prediction_summary(db, user_id, tournament_id)` — points total, exact count
4. Create `backend/app/routers/predictions.py` — all 3 prediction endpoints
5. Register router in main.py
6. Write comprehensive tests in `backend/tests/test_predictions.py`:
   - Test create prediction succeeds before kickoff
   - Test update prediction succeeds before kickoff
   - Test prediction locked → returns 423 when match has started
   - Test predictions visible for past matches
   - Test summary returns correct totals
   - Test scoring: exact score = 5 pts, correct direction = 2 pts, wrong = 0 pts
```

---

## Agent 6: Parties & Leaderboard Endpoints

**Mission:** Implement the party/invite system and leaderboard.

**Context files to feed:** `02_BACKEND_API_SPEC.md`, `01_DATABASE_SCHEMA.md`

**Prompt:**
```
You are implementing the parties and leaderboard system for a World Cup predictions app.

Using the BACKEND_API_SPEC doc (parties section) and the DATABASE_SCHEMA, do the following:
1. Create `backend/app/services/party_service.py`:
   - `create_party(db, user_id, name, tournament_id)` — generates unique 7-char alphanumeric invite code, adds creator as admin, auto-joins creator
   - `join_party(db, user_id, invite_code)` — validates code, checks not already member, adds member
   - `get_user_parties(db, user_id)` — returns all parties user belongs to, including global party
   - `get_party_leaderboard(db, party_id, tournament_id)` — reads from leaderboard_snapshots, falls back to live SQL computation if cache is stale
2. Create `backend/app/services/leaderboard_service.py`:
   - `recompute_party_leaderboard(db, party_id, tournament_id)` — runs the upsert SQL from the sync worker spec
3. Create `backend/app/schemas/party.py` — PartyCreate, PartyResponse, LeaderboardEntry, LeaderboardResponse
4. Create `backend/app/routers/parties.py` — all party endpoints
5. Register router in main.py
6. On app startup (`lifespan` in main.py), ensure a global party exists for each active tournament (create if not exists, invite_code = "GLOBAL", is_global = true). All new users are auto-added to global parties.
7. Write tests in `backend/tests/test_parties.py`:
   - Test create party generates unique invite code
   - Test join by invite code adds user
   - Test cannot join same party twice
   - Test cannot leave global party
   - Test leaderboard returns ranked results
   - Test leaderboard tiebreaker (most exact scores wins)
```

---

## Agent 7: Data Sync Worker

**Mission:** Implement the EventBridge Lambda worker that syncs fixtures and scores from api-football.com.

**Context files to feed:** `03_SYNC_WORKER_SPEC.md`, `01_DATABASE_SCHEMA.md`

**Prompt:**
```
You are implementing the data sync worker for a World Cup predictions app.

Using the SYNC_WORKER_SPEC doc, do the following:
1. Create `backend/app/workers/sync_worker.py` — Lambda handler + main sync logic
2. Create `backend/app/workers/football_api_client.py`:
   - Async HTTP client using httpx
   - Methods: `get_fixtures(league_id, season, status=None)`, `get_live_fixtures(league_id, season)`, `get_teams(league_id, season)`
   - Exponential backoff on failure (max 3 retries)
   - Respects rate limits — log remaining requests from response headers
3. Create `backend/app/workers/fixture_sync.py` — `sync_fixtures(db, league_id, season)`:
   - Upserts teams from API
   - Upserts matches with correct status mapping (STATUS_MAP from spec)
   - Upserts tournament_teams
4. Create `backend/app/workers/score_sync.py` — `sync_scores(db)`:
   - Fetches finished/live matches
   - Updates match scores and status
   - Scores all unscored predictions using scoring_service.compute_points
   - Triggers leaderboard_service.recompute_party_leaderboard for affected parties
5. Create `backend/app/workers/seed.py` — development only:
   - Populates DB with 2026 World Cup fixture data for local testing (can be hardcoded JSON or a real API call)
6. Write tests in `backend/tests/test_sync_worker.py`:
   - Mock the API responses (use httpx mock)
   - Test fixture upsert creates/updates correctly
   - Test score sync updates predictions and leaderboard
   - Test status mapping covers all cases

The sync worker must run as a standalone Lambda (separate from the API Lambda). Its entry point `handler(event, context)` accepts `{"sync_type": "fixtures"|"scores"}`.
```

---

## Agent 8: React Frontend — Auth & Layout

**Mission:** Build the React app foundation: auth pages, routing, API client, layout, and PWA config.

**Context files to feed:** `04_FRONTEND_SPEC.md`, `00_PROJECT_OVERVIEW.md`

**Prompt:**
```
You are building the foundation of a React TypeScript PWA for a World Cup predictions game.

Using the FRONTEND_SPEC doc, do the following:
1. Set up `vite.config.ts` with vite-plugin-pwa fully configured (manifest, service worker, icons)
2. Create `src/lib/apiClient.ts` — Axios instance with base URL from env, auth interceptors, token refresh on 401
3. Create `src/lib/auth.ts` — wrapper around amazon-cognito-identity-js for login, register, logout, refresh, confirm email
4. Create `src/stores/authStore.ts` — Zustand store for auth state (user, tokens, loading)
5. Create `src/types/index.ts` — TypeScript interfaces for all entities: Tournament, Match, Prediction, Party, User, LeaderboardEntry
6. Create all auth pages with clean, dark-themed UI (dark bg-gray-900, emerald accents):
   - `src/pages/LoginPage.tsx` — email/username + password, link to register
   - `src/pages/RegisterPage.tsx` — username, email, password
   - `src/pages/VerifyEmailPage.tsx` — 6-digit code input
   - `src/pages/ForgotPasswordPage.tsx` — email input, then code + new password
7. Create `src/App.tsx` — React Router setup with all routes from the spec. Protected route wrapper that redirects to /login if not authenticated.
8. Create the shell layout: `src/components/Layout.tsx` — top navbar (desktop) + bottom navigation bar (mobile, 5 tabs: Home/Predictions/Leaderboard/Parties/Profile)
9. Create empty placeholder pages for all other routes (just a title, no data yet)

Design requirements:
- Dark theme: bg-gray-900 body, bg-gray-800 cards, emerald-500 accents
- Mobile-first: bottom nav on mobile, sidebar/topnav on desktop
- Tailwind only, no additional UI libraries
```

---

## Agent 9: React Frontend — Match Cards & Predictions

**Mission:** Build the core game UI: tournament page, match cards with score inputs, and predictions page.

**Context files to feed:** `04_FRONTEND_SPEC.md`

**Prompt:**
```
You are building the core game UI for a World Cup predictions React app.

Using the FRONTEND_SPEC doc, do the following:
1. Create all API hooks in `src/hooks/`:
   - `useTournaments.ts` — list and single tournament
   - `useMatches.ts` — matches for a tournament with filters
   - `usePredictions.ts` — user's predictions, save prediction mutation
   - `useLeaderboard.ts` — global and party leaderboard
   - `useParties.ts` — user's parties, create party, join party
2. Create `src/components/MatchCard.tsx` — the most important component:
   - Editable state: team names/flags, score inputs (two number inputs with +/- buttons), save button, countdown timer showing time until lock
   - Locked/in-progress state: team names, user's prediction greyed out, "LIVE" or "In Progress" badge
   - Scored state: actual score prominently shown, user's prediction, points badge ("+5" in gold, "+2" in green, "0" in grey)
   - Smooth CSS transition between states
   - Optimistic update: show saving spinner, revert on error
3. Create `src/components/ScoreInput.tsx` — clean numeric input with + and - buttons, min 0, max 30
4. Create `src/components/Countdown.tsx` — live countdown "Locks in 2h 34m 12s", updates every second, turns red when < 30 minutes
5. Create `src/pages/TournamentPage.tsx`:
   - Stats bar at top: "You have X/Y predictions | X pts | Rank #N globally"
   - Matches grouped by stage, then match day
   - Each group has a collapsible section header
   - Lazy loads predictions alongside matches
6. Create `src/pages/MyPredictionsPage.tsx`:
   - Filter tabs: All | Group Stage | Knockout | Pending | Scored
   - Grid of prediction cards showing team, my pick, actual result, points
   - Summary stats at top
7. Make sure MatchCard correctly disables inputs and shows a lock icon when `is_locked = true`
```

---

## Agent 10: React Frontend — Leaderboard & Parties

**Mission:** Build the social features: leaderboards and party management.

**Context files to feed:** `04_FRONTEND_SPEC.md`

**Prompt:**
```
You are building the social/leaderboard features for a World Cup predictions React app.

Using the FRONTEND_SPEC doc, do the following:
1. Create `src/components/LeaderboardTable.tsx`:
   - Ranked table: position, avatar (initials fallback), username, total points, exact scores, predictions made
   - Current user's row highlighted in emerald
   - Rank delta badge (▲2 green, ▼1 red, — grey)
   - Pagination: 50 per page, load more button
2. Create `src/pages/LeaderboardPage.tsx`:
   - Tabs: Global | [each party the user is in]
   - Tournament selector dropdown (if multiple tournaments)
   - Top 3 podium display (larger cards for 1st/2nd/3rd)
3. Create `src/pages/PartiesPage.tsx`:
   - List of user's parties with member count and user's rank
   - "Create Party" button
   - "Join with code" input
4. Create `src/pages/CreatePartyPage.tsx`:
   - Form: party name, optional tournament filter
   - On success, show the generated invite code + shareable link + copy button
5. Create `src/pages/JoinPartyPage.tsx` (route: `/parties/join/:code`):
   - Shows party preview (name, member count, top 3 members)
   - "Join Party" button
   - If not logged in, redirects to login then back here
6. Create `src/pages/PartyPage.tsx`:
   - Party name, invite code (with copy button), member count
   - Leaderboard table scoped to this party
   - "Share invite link" button (copies `{base_url}/parties/join/{code}` to clipboard)
   - Leave party button (hidden for global party)
7. Create `src/pages/ProfilePage.tsx`:
   - Display name, username, email
   - Edit display name inline
   - Stats: total points, exact scores, predictions made, best rank
   - Logout button
```

---

## Agent 11: AWS Infrastructure (CDK)

**Mission:** Implement all CDK stacks and deployment scripts.

**Context files to feed:** `05_INFRASTRUCTURE_SPEC.md`, `00_PROJECT_OVERVIEW.md`

**Prompt:**
```
You are implementing AWS CDK v2 (Python) infrastructure for a World Cup predictions app.

Using the INFRASTRUCTURE_SPEC doc, do the following:
1. Set up `infrastructure/` with `app.py`, `requirements.txt` (aws-cdk-lib, constructs), and `cdk.json`
2. Create all 6 CDK stacks exactly as specified:
   - `stacks/networking_stack.py` — VPC, subnets, security groups
   - `stacks/data_stack.py` — RDS PostgreSQL, ElastiCache Redis
   - `stacks/auth_stack.py` — Cognito User Pool + App Client
   - `stacks/api_stack.py` — Lambda (API), API Gateway HTTP API, IAM roles
   - `stacks/sync_stack.py` — Lambda (sync worker), EventBridge rules
   - `stacks/frontend_stack.py` — S3, CloudFront, BucketDeployment
3. In `app.py`, instantiate all stacks with proper dependency wiring and `env_name` context
4. Create `infrastructure/scripts/deploy.sh` — script that:
   - Builds frontend (`cd ../frontend && npm run build`)
   - Runs `cdk deploy --all --context env={ENV}`
5. Create `infrastructure/scripts/migrate.sh` — script that SSMs into a bastion or uses RDS proxy to run `alembic upgrade head` against the target environment
6. Add IAM policies: Lambda execution roles need RDS access (via Secrets Manager), ElastiCache access, Cognito describe, SES send email
7. All resource names must be parameterized by `env_name` to support dev/staging/prod in the same account

Do NOT hardcode account IDs or region — use CDK environment tokens.
```

---

## Agent 12: Polish, Error Handling & Production Readiness

**Mission:** Add error handling, loading states, edge cases, and production hardening across the full stack.

**Context files to feed:** All spec files

**Prompt:**
```
You are hardening a World Cup predictions app for production. Review all existing code and do the following:

Backend:
1. Add structured JSON logging throughout (use Python `structlog` or `logging` with JSON formatter) — every request should log: method, path, user_id, duration_ms, status_code
2. Add global exception handler in main.py that catches unhandled exceptions and returns standardized error responses without leaking stack traces
3. Add rate limiting on auth endpoints (POST /auth/login: max 5/min per IP) using Redis
4. Verify all DB queries use proper async patterns and don't block the event loop
5. Add a `/health` endpoint that checks DB connectivity and Redis connectivity, returns 200 or 503
6. Add input validation: prediction scores must be 0-30; party names must be 1-80 chars; usernames alphanumeric + underscores only

Frontend:
7. Add proper loading skeletons for MatchCard, LeaderboardTable (no blank flashes)
8. Add error boundaries — if a page crashes, show a friendly error with a "Reload" button
9. Add toast notifications for: prediction saved ✅, prediction failed ❌, party created ✅, joined party ✅, errors ❌
10. Handle the "offline" state gracefully — show a banner when network is unavailable, predictions queue for retry
11. Add empty states: no predictions yet, no parties yet, leaderboard loading
12. Ensure all timestamps are displayed in the user's local timezone (use date-fns with `Intl.DateTimeFormat`)
13. Add a "Install App" prompt for PWA — show a subtle banner on mobile browsers if the app is not installed

Testing:
14. Ensure backend test coverage > 80% for services layer
15. Add one end-to-end test using pytest that simulates: register → predict → sync scores → check leaderboard
```

---

## Summary: Agent Execution Order

```
Agent 1  →  Scaffold
Agent 2  →  Database
Agent 3  →  Auth + Users
Agent 4  →  Tournaments + Matches
Agent 5  →  Predictions + Scoring
Agent 6  →  Parties + Leaderboard
Agent 7  →  Sync Worker
─────── Backend complete ───────
Agent 8  →  Frontend Foundation
Agent 9  →  Match Cards + Predictions UI
Agent 10 →  Leaderboard + Parties UI
Agent 11 →  AWS CDK Infrastructure
Agent 12 →  Polish + Production Hardening
```

Each agent should run `git commit` at the end of its work with a descriptive message.
