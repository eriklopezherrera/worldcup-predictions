# Local Development Setup

## Prerequisites
- Docker + Docker Compose
- Python 3.12 with `uv` (`pip install uv`)
- Node.js 20+
- AWS CLI (for CDK deploys only)

---

## docker-compose.yml
Located at project root. Starts local PostgreSQL and Redis.

```yaml
version: "3.9"
services:
  postgres:
    image: postgres:15-alpine
    environment:
      POSTGRES_DB: worldcuppredictions
      POSTGRES_USER: wcadmin
      POSTGRES_PASSWORD: devpassword
    ports:
      - "5433:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U wcadmin -d worldcuppredictions"]
      interval: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    ports:
      - "6380:6379"
    command: redis-server --save "" --appendonly no

volumes:
  postgres_data:
```

---

## Backend Local Dev

### Setup
```bash
cd backend
uv venv
source .venv/bin/activate    # or .venv\Scripts\activate on Windows
uv pip install -e ".[dev]"
cp .env.example .env
```

### `.env` (dev)
```
DATABASE_URL=postgresql+asyncpg://wcadmin:devpassword@localhost:5433/worldcuppredictions
REDIS_URL=redis://localhost:6380/0
COGNITO_USER_POOL_ID=us-east-1_XXXXXXXX
COGNITO_CLIENT_ID=xxxxxxxxxxxxxxxxxxxxxxxxxx
COGNITO_REGION=us-east-1
ALLOWED_ORIGINS=["http://localhost:5173"]
ENVIRONMENT=dev
MOCK_AUTH=true
```
(`DB_SECRET_ARN` is left unset locally — it's only used in deployed environments.)

For **local dev only**, you can use a mock auth mode: set `MOCK_AUTH=true` in `.env`, which bypasses Cognito JWT validation and accepts a simple `X-Dev-User-Id` header. This avoids needing a real Cognito pool during initial development.

### Run migrations
```bash
# Start postgres first
docker compose up postgres -d

# Apply migrations
alembic upgrade head
```

### Run API
```bash
uvicorn app.main:app --reload --port 8000
# API available at http://localhost:8000
# Swagger docs at http://localhost:8000/docs
```

### Load WC2026 data
```bash
python -m app.workers.populate_wc2026_teams     # 48 teams + tournament row
python -m app.workers.populate_wc2026_matches   # 104 matches (deletes + re-inserts!)
```

### Grant yourself admin (for the /admin page)
```bash
python -m app.workers.make_admin you@example.com
```

---

## Frontend Local Dev

### Setup
```bash
cd frontend
npm install
cp .env.example .env.local
```

### `.env.local`
```
VITE_API_BASE_URL=http://localhost:8000
VITE_COGNITO_USER_POOL_ID=us-east-1_XXXXXXXX
VITE_COGNITO_CLIENT_ID=xxxxxxxxxxxxxxxxxxxxxxxxxx
VITE_ENVIRONMENT=dev
```

### Run
```bash
npm run dev
# Available at http://localhost:5173
```

---

## Mock Auth (local testing without Cognito)

Registration and login go **browser → AWS Cognito directly** (via
`amazon-cognito-identity-js`), so they cannot run against placeholder pool IDs.
For local feature testing you can bypass Cognito entirely and run as a single
seeded dev user. This skips the real signup/login UI — it does **not** test the
Cognito flows themselves.

**Backend** (`backend/.env`):
```
MOCK_AUTH=true
```
This makes `get_current_user` accept an `X-Dev-User-Id` header instead of
validating a JWT.

**Frontend** (`frontend/.env.local`):
```
VITE_MOCK_AUTH=true
VITE_DEV_USER_ID=00000000-0000-0000-0000-000000000001
```
In mock mode the auth store skips Cognito (any username/password signs you in)
and the API client sends `X-Dev-User-Id` instead of a Bearer token.

**Seed the dev user** (UUID must match `VITE_DEV_USER_ID`):
```bash
cd backend
python -m app.workers.seed   # upserts the dev user + sample fixtures
```

Then **restart both servers** (env changes are not hot-reloaded) and sign in at
`/login` with any credentials.

> ⚠️ Local only. Both flags default to off in the `.env.example` files — never
> enable them in a deployed build.

---

## Database Migrations

### Create a new migration
```bash
cd backend
alembic revision --autogenerate -m "describe your change"
# Review the generated file in migrations/versions/
alembic upgrade head
```

### Reset local DB (nuclear option)
```bash
docker compose down -v    # destroys postgres volume
docker compose up postgres -d
alembic upgrade head
python -m app.workers.populate_wc2026_teams
python -m app.workers.populate_wc2026_matches
python -m app.workers.seed  # optional: dev user for mock auth
```

---

## `pyproject.toml` (backend)
```toml
[project]
name = "worldcup-predictions-backend"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "fastapi>=0.115",
    "mangum>=0.19",
    "sqlalchemy>=2.0",
    "asyncpg>=0.29",
    "alembic>=1.13",
    "pydantic>=2.0",
    "pydantic-settings>=2.0",
    "redis[asyncio]>=5.0",
    "python-jose[cryptography]>=3.3",
    "boto3>=1.34",
    "httpx>=0.27",            # Cognito JWKS fetch
    "python-multipart>=0.0.9",
    "structlog>=24.0",
]

[project.optional-dependencies]
dev = [
    "uvicorn[standard]>=0.30",
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
    "httpx>=0.27",            # TestClient
    "factory-boy>=3.3",
]
```

---

## Testing

### Backend
```bash
cd backend
pytest tests/ -v
```

Test structure:
- `tests/test_auth.py` — mock auth mode, GET /users/me, PATCH /users/me
- `tests/test_matches.py` — GET /tournaments, GET /tournaments/{id}/matches (filters), GET /matches/{id}, is_locked, actual_result
- `tests/test_predictions.py` — prediction CRUD, lock logic, scoring
- `tests/test_parties.py` — create/join/leave party, invite codes, leaderboard
- `tests/test_admin.py` — require_admin gating, set match result, re-scoring
- `tests/test_sync_worker.py` — legacy api-football sync code (unused in deploys)
- `tests/conftest.py` — async DB session (NullPool), shared redis mock, test user fixtures

Use `pytest-asyncio` with `asyncio_mode = "auto"` in `pytest.ini`.
Use a separate test database: `postgresql+asyncpg://wcadmin:devpassword@localhost:5433/worldcuppredictions_test`

The test database must be created once before running tests (it is not created automatically):
```bash
docker exec worldcup-predictions-postgres-1 psql -U wcadmin -d worldcuppredictions -c "CREATE DATABASE worldcuppredictions_test;"
```

### Frontend
```bash
cd frontend
npm run test        # vitest
npm run lint        # eslint
npm run typecheck   # tsc --noEmit
```
