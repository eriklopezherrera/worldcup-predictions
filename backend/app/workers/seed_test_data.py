"""
Seed a few synthetic players with already-scored predictions so the
"view another player's results" feature can be exercised in a non-prod env.

Run via the ops Lambda (see infrastructure/scripts/migrate.sh):

    ./scripts/migrate.sh dev seed_test_data

It is idempotent: re-running updates the same synthetic users/predictions
rather than creating duplicates. The synthetic users are identified by a
``seed::`` cognito_sub prefix and ``@seed.local`` emails, so they are easy to
spot and never collide with real Cognito accounts.

NOTE: intended for disposable/dev environments only. It will mark a handful of
the earliest fixtures as finished (with fabricated scores) if the tournament
has no finished matches yet, so the synthetic predictions have something to
score against.
"""
import uuid
from datetime import datetime, timezone

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal
from app.models.match import Match
from app.models.party import Party, PartyMember
from app.models.prediction import Prediction
from app.models.user import User
from app.services.leaderboard_service import recompute_party_leaderboard
from app.services.scoring_service import compute_points

log = structlog.get_logger()

# Synthetic players. `key` drives a stable cognito_sub so re-runs are idempotent.
TEST_USERS = [
    {"key": "alex", "username": "testplayer_alex", "display_name": "Alex Tester", "email": "alex@seed.local"},
    {"key": "sam", "username": "testplayer_sam", "display_name": "Sam Predictor", "email": "sam@seed.local"},
    {"key": "jordan", "username": "testplayer_jordan", "display_name": "Jordan Picks", "email": "jordan@seed.local"},
]

# Fabricated final scores, applied only to matches that aren't finished yet.
FABRICATED_SCORES = [(2, 1), (0, 0), (3, 1), (1, 2), (2, 2), (1, 0)]

# Per-user outcome quality for each fixture: E=exact (5pts), D=right direction
# (2pts), W=wrong (0pts). Tiered so the synthetic players land on distinct ranks
# (Alex ~19, Sam ~11, Jordan ~4 over 6 matches).
NUM_MATCHES = 6
QUALITY = {
    0: "EEDDEW",  # Alex — strong
    1: "EDDWDW",  # Sam — medium
    2: "DWWDWW",  # Jordan — weak
}


def _predicted_for(user_idx: int, match_idx: int, ah: int, aw: int) -> tuple[int, int]:
    """Deterministic pick whose quality follows the QUALITY table for the user."""
    quality = QUALITY[user_idx % len(QUALITY)]
    q = quality[match_idx % len(quality)]
    if q == "E":
        return ah, aw  # exact scoreline -> 5 pts
    if q == "D":
        # right direction, wrong scoreline -> 2 pts
        if ah > aw:
            return ah + 1, aw
        if aw > ah:
            return ah, aw + 1
        return ah + 1, aw + 1  # draw stays a draw
    # wrong outcome -> 0 pts
    if ah > aw:
        return aw, ah + 1  # flip to an away win
    if aw > ah:
        return ah + 1, aw  # flip to a home win
    return ah + 1, aw  # draw -> home win


async def _get_or_create_user(db: AsyncSession, spec: dict) -> User:
    sub = f"seed::{spec['key']}"
    user = (
        await db.execute(select(User).where(User.cognito_sub == sub))
    ).scalar_one_or_none()
    if user is None:
        user = User(
            cognito_sub=sub,
            username=spec["username"],
            email=spec["email"],
            display_name=spec["display_name"],
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
    return user


async def seed() -> dict:
    async with AsyncSessionLocal() as db:
        # The global party every user is auto-joined to; drives the global board.
        party = (
            await db.execute(
                select(Party)
                .where(Party.is_global.is_(True), Party.tournament_id.isnot(None))
                .order_by(Party.created_at)
            )
        ).scalars().first()
        if party is None:
            raise RuntimeError("No global party with a tournament found; run `seed` first.")
        tournament_id = party.tournament_id

        matches = (
            await db.execute(
                select(Match)
                .where(
                    Match.tournament_id == tournament_id,
                    Match.home_team_id.isnot(None),
                    Match.away_team_id.isnot(None),
                )
                .order_by(Match.kickoff_utc)
            )
        ).scalars().all()
        if not matches:
            raise RuntimeError("No matches with assigned teams found for the tournament.")

        chosen = matches[:NUM_MATCHES]
        now = datetime.now(timezone.utc)

        # Ensure each chosen match is finished with a score so picks can be scored.
        fabricated = 0
        for i, m in enumerate(chosen):
            if m.status != "finished" or m.home_score is None or m.away_score is None:
                m.home_score, m.away_score = FABRICATED_SCORES[i % len(FABRICATED_SCORES)]
                m.status = "finished"
                db.add(m)
                fabricated += 1
        await db.commit()

        # Users + global-party membership.
        users: list[User] = []
        for spec in TEST_USERS:
            u = await _get_or_create_user(db, spec)
            users.append(u)
            member = (
                await db.execute(
                    select(PartyMember).where(
                        PartyMember.party_id == party.id, PartyMember.user_id == u.id
                    )
                )
            ).scalar_one_or_none()
            if member is None:
                db.add(PartyMember(party_id=party.id, user_id=u.id, role="member"))
        await db.commit()

        # Scored predictions for each synthetic user.
        for user_idx, u in enumerate(users):
            for match_idx, m in enumerate(chosen):
                ph, pa = _predicted_for(user_idx, match_idx, m.home_score, m.away_score)
                pr, pe = compute_points(ph, pa, m.home_score, m.away_score)
                pred = (
                    await db.execute(
                        select(Prediction).where(
                            Prediction.user_id == u.id, Prediction.match_id == m.id
                        )
                    )
                ).scalar_one_or_none()
                if pred is None:
                    pred = Prediction(user_id=u.id, match_id=m.id,
                                      predicted_home_score=ph, predicted_away_score=pa)
                    db.add(pred)
                pred.predicted_home_score = ph
                pred.predicted_away_score = pa
                pred.points_result = pr
                pred.points_exact = pe
                pred.scored_at = now
        await db.commit()

        await recompute_party_leaderboard(db, party.id, tournament_id)

        summary = {
            "tournament_id": str(tournament_id),
            "party_id": str(party.id),
            "matches_used": len(chosen),
            "matches_fabricated": fabricated,
            "users": [
                {"id": str(u.id), "username": u.username, "display_name": u.display_name}
                for u in users
            ],
        }
        log.info("seed_test_data.done", **summary)
        return summary
