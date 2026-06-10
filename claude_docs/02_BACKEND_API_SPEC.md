# Backend API Specification

## Framework Setup
- FastAPI 0.115+
- Mangum for Lambda handler wrapping
- Pydantic v2 for schemas
- SQLAlchemy 2.x async for ORM
- asyncpg as PostgreSQL driver
- redis[asyncio] for cache
- python-jose for JWT validation against Cognito JWKs

## App Structure
`backend/app/main.py` creates the FastAPI app, registers routers, adds CORS middleware, and defines a `lifespan` context manager.

**Lifespan (startup):** On startup, calls `party_service.ensure_global_parties(db)` — creates a global `is_global=True` party for each active tournament if one doesn't already exist. A `__SYSTEM__` user is used as `created_by`. Failures are caught and logged so a missing DB never blocks startup.

**CORS origins:** configured via env var `ALLOWED_ORIGINS`, defaults to `["http://localhost:5173"]` in dev.

**Lambda handler:** `backend/app/main.py` exports `handler = Mangum(app)`.

---

## Authentication
All protected endpoints require `Authorization: Bearer <cognito_jwt>`.

### Dependency: `get_current_user`
Located in `backend/app/dependencies.py`.
1. Extract JWT from `Authorization` header
2. Fetch Cognito JWKs from `https://cognito-idp.{region}.amazonaws.com/{pool_id}/.well-known/jwks.json` (cache for 1 hour in Redis)
3. Validate signature, expiry, `aud` claim
4. Extract `sub` claim → look up `users` table → return `User` ORM object
5. If user not found in DB (first login after registration), auto-create from JWT claims
6. After auto-create, call `party_service.auto_join_global_parties(db, user.id)` to enrol the new user in every `is_global=True` party (INSERT … ON CONFLICT DO NOTHING)

---

## Routers

### `/auth` — `routers/auth.py`
These endpoints are **public** (no JWT required).

| Method | Path | Description |
|---|---|---|
| POST | `/auth/register` | Initiate Cognito sign-up. Body: `{username, email, password}`. Calls Cognito SDK. Returns `{message: "Verification email sent"}` |
| POST | `/auth/confirm` | Confirm email with code. Body: `{email, code}` |
| POST | `/auth/login` | Authenticate. Body: `{username_or_email, password}`. Returns `{access_token, id_token, refresh_token, expires_in}` |
| POST | `/auth/refresh` | Refresh tokens. Body: `{refresh_token}`. Cognito's `REFRESH_TOKEN_AUTH` flow does not return a new refresh token — the response echoes back the original one. |
| POST | `/auth/forgot-password` | Trigger password reset email. Body: `{email}`. Always returns 200 — `UserNotFoundException` is silently swallowed to prevent user enumeration. |
| POST | `/auth/confirm-forgot-password` | Confirm reset. Body: `{email, code, new_password}` |

All Cognito operations use `boto3` `cognito-idp` client with `USER_PASSWORD_AUTH` flow.

---

### `/users` — `routers/users.py`

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/users/me` | ✅ | Get own profile |
| PATCH | `/users/me` | ✅ | Update display_name, avatar_url. Omitting a field leaves it unchanged; sending `null` explicitly clears it. Uses `model_fields_set` to distinguish the two. |
| GET | `/users/{user_id}` | ✅ | Public profile (username, avatar, stats) |

---

### `/tournaments` — `routers/tournaments.py`

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/tournaments` | ✅ | List all tournaments (id, name, season, status) |
| GET | `/tournaments/{id}` | ✅ | Tournament detail with teams |
| GET | `/tournaments/{id}/matches` | ✅ | All matches. Query params: `stage`, `status`, `group` |
| GET | `/tournaments/{id}/leaderboard` | ✅ | Global leaderboard for this tournament. Query: `limit=50&offset=0` |
| POST | `/tournaments` | Admin only | Create tournament (admin endpoint, protected by Cognito group) |

---

### `/matches` — `routers/matches.py`

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/matches/{id}` | ✅ | Match detail with current prediction for authenticated user |
| GET | `/matches/{id}/predictions` | ✅ | All predictions for a match (visible after kickoff only) |

---

### `/predictions` — `routers/predictions.py`

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/predictions` | ✅ | All predictions by current user. Query: `tournament_id`, `status` |
| PUT | `/predictions/{match_id}` | ✅ | Create or update prediction. Body: `{predicted_home_score, predicted_away_score}`. Returns 423 if match has started. |
| GET | `/predictions/summary` | ✅ | User stats: total points, exact scores, predictions made |

**Lock logic in `PUT /predictions/{match_id}`:**
```python
if match.kickoff_utc <= datetime.now(timezone.utc):
    raise HTTPException(status_code=423, detail="Match has already started. Predictions are locked.")
```

---

