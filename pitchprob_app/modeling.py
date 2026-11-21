"""Train Dixon-Coles models, turn their output into probabilities, and score them."""
import math
from datetime import datetime, timezone
import numpy as np
import pandas as pd
import penaltyblog as pb
from config import MODELS_DIR, TRAIN_WINDOW_DAYS, XI, seasons_to_load
from db import connect
from scoreline import summarize_grid

OUTCOMES = ("H", "D", "A")
CORNER_TOTAL_LINES = (7.5, 8.5, 9.5, 10.5, 11.5)
CORNER_TEAM_LINES = (2.5, 3.5, 4.5, 5.5, 6.5)


def load_matches(conn, league: str, seasons: list[str]) -> pd.DataFrame:
    marks = ",".join("?" * len(seasons))
    df = pd.read_sql_query(
        f"SELECT * FROM matches WHERE league = ? AND season IN ({marks}) ORDER BY match_date",
        conn, params=[league, *seasons],
    )
    df["match_date"] = pd.to_datetime(df["match_date"])
    return df


def fit_model(df: pd.DataFrame, xi: float = XI, window_days: int | None = TRAIN_WINDOW_DAYS):
    if df.empty:
        raise ValueError("Cannot fit a model without match history.")
    if window_days is not None:
        latest = df["match_date"].max()
        df = df[df["match_date"] >= latest - pd.Timedelta(days=window_days)]
    weights = pb.models.dixon_coles_weights(df["match_date"], xi=xi)
    model = pb.models.DixonColesGoalModel(
        df["home_goals"].values, df["away_goals"].values, df["home"].values, df["away"].values, weights=weights
    )
    model.fit()
    return model


def forecast(model, home: str, away: str) -> dict:
    """Probabilities for one match. Raises ValueError if a team was not in the training data."""
    prediction = model.predict(home, away, max_goals=15)
    grid = np.asarray(prediction.grid, dtype=float)
    details = summarize_grid(grid)
    p_home, p_draw, p_away = (float(x) for x in prediction.home_draw_away)
    return {
        "p_home": p_home, "p_draw": p_draw, "p_away": p_away,
        "p_over15": details["over"]["1.5"], "p_over25": details["over"]["2.5"],
        "p_btts": details["btts"], "btts": details["btts"],
        "xg_home": details["exp_home"], "xg_away": details["exp_away"],
        "exp_total": details["exp_total"], "over": details["over"],
        "top_scores": details["top_scores"], "grid": details["grid"], "grid_other": details["grid_other"],
        "full_grid": details["full_grid"],
    }


def recent_weight_share(df: pd.DataFrame, xi: float = XI, days: int = 730) -> float:
    if df.empty:
        return 0.0
    weights = pb.models.dixon_coles_weights(df["match_date"], xi=xi)
    recent = (df["match_date"] >= df["match_date"].max() - pd.Timedelta(days=days)).to_numpy()
    total = float(weights.sum())
    return float(weights[recent].sum() / total) if total else 0.0


def fit_corner_model(df: pd.DataFrame):
    rows = df.dropna(subset=["home_corners", "away_corners"]).copy()
    if len(rows) < 30:
        return None
    from config import USE_NB_CORNERS
    weights = pb.models.dixon_coles_weights(rows["match_date"], xi=XI)
    if USE_NB_CORNERS:
        # Step 5: negative binomial handles over-dispersion better than Poisson
        model = pb.models.NegativeBinomialGoalModel(
            rows["home_corners"].astype(int).values,
            rows["away_corners"].astype(int).values,
            rows["home"].values,
            rows["away"].values,
            weights=weights,
        )
    else:
        model = pb.models.PoissonGoalsModel(
            rows["home_corners"].astype(int).values,
            rows["away_corners"].astype(int).values,
            rows["home"].values,
            rows["away"].values,
            weights=weights,
        )
    model.fit()
    return model


def corner_forecast(model, home: str, away: str) -> dict:
    grid = np.asarray(model.predict(home, away, max_goals=30).grid, dtype=float)
    details = summarize_grid(grid)
    home_goals, away_goals = np.indices(grid.shape)
    total_goals = home_goals + away_goals
    return {
        "available": True,
        "expected": {
            "home": details["exp_home"],
            "away": details["exp_away"],
            "total": details["exp_total"],
        },
        "total_over": {
            f"{line:g}": float(grid[total_goals > line].sum() / grid.sum())
            for line in CORNER_TOTAL_LINES
        },
        "team_over": {
            side: {
                f"{line:g}": float(grid[goals > line].sum() / grid.sum())
                for line in CORNER_TEAM_LINES
            }
            for side, goals in (("home", home_goals), ("away", away_goals))
        },
    }


