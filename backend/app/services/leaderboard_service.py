import uuid

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def recompute_party_leaderboard(
    db: AsyncSession,
    party_id: uuid.UUID,
    tournament_id: uuid.UUID,
) -> None:
    """
    Upsert leaderboard_snapshots for every member of party_id who has scored
    predictions in tournament_id.  Called by the sync worker after matches are
    scored; also callable on-demand.
    """
    sql = text("""
        INSERT INTO leaderboard_snapshots
            (party_id, user_id, tournament_id, total_points, exact_scores,
             predictions_made, rank, computed_at)
        SELECT
            pm.party_id,
            p.user_id,
            m.tournament_id,
            COALESCE(SUM(p.total_points), 0)                                    AS total_points,
            COALESCE(SUM(CASE WHEN p.points_exact > 0 THEN 1 ELSE 0 END), 0)   AS exact_scores,
            COUNT(p.id)                                                         AS predictions_made,
            RANK() OVER (
                PARTITION BY pm.party_id
                ORDER BY
                    SUM(p.total_points) DESC,
                    SUM(CASE WHEN p.points_exact > 0 THEN 1 ELSE 0 END) DESC
            )                                                                   AS rank,
            now()                                                               AS computed_at
        FROM party_members pm
        JOIN predictions   p  ON p.user_id  = pm.user_id
        JOIN matches       m  ON m.id        = p.match_id
        WHERE pm.party_id       = :party_id
          AND m.tournament_id   = :tournament_id
          AND p.scored_at IS NOT NULL
        GROUP BY pm.party_id, p.user_id, m.tournament_id
        ON CONFLICT (party_id, user_id, tournament_id) DO UPDATE SET
            total_points      = EXCLUDED.total_points,
            exact_scores      = EXCLUDED.exact_scores,
            predictions_made  = EXCLUDED.predictions_made,
            rank              = EXCLUDED.rank,
            computed_at       = EXCLUDED.computed_at
    """)
    await db.execute(sql, {"party_id": str(party_id), "tournament_id": str(tournament_id)})
    await db.commit()