### `/parties` — `routers/parties.py`

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/parties` | ✅ | List parties the current user belongs to |
| POST | `/parties` | ✅ | Create a new party. Body: `{name, tournament_id?}`. Auto-generates invite_code. Auto-adds creator as admin. |
| GET | `/parties/{id}` | ✅ | Party detail (members count, tournament) |
| GET | `/parties/{id}/members` | ✅ | List members with their leaderboard position |
| GET | `/parties/{id}/leaderboard` | ✅ | Party leaderboard for tournament. Query: `tournament_id` |
| POST | `/parties/join` | ✅ | Join by invite code. Body: `{invite_code}` |
| DELETE | `/parties/{id}/leave` | ✅ | Leave a party (cannot leave global party) |
| DELETE | `/parties/{id}` | ✅ Admin | Delete party (only creator/admin, cannot delete global party) |
| GET | `/parties/invite/{invite_code}` | Public | Preview party info before joining (for invite link landing page) |

---

## Request/Response Schemas (Pydantic v2)
All schemas in `backend/app/schemas/`.

### Key patterns:
```python
# schemas/prediction.py
class PredictionCreate(BaseModel):
    predicted_home_score: int = Field(ge=0, le=30)
    predicted_away_score: int = Field(ge=0, le=30)

class PredictionResponse(BaseModel):
    id: UUID
    match_id: UUID
    predicted_home_score: int
    predicted_away_score: int
    points_result: int
    points_exact: int
    total_points: int
    is_locked: bool  # computed: match.kickoff_utc <= datetime.now(timezone.utc)
    model_config = ConfigDict(from_attributes=True)

class PredictionSummary(BaseModel):
    total_points: int
    exact_scores: int
    predictions_made: int
```

```python
# schemas/party.py
class PartyCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=80)
    tournament_id: Optional[UUID] = None

class JoinPartyRequest(BaseModel):
    invite_code: str

class PartyResponse(BaseModel):
    id: UUID
    name: str
    invite_code: str          # 7-char alphanumeric for user parties; "GLOBAL" for the global party
    created_by: UUID
    tournament_id: Optional[UUID]
    is_global: bool
    max_members: int
    member_count: int = 0     # computed from party_members COUNT; not a DB column
    model_config = ConfigDict(from_attributes=True)

class LeaderboardEntry(BaseModel):
    user_id: UUID
    username: str
    display_name: Optional[str]
    avatar_url: Optional[str]
    total_points: int
    exact_scores: int         # tiebreaker
    predictions_made: int
    rank: int                 # RANK() semantics — ties share the same rank

class LeaderboardResponse(BaseModel):
    party_id: UUID
    tournament_id: UUID
    entries: list[LeaderboardEntry]
    computed_at: Optional[datetime] = None  # None when result came from live computation
```

---

## Service Layer
Business logic lives in `backend/app/services/`, not in routers.

- `services/match_service.py` — fetch matches, enrich with user's prediction
- `services/prediction_service.py` — upsert prediction, check lock, return result
- `services/leaderboard_service.py` — query leaderboard_snapshots, fallback to live computation
- `services/party_service.py` — create party, generate invite code, join logic
- `services/scoring_service.py` — compute points for a prediction given final scores

### Scoring logic (`services/scoring_service.py`):
```python
def compute_points(
    predicted_home: int, predicted_away: int,
    actual_home: int, actual_away: int
) -> tuple[int, int]:
    """Returns (points_result, points_exact)"""
    def result(h, a):
        if h > a: return "home"
        if a > h: return "away"
        return "draw"
    
    points_result = 2 if result(predicted_home, predicted_away) == result(actual_home, actual_away) else 0
    points_exact = 3 if predicted_home == actual_home and predicted_away == actual_away else 0
    return points_result, points_exact
```

---

## Error Handling
Global exception handler in `main.py`. Standard error response:
```json
{"detail": "Human-readable error message", "code": "MACHINE_READABLE_CODE"}
```

Common codes: `MATCH_LOCKED`, `ALREADY_IN_PARTY`, `PARTY_NOT_FOUND`, `INVALID_INVITE_CODE`, `PREDICTION_NOT_FOUND`.

---

## Config (`app/config.py`)
```python
class Settings(BaseSettings):
    DATABASE_URL: str           # asyncpg connection string
    REDIS_URL: str              # redis://...
    COGNITO_USER_POOL_ID: str
    COGNITO_CLIENT_ID: str
    COGNITO_REGION: str
    FOOTBALL_API_KEY: str       # api-football.com key via Secrets Manager
    ALLOWED_ORIGINS: list[str]
    ENVIRONMENT: str = "dev"    # dev | staging | prod
    
    model_config = SettingsConfigDict(env_file=".env")

    # All field names are lowercase; pydantic-settings matches them case-insensitively
    # to env vars (DATABASE_URL → database_url, etc.)
```

In Lambda, env vars are injected from Secrets Manager + SSM by CDK at deploy time.