def load_corner_model(code: str):
    path = MODELS_DIR / f"corners_{code}.pkl"
    if not path.exists():
        return None
    from config import USE_NB_CORNERS
    if USE_NB_CORNERS:
        try:
            return pb.models.NegativeBinomialGoalModel.load(str(path))
        except Exception:
            pass
    return pb.models.PoissonGoalsModel.load(str(path))


def outcome_of(home_goals: int, away_goals: int) -> str:
    return "H" if home_goals > away_goals else "A" if home_goals < away_goals else "D"


# ---- scoring rules (lower is better) ----
def log_loss(p_event: float) -> float:
    """-ln(probability given to what actually happened)."""
    return -math.log(max(p_event, 1e-12))


def rps_1x2(probs: tuple[float, float, float], outcome: str) -> float:
    """Ranked probability score for the ordered outcomes Home, Draw, Away."""
    obs = [1.0 if o == outcome else 0.0 for o in OUTCOMES]
    cum_p, cum_o, total = 0.0, 0.0, 0.0
    for i in range(2):  # the last cumulative term is always 0
        cum_p += probs[i]
        cum_o += obs[i]
        total += (cum_p - cum_o) ** 2
    return total / 2


def baseline_probs(df: pd.DataFrame) -> tuple[float, float, float]:
    """The 'no model' forecast: how often home wins, draws and away wins happened in the training data."""
    outcomes = [outcome_of(h, a) for h, a in zip(df["home_goals"], df["away_goals"])]
    n = len(outcomes)
    return tuple(outcomes.count(o) / n for o in OUTCOMES)


def train_all() -> None:
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    from config import LEAGUES
    seasons = seasons_to_load()
    with connect() as conn:
        league_marks = ",".join("?" * len(LEAGUES))
        season_marks = ",".join("?" * len(seasons))
        stored = conn.execute(
            f"SELECT COUNT(*) FROM matches WHERE league IN ({league_marks}) AND season IN ({season_marks})",
            [*LEAGUES, *seasons],
        ).fetchone()[0]
        if stored == 0:
            raise SystemExit(
                "No finished matches are stored for the configured leagues and training seasons. "
                "Run `python cli.py load-history` first, then retry `python cli.py train`."
            )
        for code in LEAGUES:
            if LEAGUES[code].get("kind") == "national" or LEAGUES[code].get("pb_name") is None:
                continue
            df = load_matches(conn, code, seasons)
            if len(df) < 300:
                print(f"  {code}: only {len(df)} matches stored, skipping (need at least 300)")
                continue
            model = fit_model(df)
            model.save(str(MODELS_DIR / f"{code}.pkl"))
            (MODELS_DIR / f"{code}.trained_at").write_text(datetime.now(timezone.utc).isoformat())
            training = df[df["match_date"] >= df["match_date"].max() - pd.Timedelta(days=TRAIN_WINDOW_DAYS)]
            share = recent_weight_share(training)
            print(f"  {code}: trained on {len(training)} matches, {len(model.teams)} teams; "
                  f"{share:.1%} weight from the last 730 days")
            corner_model = fit_corner_model(df)
            if corner_model is None:
                print(f"  {code}: corner model unavailable (fewer than 30 matches with corner data)")
            else:
                corner_model.save(str(MODELS_DIR / f"corners_{code}.pkl"))
                corners = df.dropna(subset=["home_corners", "away_corners"])
                print(f"  {code}: trained corner model on {len(corners)} matches")
        if conn.execute("SELECT COUNT(*) FROM intl_matches").fetchone()[0]:
            from international import train_nations_league

            try:
                train_nations_league(conn)
            except ValueError as err:
                print(f"  UNL: {err}")


def home_advantage(model=None, code: str | None = None) -> float | None:
    """Return the fitted Dixon-Coles home advantage parameter for a model or league code."""
    if model is None:
        if code is None:
            return None
        model, _ = load_model(code)
    if model is None:
        return None
    params = getattr(model, "_params", None)
    if params is None or len(params) < 2:
        return None
    return float(params[-2])


def load_model(code: str):
    path = MODELS_DIR / f"{code}.pkl"
    if not path.exists():
        return None, None
    stamp = (MODELS_DIR / f"{code}.trained_at").read_text() if (MODELS_DIR / f"{code}.trained_at").exists() else ""
    return pb.models.DixonColesGoalModel.load(str(path)), stamp
