"""In-play probabilities from the pre-match goal rates. NOT VALIDATED: do not show to users until it has been tested on your own live data."""
import math
import numpy as np


def inplay_1x2(lam: float, mu: float, minute: int, home_goals: int, away_goals: int, max_goals: int = 12) -> dict:
    """Assumes goals arrive at a constant rate over 90 minutes (real rates rise late in matches, so this is only a first approximation)."""
    left = max(90 - minute, 0) / 90
    pm = lambda k, m: math.exp(-m) * m ** k / math.factorial(k)
    ph = np.array([pm(k, lam * left) for k in range(max_goals)]); pa = np.array([pm(k, mu * left) for k in range(max_goals)])
    grid = np.outer(ph, pa); grid /= grid.sum()
    i, j = np.indices(grid.shape)
    final = (i + home_goals) - (j + away_goals)
    return {"p_home": float(grid[final > 0].sum()), "p_draw": float(grid[final == 0].sum()), "p_away": float(grid[final < 0].sum())}
