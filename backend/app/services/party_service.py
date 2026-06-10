import random
import string
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import HTTPException
from sqlalchemy import case, func, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.leaderboard import LeaderboardSnapshot
from app.models.match import Match
from app.models.party import Party, PartyMember
from app.models.prediction import Prediction
from app.models.tournament import Tournament
from app.models.user import User

_CODE_CHARS = string.ascii_uppercase + string.digits
_STALE_AFTER = timedelta(hours=1)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _party_to_dict(party: Party, member_count: int = 0) -> dict:
    return {
        "id": party.id,
        "name": party.name,
        "invite_code": party.invite_code,
        "created_by": party.created_by,
        "tournament_id": party.tournament_id,
        "is_global": party.is_global,
        "max_members": party.max_members,
        "member_count": member_count,
    }


def _snapshot_to_entry(snap: LeaderboardSnapshot, user: User) -> dict:
    return {
        "user_id": snap.user_id,
        "username": user.username,
        "display_name": user.display_name,
        "avatar_url": user.avatar_url,
        "total_points": snap.total_points,
        "exact_scores": snap.exact_scores,
        "predictions_made": snap.predictions_made,
        "rank": snap.rank,
    }


async def _generate_invite_code(db: AsyncSession) -> str:
    for _ in range(10):
        code = "".join(random.choices(_CODE_CHARS, k=7))
        taken = (
            await db.execute(select(Party).where(Party.invite_code == code))
        ).scalar_one_or_none()
        if not taken:
            return code
    raise RuntimeError("Failed to generate unique invite code after 10 attempts")


async def _member_count(db: AsyncSession, party_id: uuid.UUID) -> int:
    result = await db.execute(
        select(func.count(PartyMember.party_id)).where(PartyMember.party_id == party_id)
    )
    return result.scalar() or 0


async def _assert_member(
    db: AsyncSession, party_id: uuid.UUID, user_id: uuid.UUID
) -> PartyMember:
    member = (
        await db.execute(
            select(PartyMember).where(
                PartyMember.party_id == party_id,
                PartyMember.user_id == user_id,
            )
        )
    ).scalar_one_or_none()
    if not member:
        raise HTTPException(status_code=403, detail="Not a member of this party")
    return member


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------


async def create_party(
    db: AsyncSession,
    user_id: uuid.UUID,
    name: str,
    tournament_id: Optional[uuid.UUID],
) -> dict:
    invite_code = await _generate_invite_code(db)
    party = Party(
        name=name,
        invite_code=invite_code,
        created_by=user_id,
        tournament_id=tournament_id,
    )
    db.add(party)
    await db.flush()

    member = PartyMember(party_id=party.id, user_id=user_id, role="admin")
    db.add(member)
    await db.commit()
    await db.refresh(party)
    return _party_to_dict(party, member_count=1)


async def join_party(
    db: AsyncSession,
    user_id: uuid.UUID,
    invite_code: str,
) -> dict:
    party = (
        await db.execute(select(Party).where(Party.invite_code == invite_code))
    ).scalar_one_or_none()
    if not party:
        raise HTTPException(status_code=404, detail="Party not found")

    existing = (
        await db.execute(
            select(PartyMember).where(
                PartyMember.party_id == party.id,
                PartyMember.user_id == user_id,
            )
        )
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail="Already a member of this party")

    count = await _member_count(db, party.id)
    if count >= party.max_members:
        raise HTTPException(status_code=409, detail="Party is full")

    db.add(PartyMember(party_id=party.id, user_id=user_id, role="member"))
    await db.commit()
    return _party_to_dict(party, member_count=count + 1)


async def get_user_parties(db: AsyncSession, user_id: uuid.UUID) -> list[dict]:
    from sqlalchemy.orm import aliased

    # Correlated subquery counts ALL members in the party, not just the
    # filtered membership row used to check the user belongs to it.
    pm_all = aliased(PartyMember, name="pm_all")
    member_count_sq = (
        select(func.count(pm_all.party_id))
        .where(pm_all.party_id == Party.id)
        .correlate(Party)
        .scalar_subquery()
    )

    stmt = (
        select(Party, member_count_sq.label("member_count"))
        .join(PartyMember, Party.id == PartyMember.party_id)
        .where(PartyMember.user_id == user_id)
    )
    rows = (await db.execute(stmt)).all()
    return [_party_to_dict(party, member_count) for party, member_count in rows]


