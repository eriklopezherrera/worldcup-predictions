"""
Grant (or revoke) admin rights for a user, looked up by email or username.

Usage:
    cd backend
    python -m app.workers.make_admin you@example.com
    python -m app.workers.make_admin you@example.com --revoke
"""

import asyncio
import sys

import structlog
from sqlalchemy import or_, select

from app.database import AsyncSessionLocal
from app.models.user import User

log = structlog.get_logger()


async def set_admin(identifier: str, is_admin: bool) -> None:
    async with AsyncSessionLocal() as db:
        user = (
            await db.execute(
                select(User).where(
                    or_(User.email == identifier, User.username == identifier)
                )
            )
        ).scalar_one_or_none()
        if user is None:
            log.error("make_admin.user_not_found", identifier=identifier)
            sys.exit(1)

        user.is_admin = is_admin
        await db.commit()
        log.info("make_admin.done", username=user.username, is_admin=is_admin)


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if a != "--revoke"]
    if len(args) != 1:
        print(__doc__)
        sys.exit(1)
    asyncio.run(set_admin(args[0], "--revoke" not in sys.argv))
