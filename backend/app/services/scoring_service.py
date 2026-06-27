import uuid
from typing import Optional


def _direction(h: int, a: int) -> str:
    if h > a:
        return "home"
    if a > h:
        return "away"
    return "draw"


def compute_points(
    predicted_home: int,
    predicted_away: int,
    actual_home: int,
    actual_away: int,
) -> tuple[int, int]:
    """Group-stage scoring. Returns (points_result, points_exact).

    points_result: 2 if predicted result direction matches actual, else 0.
    points_exact:  3 if predicted scoreline matches actual exactly, else 0.
    """

    points_result = (
        2 if _direction(predicted_home, predicted_away) == _direction(actual_home, actual_away) else 0
    )
    points_exact = 3 if predicted_home == actual_home and predicted_away == actual_away else 0
    return points_result, points_exact


def compute_points_knockout(
    predicted_home: int,
    predicted_away: int,
    predicted_advancing_team_id: Optional[uuid.UUID],
    actual_home: int,
    actual_away: int,
    winner_team_id: Optional[uuid.UUID],
) -> tuple[int, int, int]:
    """Knockout-stage scoring. Returns (points_result, points_exact, points_advancing).

    Scores are compared against the recorded scoreline, which is the score at the
    end of extra time; a penalty shootout is recorded as a draw and only resolves
    ``winner_team_id``.

    points_result:    1 if predicted result direction matches actual, else 0.
    points_exact:     2 if predicted scoreline matches actual exactly, else 0.
    points_advancing: 2 if the predicted advancing team is the one that advanced.

    The advancing pick is stored on the prediction at submission time (inferred
    from a decisive scoreline, or chosen explicitly for a predicted draw), so
    this function is agnostic to how it was set.
    """

    points_result = (
        1 if _direction(predicted_home, predicted_away) == _direction(actual_home, actual_away) else 0
    )
    points_exact = 2 if predicted_home == actual_home and predicted_away == actual_away else 0
    points_advancing = (
        2
        if predicted_advancing_team_id is not None
        and winner_team_id is not None
        and predicted_advancing_team_id == winner_team_id
        else 0
    )
    return points_result, points_exact, points_advancing


KNOCKOUT_STAGES = frozenset(
    {"round_of_32", "round_of_16", "quarter_final", "semi_final", "third_place", "final"}
)


def is_knockout_stage(stage: str) -> bool:
    return stage in KNOCKOUT_STAGES