async def get_party(
    db: AsyncSession, party_id: uuid.UUID, user_id: uuid.UUID
) -> dict:
    party = await db.get(Party, party_id)
    if not party:
        raise HTTPException(status_code=404, detail="Party not found")
    await _assert_member(db, party_id, user_id)
    count = await _member_count(db, party_id)
    return _party_to_dict(party, member_count=count)


async def get_party_members(
    db: AsyncSession, party_id: uuid.UUID, user_id: uuid.UUID
) -> list[dict]:
    await _assert_member(db, party_id, user_id)
    stmt = (
        select(PartyMember, User)
        .join(User, User.id == PartyMember.user_id)
        .where(PartyMember.party_id == party_id)
    )
    rows = (await db.execute(stmt)).all()
    return [
        {
            "user_id": user.id,
            "username": user.username,
            "display_name": user.display_name,
            "avatar_url": user.avatar_url,
            "role": member.role,
            "joined_at": member.joined_at,
            "total_points": 0,
            "rank": None,
        }
        for member, user in rows
    ]


async def leave_party(
    db: AsyncSession, user_id: uuid.UUID, party_id: uuid.UUID
) -> None:
    party = await db.get(Party, party_id)
    if not party:
        raise HTTPException(status_code=404, detail="Party not found")
    if party.is_global:
        raise HTTPException(status_code=403, detail="Cannot leave the global party")

    member = (
        await db.execute(
            select(PartyMember).where(
                PartyMember.party_id == party_id,
                PartyMember.user_id == user_id,
            )
        )
    ).scalar_one_or_none()
    if not member:
        raise HTTPException(status_code=404, detail="Not a member of this party")

    await db.delete(member)
    await db.commit()


async def delete_party(
    db: AsyncSession, user_id: uuid.UUID, party_id: uuid.UUID
) -> None:
    party = await db.get(Party, party_id)
    if not party:
        raise HTTPException(status_code=404, detail="Party not found")
    if party.is_global:
        raise HTTPException(status_code=403, detail="Cannot delete the global party")

    member = (
        await db.execute(
            select(PartyMember).where(
                PartyMember.party_id == party_id,
                PartyMember.user_id == user_id,
                PartyMember.role == "admin",
            )
        )
    ).scalar_one_or_none()
    if not member:
        raise HTTPException(status_code=403, detail="Only party admins can delete this party")

    await db.delete(party)
    await db.commit()


async def get_party_preview(db: AsyncSession, invite_code: str) -> dict:
    party = (
        await db.execute(select(Party).where(Party.invite_code == invite_code))
    ).scalar_one_or_none()
    if not party:
        raise HTTPException(status_code=404, detail="Party not found")
    count = await _member_count(db, party.id)
    return _party_to_dict(party, member_count=count)


# ---------------------------------------------------------------------------
# Leaderboard
# ---------------------------------------------------------------------------


async def get_party_leaderboard(
    db: AsyncSession,
    party_id: uuid.UUID,
    tournament_id: uuid.UUID,
    user_id: uuid.UUID,
) -> dict:
    await _assert_member(db, party_id, user_id)

    # Try the snapshot cache first.
    stmt = (
        select(LeaderboardSnapshot, User)
        .join(User, User.id == LeaderboardSnapshot.user_id)
        .where(
            LeaderboardSnapshot.party_id == party_id,
            LeaderboardSnapshot.tournament_id == tournament_id,
        )
        .order_by(LeaderboardSnapshot.rank)
    )
    rows = (await db.execute(stmt)).all()

    if rows:
        stale_threshold = datetime.now(timezone.utc) - _STALE_AFTER
        most_recent = max(snap.computed_at for snap, _ in rows)
        if most_recent >= stale_threshold:
            return {
                "party_id": party_id,
                "tournament_id": tournament_id,
                "entries": [_snapshot_to_entry(snap, user) for snap, user in rows],
                "computed_at": most_recent,
            }

    # Fallback: live computation from predictions.
    return await _live_leaderboard(db, party_id, tournament_id)


