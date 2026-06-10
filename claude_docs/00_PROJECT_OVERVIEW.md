# World Cup Predictions Game — Project Overview

## What We're Building
A web application (PWA) where users predict scores for football matches (initially FIFA World Cup 2026, designed to scale to other tournaments). Users join parties, submit predictions before kickoff, earn points based on accuracy, and compete on leaderboards.

## Core User Flows
1. Register/login (email or username + password via AWS Cognito)
2. See upcoming matches and submit score predictions
3. Predictions lock automatically at kickoff time
4. After matches finish, scores are synced from external API and points are awarded
5. View personal and party leaderboards
6. Create or join parties via invite code/link

## Technology Stack

### Backend
- **Language:** Python 3.12
- **Framework:** FastAPI with Mangum (AWS Lambda adapter)
- **Database:** PostgreSQL 15 on AWS RDS (t3.micro)
- **Cache:** Redis via AWS ElastiCache (cache.t3.micro) — used for leaderboard and match schedule caching
- **Auth:** AWS Cognito User Pool (JWT tokens)
- **Deployment:** AWS Lambda + API Gateway (HTTP API)
- **Infra as Code:** AWS CDK (Python)
- **Package manager:** uv (for fast installs in Lambda layers)

### Frontend
- **Framework:** React 18 with Vite
- **Language:** TypeScript
- **Styling:** Tailwind CSS v3
- **PWA:** vite-plugin-pwa (Workbox)
- **State:** React Query (TanStack Query v5) for server state, Zustand for local state
- **Auth client:** amazon-cognito-identity-js
- **Routing:** React Router v6
- **Hosting:** S3 + CloudFront

### External Data
- **Primary API:** api-football.com (via RapidAPI) for fixtures and live scores
- **Sync mechanism:** EventBridge scheduled rule → Lambda worker

### AWS Services Used
- Lambda (API + sync worker)
- API Gateway (HTTP API)
- RDS PostgreSQL
- ElastiCache Redis
- S3 (frontend hosting + static assets)
- CloudFront (CDN)
- Cognito (auth)
- EventBridge (scheduled sync jobs)
- SES (invite emails + transactional email)
- Secrets Manager (API keys, DB credentials)
- VPC (RDS + ElastiCache inside private subnet)
- CDK (infrastructure as code)

## Repository Structure
```
worldcup-predictions/
├── backend/
│   ├── app/
│   │   ├── main.py               # FastAPI app entrypoint
│   │   ├── config.py             # Settings (pydantic-settings)
│   │   ├── database.py           # SQLAlchemy async engine + get_db dependency
│   │   ├── dependencies.py       # FastAPI dependency injection (auth, db, cache)
│   │   ├── models/               # SQLAlchemy ORM models
│   │   │   ├── base.py           #   Base, UUIDPrimaryKeyMixin, TimestampMixin
│   │   │   ├── tournament.py     #   Tournament, Team, TournamentTeam
│   │   │   ├── match.py          #   Match
│   │   │   ├── user.py           #   User
│   │   │   ├── party.py          #   Party, PartyMember
│   │   │   ├── prediction.py     #   Prediction
│   │   │   └── leaderboard.py    #   LeaderboardSnapshot
│   │   ├── schemas/              # Pydantic request/response schemas
│   │   ├── routers/              # FastAPI route handlers
│   │   ├── services/             # Business logic layer
│   │   ├── workers/              # Background/sync jobs
│   │   └── utils/
│   ├── migrations/               # Alembic migrations (env.py + versions/)
│   ├── tests/
│   ├── pyproject.toml
│   └── Dockerfile                # For local dev only
├── frontend/
│   ├── src/
│   │   ├── main.tsx
│   │   ├── App.tsx
│   │   ├── pages/
│   │   ├── components/
│   │   ├── hooks/
│   │   ├── stores/
│   │   ├── lib/                  # API client, auth helpers
│   │   └── types/
│   ├── public/
│   │   ├── manifest.json
│   │   └── icons/
│   ├── index.html
│   ├── vite.config.ts
│   ├── tailwind.config.ts
│   └── package.json
├── infrastructure/
│   ├── app.py                    # CDK app entrypoint
│   ├── stacks/
│   │   ├── networking_stack.py   # VPC, subnets, security groups
│   │   ├── data_stack.py         # RDS, ElastiCache
│   │   ├── auth_stack.py         # Cognito
│   │   ├── api_stack.py          # Lambda, API Gateway
│   │   ├── frontend_stack.py     # S3, CloudFront
│   │   └── sync_stack.py         # EventBridge + sync Lambda
│   ├── requirements.txt
│   └── cdk.json
├── docker-compose.yml            # Local dev (postgres + redis)
└── README.md
```

## Scoring System
| Outcome | Points |
|---|---|
| Correct result direction (home win / draw / away win) | 2 pts |
| Exact scoreline | +3 pts |
| Maximum per match | 5 pts |

Predictions lock at `match.kickoff_utc`. Any edit attempt after this timestamp returns HTTP 423.

## Environment Targets
- `dev` — local docker-compose (postgres + redis), no AWS required
- `staging` — AWS account, cheap tier, used for testing
- `prod` — AWS account, same stack, production data
