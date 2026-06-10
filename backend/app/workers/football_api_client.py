import asyncio
from typing import Any

import httpx
import structlog

log = structlog.get_logger()

STATUS_MAP: dict[str, str] = {
    "NS": "scheduled",
    "1H": "live",
    "HT": "live",
    "2H": "live",
    "ET": "live",
    "BT": "live",
    "P": "live",       # Penalties in progress
    "FT": "finished",
    "AET": "finished",  # After Extra Time
    "PEN": "finished",  # After Penalties
    "PST": "postponed",
    "CANC": "cancelled",
    "SUSP": "cancelled",
}

_BASE_URL = "https://v3.football.api-sports.io"
_MAX_RETRIES = 3


class FootballApiClient:
    def __init__(self, api_key: str) -> None:
        self._client = httpx.AsyncClient(
            base_url=_BASE_URL,
            headers={"x-apisports-key": api_key},
            timeout=30.0,
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> "FootballApiClient":
        return self

    async def __aexit__(self, *_: Any) -> None:
        await self.close()

    async def _get(self, path: str, params: dict) -> dict:
        last_exc: Exception | None = None
        for attempt in range(_MAX_RETRIES):
            try:
                resp = await self._client.get(path, params=params)
                remaining = resp.headers.get("x-ratelimit-requests-remaining")
                if remaining is not None:
                    log.info("football_api.rate_limit", remaining=remaining)
                if resp.status_code == 429:
                    wait = 2 ** attempt
                    log.warning("football_api.rate_limited", attempt=attempt, wait_s=wait)
                    await asyncio.sleep(wait)
                    continue
                resp.raise_for_status()
                data = resp.json()
                # api-football returns HTTP 200 even when the request is rejected
                # (bad key, plan/season not allowed, etc.); the reason lives in
                # `errors` ([] when OK, a dict of messages when not). Surface it.
                errors = data.get("errors")
                if errors:
                    log.warning("football_api.api_error", path=path, params=params, errors=errors)
                return data
            except (httpx.HTTPStatusError, httpx.RequestError) as exc:
                last_exc = exc
                log.warning(
                    "football_api.request_error",
                    attempt=attempt,
                    path=path,
                    error=str(exc),
                )
                if attempt < _MAX_RETRIES - 1:
                    await asyncio.sleep(2 ** attempt)
        raise last_exc  # type: ignore[misc]

    async def get_fixtures(
        self,
        league_id: int,
        season: int,
        status: str | None = None,
    ) -> list[dict]:
        params: dict = {"league": league_id, "season": season}
        if status:
            params["status"] = status
        data = await self._get("/fixtures", params)
        return data.get("response", [])

    async def get_live_fixtures(self, league_id: int, season: int) -> list[dict]:
        data = await self._get(
            "/fixtures",
            {"league": league_id, "season": season, "live": "all"},
        )
        return data.get("response", [])

    async def get_teams(self, league_id: int, season: int) -> list[dict]:
        data = await self._get("/teams", {"league": league_id, "season": season})
        return data.get("response", [])
