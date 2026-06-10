def compute_points(
    predicted_home: int,
    predicted_away: int,
    actual_home: int,
    actual_away: int,
) -> tuple[int, int]:
    """Returns (points_result, points_exact).

    points_result: 2 if predicted result direction matches actual, else 0.
    points_exact:  3 if predicted scoreline matches actual exactly, else 0.
    """

    def _direction(h: int, a: int) -> str:
        if h > a:
            return "home"
        if a > h:
            return "away"
        return "draw"

    points_result = (
        2 if _direction(predicted_home, predicted_away) == _direction(actual_home, actual_away) else 0
    )
    points_exact = 3 if predicted_home == actual_home and predicted_away == actual_away else 0
    return points_result, points_exact
