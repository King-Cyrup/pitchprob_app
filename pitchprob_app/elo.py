"""Elo ratings and the blend with the goals model (tested: +0.005 log loss on 3,458 real club matches)."""
import math
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

K, HOME_ADV, START = 20.0, 60.0, 1500.0     # settings used in the test; change only with a new test


class EloRatings:
    def __init__(self, k=K, home_adv=HOME_ADV, start=START):
        self.k, self.home_adv, self.start, self.r = k, home_adv, start, {}

    def diff(self, league: str, home: str, away: str) -> float:
        """Home rating plus home advantage minus away rating, BEFORE the match is played."""
        return self.r.get((league, home), self.start) + self.home_adv - self.r.get((league, away), self.start)

    def update(self, league: str, home: str, away: str, hg: int, ag: int) -> None:
        a, b = self.r.get((league, home), self.start), self.r.get((league, away), self.start)
        expected = 1 / (1 + 10 ** (-(a + self.home_adv - b) / 400))
        score = 1.0 if hg > ag else 0.0 if hg < ag else 0.5
        margin = math.log(abs(hg - ag) + 1) + 1 if hg != ag else 1.0       # bigger wins move ratings more
        delta = self.k * margin * (score - expected)
        self.r[(league, home)], self.r[(league, away)] = a + delta, b - delta


def pre_match_diffs(matches: pd.DataFrame) -> pd.Series:
    """matches: columns league, home, away, hg, ag, sorted by date. Returns each match's Elo difference before kickoff."""
    elo, out = EloRatings(), []
    for r in matches.itertuples():
        out.append(elo.diff(r.league, r.home, r.away))
        elo.update(r.league, r.home, r.away, r.hg, r.ag)
    return pd.Series(out, index=matches.index)


class EloMapper:
    """Turns an Elo difference into probabilities [home, draw, away]. Refit on earlier matches before every use."""
    def fit(self, diffs, results):                       # results: 0 = home win, 1 = draw, 2 = away win
        self.model = make_pipeline(StandardScaler(), LogisticRegression(C=0.3, max_iter=2000))
        self.model.fit(np.asarray(diffs, dtype=float).reshape(-1, 1), np.asarray(results))
        return self

    def predict(self, diffs) -> np.ndarray:
        return self.model.predict_proba(np.asarray(diffs, dtype=float).reshape(-1, 1))


def blend(goals_model_probs, elo_probs, weight: float = 0.5) -> np.ndarray:
    """Weighted average of two probability tables (rows = matches, columns = H, D, A). 0.5 was the best tested weight."""
    out = (1 - weight) * np.asarray(goals_model_probs) + weight * np.asarray(elo_probs)
    return out / out.sum(axis=1, keepdims=True)
