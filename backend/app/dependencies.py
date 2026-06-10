from collections.abc import AsyncGenerator
import json
import uuid

import httpx
import redis.asyncio as aioredis
from fastapi import Depends, HTTPException, Header
from jose import jwt, JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db, AsyncSessionLocal  # noqa: F401 — re-export get_db for conftest
from app.models.user import User

__all__ = ["get_db", "get_redis", "get_current_user", "require_admin"]


async def get_redis() -> AsyncGenerator[aioredis.Redis, None]:
    client = aioredis.from_url(settings.redis_url, decode_responses=True)
    try:
        yield client
    finally:
        await client.aclose()


async def _fetch_jwks(redis_client: aioredis.Redis) -> dict:
    """Fetch Cognito JWKs, returning a cached copy when available."""
    cache_key = "cognito:jwks"
    cached = await redis_client.get(cache_key)
    if cached:
        return json.loads(cached)

    url = (
        f"https://cognito-idp.{settings.cognito_region}.amazonaws.com"
        f"/{settings.cognito_user_pool_id}/.well-known/jwks.json"
    )
    async with httpx.AsyncClient() as http:
        resp = await http.get(url)
        resp.raise_for_status()
        jwks = resp.json()

    await redis_client.set(cache_key, json.dumps(jwks), ex=3600)
    return jwks


async def _validate_token(token: str, redis_client: aioredis.Redis) -> dict:
    try:
        headers = jwt.get_unverified_header(token)
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token format")

    kid = headers.get("kid")
    jwks = await _fetch_jwks(redis_client)
    key = next((k for k in jwks["keys"] if k["kid"] == kid), None)
    if not key:
        raise HTTPException(status_code=401, detail="Token signing key not found")

    try:
        payload = jwt.decode(
            token,
            key,
            algorithms=["RS256"],
            audience=settings.cognito_client_id,
        )
    except JWTError as exc:
        raise HTTPException(status_code=401, detail=f"Invalid token: {exc}")

    return payload


async def get_current_user(
    authorization: str | None = Header(default=None),
    x_dev_user_id: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
    redis_client: aioredis.Redis = Depends(get_redis),
) -> User:
    if settings.mock_auth:
        if not x_dev_user_id:
            raise HTTPException(status_code=401, detail="X-Dev-User-Id header required in mock auth mode")
        try:
            user_uuid = uuid.UUID(x_dev_user_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid user ID format")
        user = await db.get(User, user_uuid)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        return user

    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authorization header required")

    token = authorization.removeprefix("Bearer ")
    payload = await _validate_token(token, redis_client)

    cognito_sub = payload.get("sub")
    if not cognito_sub:
        raise HTTPException(status_code=401, detail="Invalid token: missing sub claim")

    result = await db.execute(select(User).where(User.cognito_sub == cognito_sub))
    user = result.scalar_one_or_none()

    if not user:
        # Auto-create on first login — JWT claims are the source of truth for identity
        user = User(
            cognito_sub=cognito_sub,
            username=payload.get("cognito:username", cognito_sub),
            email=payload.get("email", ""),
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)

        from app.services.party_service import auto_join_global_parties
        await auto_join_global_parties(db, user.id)
        await db.commit()

    return user


async def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin privileges required")
    return current_user
