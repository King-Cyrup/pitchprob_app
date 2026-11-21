"""Training data and Dixon-Coles predictions for UEFA national teams."""

import math
from pathlib import Path

import numpy as np
import pandas as pd
import penaltyblog as pb

from config import MODELS_DIR, TRAIN_WINDOW_DAYS, XI
from scoreline import summarize_grid

RESULTS_URL = "https://raw.githubusercontent.com/martj42/international_results/master/results.csv"
NL_NAME = "UEFA Nations League"
MIN_TRAIN_ROWS = 300
MAX_GOALS = 10
LAMBDA_MIN = 0.15
LAMBDA_MAX = 3.5


def clean_results(df: pd.DataFrame) -> pd.DataFrame:
    required = {"date", "home_team", "away_team", "home_score", "away_score", "tournament", "neutral"}
    missing = required.difference(df.columns)
    if missing:
        raise ValueError(f"International results are missing columns: {', '.join(sorted(missing))}")
    out = df.copy()
    out["date"] = pd.to_datetime(out["date"], errors="coerce")
    out["neutral"] = out["neutral"].astype(str).str.strip().str.upper().isin({"TRUE", "1", "YES"})
    out["home_score"] = pd.to_numeric(out["home_score"], errors="coerce")
    out["away_score"] = pd.to_numeric(out["away_score"], errors="coerce")
    out = out.dropna(subset=["date", "home_score", "away_score", "home_team", "away_team"])
    out["home_score"] = out["home_score"].astype(int)
    out["away_score"] = out["away_score"].astype(int)
    return out.sort_values("date", kind="stable").reset_index(drop=True)


def load_results(source: str | Path = RESULTS_URL) -> pd.DataFrame:
    return clean_results(pd.read_csv(source))


def uefa_teams(df: pd.DataFrame) -> set[str]:
    nations_league = df[df["tournament"] == NL_NAME]
    return set(nations_league["home_team"]) | set(nations_league["away_team"])


def training_rows(
    df: pd.DataFrame,
    as_of,
    uefa: set[str],
    window_days: int = TRAIN_WINDOW_DAYS,
) -> pd.DataFrame:
    cutoff = pd.Timestamp(as_of)
    rows = df[
        (df["date"] >= cutoff - pd.Timedelta(days=window_days))
        & (df["date"] < cutoff)
        & (df["home_team"].isin(uefa) | df["away_team"].isin(uefa))
    ][["date", "home_team", "away_team", "home_score", "away_score", "neutral"]].copy()
    rows["weight"] = np.where(rows["neutral"].astype(bool), 0.5, 1.0)
    neutral = rows[rows["neutral"].astype(bool)].rename(
        columns={
            "home_team": "away_team",
            "away_team": "home_team",
            "home_score": "away_score",
            "away_score": "home_score",
        }
    )
    return pd.concat([rows, neutral], ignore_index=True)


def recent_weight_share(rows: pd.DataFrame, as_of, xi: float = XI, years: int = 2) -> float:
    if rows.empty:
        return 0.0
    weights = pb.models.dixon_coles_weights(rows["date"], xi=xi) * rows["weight"].to_numpy()
    recent = (rows["date"] >= pd.Timestamp(as_of) - pd.Timedelta(days=365 * years)).to_numpy()
    total = float(weights.sum())
    return float(weights[recent].sum() / total) if total else 0.0


def fit_international(rows: pd.DataFrame, xi: float = XI):
    if len(rows) < MIN_TRAIN_ROWS:
        raise ValueError(f"Only {len(rows)} training rows (need {MIN_TRAIN_ROWS}).")
    weights = pb.models.dixon_coles_weights(rows["date"], xi=xi) * rows["weight"].to_numpy()
    model = pb.models.DixonColesGoalModel(
        rows["home_score"].to_numpy(),
        rows["away_score"].to_numpy(),
        rows["home_team"].to_numpy(),
        rows["away_team"].to_numpy(),
        weights=weights,
    )
    model.fit()
    return model


def team_rates(model, home: str, away: str) -> tuple[float, float]:
    params = model.params
    try:
        home_rate = math.exp(
            params["home_advantage"] + params[f"attack_{home}"] + params[f"defence_{away}"]
        )
        away_rate = math.exp(params[f"attack_{away}"] + params[f"defence_{home}"])
    except KeyError as missing:
        raise ValueError(f"Team not in the training data: {missing.args[0]}") from None
    return home_rate, away_rate