async def _live_leaderboard(
    db: AsyncSession,
    party_id: uuid.UUID,
    tournament_id: uuid.UUID,
) -> dict:
    total_pts = func.coalesce(func.sum(Prediction.total_points), 0).label("total_points")
    exact_sc = func.coalesce(
        func.sum(case((Prediction.points_exact > 0, 1), else_=0)), 0
    ).label("exact_scores")

    stmt = (
        select(
            PartyMember.user_id,
            User.username,
            User.display_name,
            User.avatar_url,
            total_pts,
            exact_sc,
            func.count(Prediction.id).label("predictions_made"),
        )
        .join(Prediction, Prediction.user_id == PartyMember.user_id)
        .join(Match, Match.id == Prediction.match_id)
        .join(User, User.id == PartyMember.user_id)
        .where(
            PartyMember.party_id == party_id,
            Match.tournament_id == tournament_id,
            Prediction.scored_at.is_not(None),
        )
        .group_by(PartyMember.user_id, User.username, User.display_name, User.avatar_url)
        .order_by(text("total_points DESC"), text("exact_scores DESC"))
    )
    rows = (await db.execute(stmt)).all()

    entries: list[dict] = []
    prev_pts = prev_exact = None
    current_rank = 0
    for i, row in enumerate(rows):
        if row.total_points != prev_pts or row.exact_scores != prev_exact:
            current_rank = i + 1
        prev_pts = row.total_points
        prev_exact = row.exact_scores
        entries.append(
            {
                "user_id": row.user_id,
                "username": row.username,
                "display_name": row.display_name,
                "avatar_url": row.avatar_url,
                "total_points": row.total_points,
                "exact_scores": row.exact_scores,
                "predictions_made": row.predictions_made,
                "rank": current_rank,
            }
        )

    return {
        "party_id": party_id,
        "tournament_id": tournament_id,
        "entries": entries,
        "computed_at": None,
    }


# ---------------------------------------------------------------------------
# Startup
# ---------------------------------------------------------------------------


async def ensure_global_parties(db: AsyncSession) -> None:
    """
    Idempotent: called at app startup.  For each active tournament, create a
    global party if one doesn't already exist.
    """
    # Get or create the system user used as `created_by` for global parties.
    result = await db.execute(select(User).where(User.cognito_sub == "__SYSTEM__"))
    system_user = result.scalar_one_or_none()
    if not system_user:
        system_user = User(
            cognito_sub="__SYSTEM__",
            username="__system__",
            email="system@worldcup.internal",
        )
        db.add(system_user)
        await db.flush()

    result = await db.execute(select(Tournament).where(Tournament.status == "active"))
    tournaments = result.scalars().all()

    for tournament in tournaments:
        existing = (
            await db.execute(
                select(Party).where(
                    Party.is_global == True,  # noqa: E712
                    Party.tournament_id == tournament.id,
                )
            )
        ).scalar_one_or_none()
        if existing:
            continue

        # Prefer "GLOBAL" as the invite code; fall back to a derived code if taken.
        code = "GLOBAL"
        code_taken = (
            await db.execute(select(Party).where(Party.invite_code == code))
        ).scalar_one_or_none()
        if code_taken:
            code = f"GL{str(tournament.id).replace('-', '')[:8].upper()}"[:10]

        db.add(
            Party(
                name=f"Global — {tournament.name}",
                invite_code=code,
                created_by=system_user.id,
                tournament_id=tournament.id,
                is_global=True,
            )
        )

    await db.commit()


async def auto_join_global_parties(db: AsyncSession, user_id: uuid.UUID) -> None:
    """Add a newly-created user to all existing global parties."""
    result = await db.execute(
        select(Party).where(Party.is_global == True)  # noqa: E712
    )
    for party in result.scalars().all():
        stmt = (
            pg_insert(PartyMember)
            .values(party_id=party.id, user_id=user_id, role="member")
            .on_conflict_do_nothing()
        )
        await db.execute(stmt)
