# Database Schema

## Engine
PostgreSQL 15 via SQLAlchemy 2.x (async, using `asyncpg` driver).
All models live in `backend/app/models/`.
Migrations managed by Alembic.

---

## Tables

### `tournaments`
Represents a football tournament (e.g., FIFA World Cup 2026).
```sql
CREATE TABLE tournaments (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name        VARCHAR(120) NOT NULL,           -- "FIFA World Cup 2026"
    season      VARCHAR(10) NOT NULL,            -- "2026"
    country     VARCHAR(80),                     -- "USA/Canada/Mexico" or NULL for international
    logo_url    TEXT,
    external_id INTEGER UNIQUE,                  -- stable identifier (WC2026 = 1, set by populate script)
    status      VARCHAR(20) DEFAULT 'upcoming',  -- upcoming | active | finished
    default_prediction_stage VARCHAR(20) NOT NULL DEFAULT 'group',
    created_at  TIMESTAMPTZ DEFAULT now(),
    updated_at  TIMESTAMPTZ DEFAULT now()
);
```

### `teams`
```sql
CREATE TABLE teams (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name        VARCHAR(120) NOT NULL,
    short_name  VARCHAR(10),                     -- "BRA", "ARG"
    logo_url    TEXT,
    external_id INTEGER UNIQUE,                  -- unused for WC2026 (teams matched by name); kept for future tournaments
    created_at  TIMESTAMPTZ DEFAULT now()
);
```

### `tournament_teams`
Many-to-many: which teams participate in which tournament.
```sql
CREATE TABLE tournament_teams (
    tournament_id UUID REFERENCES tournaments(id) ON DELETE CASCADE,
    team_id       UUID REFERENCES teams(id) ON DELETE CASCADE,
    group_name    VARCHAR(5),                    -- "A", "B", ... or NULL for knockouts
    PRIMARY KEY (tournament_id, team_id)
);
```

### `matches`
Core fixture table.
```sql
CREATE TABLE matches (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tournament_id   UUID NOT NULL REFERENCES tournaments(id) ON DELETE CASCADE,
    home_team_id    UUID REFERENCES teams(id),   -- NULL before group draw
    away_team_id    UUID REFERENCES teams(id),
    kickoff_utc     TIMESTAMPTZ NOT NULL,
    venue           VARCHAR(120),
    stage           VARCHAR(30) NOT NULL,        -- group_stage | round_of_16 | quarter_final | semi_final | third_place | final
    group_name      VARCHAR(5),                  -- "A"..."H", NULL for knockouts
    match_day       INTEGER,                     -- 1, 2, 3 for group stage
    home_score      INTEGER,                     -- NULL until finished
    away_score      INTEGER,
    home_score_ht   INTEGER,                     -- half time
    away_score_ht   INTEGER,
    status          VARCHAR(20) DEFAULT 'scheduled', -- scheduled | live | finished | postponed | cancelled
    external_id     INTEGER UNIQUE,              -- unused for WC2026 (matches loaded from JSON); kept for future tournaments
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_matches_tournament ON matches(tournament_id);
CREATE INDEX idx_matches_kickoff ON matches(kickoff_utc);
CREATE INDEX idx_matches_status ON matches(status);
```

### `users`
Application-level user record. Cognito handles passwords.
```sql
CREATE TABLE users (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cognito_sub     VARCHAR(128) UNIQUE NOT NULL,  -- Cognito user sub (JWT `sub` claim)
    username        VARCHAR(50) UNIQUE NOT NULL,
    email           VARCHAR(255) UNIQUE NOT NULL,
    display_name    VARCHAR(80),
    avatar_url      TEXT,
    is_active       BOOLEAN DEFAULT true,
    is_admin        BOOLEAN NOT NULL DEFAULT false,  -- gates /admin/* endpoints; set via make_admin worker
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_users_cognito ON users(cognito_sub);
CREATE INDEX idx_users_username ON users(username);
```

### `parties`
A group of friends competing together.
```sql
CREATE TABLE parties (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            VARCHAR(80) NOT NULL,
    invite_code     VARCHAR(10) UNIQUE NOT NULL,  -- e.g. "WC26ABC"
    created_by      UUID NOT NULL REFERENCES users(id),
    tournament_id   UUID REFERENCES tournaments(id),  -- NULL = all tournaments
    is_global       BOOLEAN DEFAULT false,            -- the one auto-global party
    max_members     INTEGER DEFAULT 200,
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_parties_invite ON parties(invite_code);
```

### `party_members`
```sql
CREATE TABLE party_members (
    party_id    UUID REFERENCES parties(id) ON DELETE CASCADE,
    user_id     UUID REFERENCES users(id) ON DELETE CASCADE,
    role        VARCHAR(20) DEFAULT 'member',    -- member | admin
    joined_at   TIMESTAMPTZ DEFAULT now(),
    PRIMARY KEY (party_id, user_id)
);
```

### `predictions`
One row per user per match. Upserted on each save.
```sql
CREATE TABLE predictions (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id                 UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    match_id                UUID NOT NULL REFERENCES matches(id) ON DELETE CASCADE,
    predicted_home_score    INTEGER NOT NULL,
    predicted_away_score    INTEGER NOT NULL,
    -- Computed when an admin enters the final score (match_service.set_match_result)
    points_result           INTEGER DEFAULT 0,  -- 0 or 2 (correct W/D/L direction)
    points_exact            INTEGER DEFAULT 0,  -- 0 or 3 (exact scoreline)
    total_points            INTEGER GENERATED ALWAYS AS (points_result + points_exact) STORED,
    scored_at               TIMESTAMPTZ,        -- when points were computed
    created_at              TIMESTAMPTZ DEFAULT now(),
    updated_at              TIMESTAMPTZ DEFAULT now(),
    UNIQUE (user_id, match_id)
);

CREATE INDEX idx_predictions_user ON predictions(user_id);
CREATE INDEX idx_predictions_match ON predictions(match_id);
```

### `leaderboard_snapshots`
Cached leaderboard entries. Recomputed by `leaderboard_service.recompute_party_leaderboard` whenever an admin enters/corrects a match result.
```sql
CREATE TABLE leaderboard_snapshots (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    party_id        UUID NOT NULL REFERENCES parties(id) ON DELETE CASCADE,
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    tournament_id   UUID NOT NULL REFERENCES tournaments(id) ON DELETE CASCADE,
    total_points    INTEGER DEFAULT 0,
    exact_scores    INTEGER DEFAULT 0,   -- count of exact score predictions (tiebreaker)
    predictions_made INTEGER DEFAULT 0,
    rank            INTEGER,
    computed_at     TIMESTAMPTZ DEFAULT now(),
    UNIQUE (party_id, user_id, tournament_id)
);

CREATE INDEX idx_leaderboard_party ON leaderboard_snapshots(party_id, tournament_id);
```

---

## SQLAlchemy Model Notes
- Use `mapped_column` and `Mapped` (SQLAlchemy 2.x declarative style)
- Use `AsyncSession` throughout
- Base class: `app.models.base.Base`
- All UUID primary keys use `uuid.uuid4` as Python default + `server_default=text("gen_random_uuid()")`
- All timestamps use `server_default=func.now()` and `onupdate=func.now()`

## Alembic Setup
- Config at `backend/alembic.ini` (not inside `migrations/`)
- `env.py` imports `Base` from `app.models.base` and `import app.models` to register all tables
- Uses async setup with `asyncpg` via `async_engine_from_config` + `asyncio.run`
- Initial schema migration already applied; run `alembic upgrade head` after any model changes
