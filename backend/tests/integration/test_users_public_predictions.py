"""
Tests for GET /users/{user_id}/predictions — another player's scored picks.

Only predictions whose match has already been scored (scored_at set) should be
exposed, and the response must never leak the player's email or private data.
"""
import uuid
from datetime import datetime, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.match import Match
from app.models.prediction import Prediction
from app.models.user import User


def _auth(u: User) -> dict:
    return {"X-Dev-User-Id": str(u.id)}


@pytest.fixture
async def scored_prediction(
    db: AsyncSession, other_user: User, finished_match: Match
) -> Prediction:
    """A prediction by other_user on a finished match that has been scored."""
    p = Prediction(
        user_id=other_user.id,
        match_id=finished_match.id,
        predicted_home_score=2,
        predicted_away_score=0,
        points_result=2,
        points_exact=3,
        scored_at=datetime.now(timezone.utc),
    )
    db.add(p)
    await db.commit()
    await db.refresh(p)
    return p


@pytest.fixture
async def unscored_prediction(
    db: AsyncSession, other_user: User, future_match: Match
) -> Prediction:
    """A prediction on a not-yet-played match — must stay private."""
    p = Prediction(
        user_id=other_user.id,
        match_id=future_match.id,
        predicted_home_score=1,
        predicted_away_score=1,
    )
    db.add(p)
    await db.commit()
    await db.refresh(p)
    return p


async def test_returns_scored_prediction(
    auth_client: AsyncClient, user: User, other_user: User, scored_prediction: Prediction
):
    response = await auth_client.get(
        f"/users/{other_user.id}/predictions", headers=_auth(user)
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    item = data[0]
    assert item["predicted_home_score"] == 2
    assert item["predicted_away_score"] == 0
    assert item["total_points"] == 5
    assert item["home_score"] == 2
    assert item["away_score"] == 0
    assert item["actual_result"] == "home_win"


async def test_excludes_unscored_prediction(
    auth_client: AsyncClient,
    user: User,
    other_user: User,
    scored_prediction: Prediction,
    unscored_prediction: Prediction,
):
    response = await auth_client.get(
        f"/users/{other_user.id}/predictions", headers=_auth(user)
    )
    assert response.status_code == 200
    data = response.json()
    # Only the scored one is returned; the future-match pick stays private.
    assert len(data) == 1
    assert data[0]["match_id"] == str(scored_prediction.match_id)


async def test_response_does_not_leak_email_or_user(
    auth_client: AsyncClient, user: User, other_user: User, scored_prediction: Prediction
):
    response = await auth_client.get(
        f"/users/{other_user.id}/predictions", headers=_auth(user)
    )
    assert response.status_code == 200
    body = response.text
    assert other_user.email not in body
    item = response.json()[0]
    assert "email" not in item
    assert "user_id" not in item


async def test_unknown_user_returns_404(auth_client: AsyncClient, user: User):
    response = await auth_client.get(
        f"/users/{uuid.uuid4()}/predictions", headers=_auth(user)
    )
    assert response.status_code == 404


async def test_requires_auth(auth_client: AsyncClient, other_user: User):
    response = await auth_client.get(f"/users/{other_user.id}/predictions")
    assert response.status_code == 401


async def test_empty_when_no_scored_predictions(
    auth_client: AsyncClient, user: User, other_user: User
):
    response = await auth_client.get(
        f"/users/{other_user.id}/predictions", headers=_auth(user)
    )
    assert response.status_code == 200
    assert response.json() == []
