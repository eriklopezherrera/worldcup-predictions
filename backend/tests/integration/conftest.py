"""
Shared fixtures for the integration test suite.

The parent tests/conftest.py supplies: setup_db (autouse), db, client.
This file adds auth-aware fixtures and common domain objects used across
the integration sub-suite.
"""
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.dependencies import get_db, get_redis
from app.main import app
from app.models.match import Match
from app.models.tournament import Tournament
from app.models.user import User


@pytest.fixture
def mock_auth(monkeypatch):
    monkeypatch.setattr(settings, "mock_auth", True)


@pytest.fixture
async def auth_client(db: AsyncSession, mock_auth):
    """HTTP client that uses X-Dev-User-Id mock auth."""
    mock_redis = MagicMock()
    mock_redis.get = AsyncMock(return_value=None)
    mock_redis.set = AsyncMock(return_value=True)
    mock_redis.aclose = AsyncMock()

    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_redis] = lambda: mock_redis
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest.fixture
async def user(db: AsyncSession) -> User:
    u = User(
        cognito_sub="int-sub-user1",
        username="intuser1",
        email="int1@example.com",
        display_name="Integration User",
    )
    db.add(u)
    await db.commit()
    await db.refresh(u)
    return u


@pytest.fixture
async def other_user(db: AsyncSession) -> User:
    u = User(
        cognito_sub="int-sub-user2",
        username="intuser2",
        email="int2@example.com",
    )
    db.add(u)
    await db.commit()
    await db.refresh(u)
    return u


@pytest.fixture
async def system_user(db: AsyncSession) -> User:
    u = User(
        cognito_sub="__SYSTEM__",
        username="__system__",
        email="system@worldcup.internal",
    )
    db.add(u)
    await db.commit()
    await db.refresh(u)
    return u


@pytest.fixture
async def tournament(db: AsyncSession) -> Tournament:
    t = Tournament(
        name="FIFA World Cup 2026",
        season="2026",
        status="active",
        country="USA/Canada/Mexico",
    )
    db.add(t)
    await db.commit()
    await db.refresh(t)
    return t


@pytest.fixture
async def future_match(db: AsyncSession, tournament: Tournament) -> Match:
    m = Match(
        tournament_id=tournament.id,
        kickoff_utc=datetime.now(timezone.utc) + timedelta(hours=3),
        stage="group_stage",
        group_name="A",
        status="scheduled",
    )
    db.add(m)
    await db.commit()
    await db.refresh(m)
    return m


@pytest.fixture
async def finished_match(db: AsyncSession, tournament: Tournament) -> Match:
    m = Match(
        tournament_id=tournament.id,
        kickoff_utc=datetime.now(timezone.utc) - timedelta(hours=3),
        stage="group_stage",
        group_name="B",
        status="finished",
        home_score=2,
        away_score=0,
    )
    db.add(m)
    await db.commit()
    await db.refresh(m)
    return m
