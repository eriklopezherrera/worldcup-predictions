# World Cup Predictions

A full-stack PWA for predicting football match scores and competing on leaderboards.

## Prerequisites

- Docker + Docker Compose
- Python 3.12 with `uv` — `pip install uv`
- Node.js 20+
- AWS CLI (CDK deploys only)

---

## Quick Start

### 1. Start local infrastructure

```bash
docker compose up -d
```

This starts PostgreSQL on port 5432 and Redis on port 6379.

### 2. Backend

```bash
cd backend
uv venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS / Linux
uv pip install -e ".[dev]"
cp .env.example .env          # edit values if needed
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

- API: http://localhost:8000
- Swagger: http://localhost:8000/docs
- Health check: http://localhost:8000/health

### 3. Frontend

```bash
cd frontend
npm install
cp .env.example .env.local
npm run dev
```

Frontend: http://localhost:5173

---

## Testing

```bash
# Backend
cd backend && pytest tests/ -v

# Frontend
cd frontend && npm test
cd frontend && npm run typecheck
cd frontend && npm run lint
```

---

## Database Migrations

```bash
cd backend
alembic revision --autogenerate -m "describe your change"
alembic upgrade head
```

Reset local DB:

```bash
docker compose down -v
docker compose up postgres -d
alembic upgrade head
```

---

## Mock Auth (local dev)

Set `MOCK_AUTH=true` in `backend/.env`. Then pass `X-Dev-User-Id: <any-uuid>` as a request header — this bypasses Cognito JWT validation.

---

## Environment Targets

| Target   | Description                          |
|----------|--------------------------------------|
| `dev`    | Local docker-compose, no AWS needed  |
| `staging`| AWS account, cheap tier              |
| `prod`   | AWS account, production data         |
