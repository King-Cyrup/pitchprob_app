"""Monte Carlo season simulation: how likely is each final position?"""
import numpy as np


def simulate(table: dict, fixtures: list[dict], n_sims: int = 10000, seed: int = 0) -> dict:
    """table: {team: {"points": int, "gd": int, "gf": int}} today.
    fixtures: remaining matches [{"home", "away", "grid": 2-D array of scoreline probabilities (row = home goals)}].
    Returns {team: array of length n_teams with P(final position = 1..n)}. Ties: points, goal difference, goals for."""
    rng = np.random.default_rng(seed)
    teams = list(table)
    idx = {t: i for i, t in enumerate(teams)}
    pts = np.array([table[t]["points"] for t in teams], dtype=float)[None, :].repeat(n_sims, 0)
    gd = np.array([table[t]["gd"] for t in teams], dtype=float)[None, :].repeat(n_sims, 0)
    gf = np.array([table[t]["gf"] for t in teams], dtype=float)[None, :].repeat(n_sims, 0)
    for fx in fixtures:
        grid = np.asarray(fx["grid"], dtype=float)
        flat = rng.choice(grid.size, size=n_sims, p=(grid / grid.sum()).ravel())
        hg, ag = np.divmod(flat, grid.shape[1])
        h, a = idx[fx["home"]], idx[fx["away"]]
        pts[:, h] += np.where(hg > ag, 3, np.where(hg == ag, 1, 0)); pts[:, a] += np.where(ag > hg, 3, np.where(hg == ag, 1, 0))
        gd[:, h] += hg - ag; gd[:, a] += ag - hg; gf[:, h] += hg; gf[:, a] += ag
    score = pts * 1e6 + gd * 1e3 + gf                       # larger = better; fine for realistic totals
    order = np.argsort(-score, axis=1, kind="stable")        # team indices from first place to last
    position = np.empty_like(order)
    np.put_along_axis(position, order, np.arange(order.shape[1])[None, :].repeat(n_sims, 0), axis=1)
    return {t: np.bincount(position[:, idx[t]], minlength=len(teams)) / n_sims for t in teams}
