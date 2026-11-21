"""Markets and correct-score details derived from a scoreline probability grid."""

import numpy as np

GOAL_LINES = (0.5, 1.5, 2.5, 3.5, 4.5)
UI_GRID_GOALS = 6


def normalize(grid) -> np.ndarray:
    values = np.asarray(grid, dtype=float)
    if values.ndim != 2 or values.shape[0] != values.shape[1]:
        raise ValueError("A scoreline grid must be a square two-dimensional array.")
    if not np.isfinite(values).all() or (values < 0).any():
        raise ValueError("A scoreline grid must contain finite, non-negative probabilities.")
    total = float(values.sum())
    if total <= 0:
        raise ValueError("A scoreline grid must have positive total probability.")
    return values / total


def summarize_grid(grid, top_n: int = 10) -> dict:
    if top_n < 1:
        raise ValueError("top_n must be positive.")
    probabilities = normalize(grid)
    n = probabilities.shape[0]
    home_goals, away_goals = np.indices(probabilities.shape)
    total_goals = home_goals + away_goals
    counts = np.arange(n)
    ui_size = min(UI_GRID_GOALS + 1, n)
    order = np.argsort(probabilities, axis=None)[::-1][:top_n]
    top_scores = []
    for flat_index in order:
        home, away = divmod(int(flat_index), n)
        top_scores.append({"score": f"{home}-{away}", "p": float(probabilities[home, away])})
    visible_grid = probabilities[:ui_size, :ui_size]
    return {
        "exp_home": float((probabilities.sum(axis=1) * counts).sum()),
        "exp_away": float((probabilities.sum(axis=0) * counts).sum()),
        "exp_total": float((probabilities * total_goals).sum()),
        "over": {
            f"{line:g}": float(probabilities[total_goals > line].sum())
            for line in GOAL_LINES
        },
        "btts": float(probabilities[(home_goals > 0) & (away_goals > 0)].sum()),
        "top_scores": top_scores,
        "grid": [[round(float(value), 5) for value in row] for row in visible_grid],
        "grid_other": float(max(0.0, 1.0 - visible_grid.sum())),
        "full_grid": [[round(float(value), 5) for value in row] for row in probabilities],
    }
