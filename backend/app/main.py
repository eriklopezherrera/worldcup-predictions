import structlog
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from mangum import Mangum

from app.config import settings
from app.database import AsyncSessionLocal
from app.routers import auth, matches, parties, predictions, tournaments, users

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.services import party_service

    try:
        async with AsyncSessionLocal() as db:
            await party_service.ensure_global_parties(db)
    except Exception as exc:
        logger.warning("startup.global_parties_skipped", error=str(exc))
    yield


app = FastAPI(title="World Cup Predictions API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(tournaments.router)
app.include_router(matches.router)
app.include_router(predictions.router)
app.include_router(parties.router)


@app.get("/health")
async def health():
    return {"status": "ok"}


handler = Mangum(app)