def dc_grid(home_rate: float, away_rate: float, rho: float, n: int = MAX_GOALS) -> np.ndarray:
    def poisson(goal_count: int, rate: float) -> float:
        return math.exp(-rate) * rate**goal_count / math.factorial(goal_count)

    grid = np.array([
        [poisson(home_goals, home_rate) * poisson(away_goals, away_rate) for away_goals in range(n)]
        for home_goals in range(n)
    ])
    adjustments = {
        (0, 0): 1 - home_rate * away_rate * rho,
        (0, 1): 1 + home_rate * rho,
        (1, 0): 1 + away_rate * rho,
        (1, 1): 1 - rho,
    }
    if min(adjustments.values()) > 0:
        for (home_goals, away_goals), factor in adjustments.items():
            grid[home_goals, away_goals] *= factor
    return grid / grid.sum()


def predict_match(model, home: str, away: str, neutral: bool = False) -> dict:
    home_rate, away_rate = team_rates(model, home, away)
    rho = model.params["rho"]
    home_rate = min(max(home_rate, LAMBDA_MIN), LAMBDA_MAX)
    away_rate = min(max(away_rate, LAMBDA_MIN), LAMBDA_MAX)
    grid = dc_grid(home_rate, away_rate, rho)
    if neutral:
        flipped_home, flipped_away = team_rates(model, away, home)
        flipped = dc_grid(
            min(max(flipped_home, LAMBDA_MIN), LAMBDA_MAX),
            min(max(flipped_away, LAMBDA_MIN), LAMBDA_MAX),
            rho,
        ).T
        grid = (grid + flipped) / 2
    home_goals, away_goals = np.indices(grid.shape)
    total_goals = home_goals + away_goals
    summary = summarize_grid(grid)
    return {
        "p_home": float(grid[home_goals > away_goals].sum()),
        "p_draw": float(grid[home_goals == away_goals].sum()),
        "p_away": float(grid[home_goals < away_goals].sum()),
        "p_over15": summary["over"]["1.5"],
        "p_over25": summary["over"]["2.5"],
        "p_btts": summary["btts"],
        "xg_home": summary["exp_home"],
        "xg_away": summary["exp_away"],
        "exp_total": summary["exp_total"],
        "over": summary["over"],
        "btts": summary["btts"],
        "top_scores": summary["top_scores"],
        "grid": summary["grid"],
        "grid_other": summary["grid_other"],
        "full_grid": summary["full_grid"],
    }


def train_nations_league(conn, as_of=None):
    as_of = pd.Timestamp(as_of or pd.Timestamp.now(tz="UTC").date()).tz_localize(None)
    rows = pd.read_sql_query("SELECT * FROM intl_matches ORDER BY date", conn)
    if rows.empty:
        raise ValueError("No international results are loaded; run `python cli.py load-international` first.")
    rows = rows.rename(columns={
        "home_team": "home_team",
        "away_team": "away_team",
        "home_score": "home_score",
        "away_score": "away_score",
    })
    rows["date"] = pd.to_datetime(rows["date"])
    rows["neutral"] = rows["neutral"].astype(bool)
    uefa = uefa_teams(rows)
    training = training_rows(rows, as_of, uefa)
    model = fit_international(training)
    share = recent_weight_share(training, as_of)
    model_path = MODELS_DIR / "UNL.pkl"
    model_path.parent.mkdir(parents=True, exist_ok=True)
    model.save(str(model_path))
    (MODELS_DIR / "UNL.trained_at").write_text(as_of.date().isoformat(), encoding="utf-8")
    print(f"  UNL: {len(training)} training rows; {share:.1%} of training weight from the last 730 days")
    return model, training, as_of


def load_nations_league_model():
    model_path = MODELS_DIR / "UNL.pkl"
    if not model_path.exists():
        return None, None
    stamp_path = MODELS_DIR / "UNL.trained_at"
    stamp = stamp_path.read_text(encoding="utf-8").strip() if stamp_path.exists() else ""
    return pb.models.DixonColesGoalModel.load(str(model_path)), stamp
