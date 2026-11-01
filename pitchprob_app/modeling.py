"""Train Dixon-Coles models, turn their output into probabilities, and score them."""
import math
from datetime import datetime, timezone
import numpy as np
import pandas as pd
import penaltyblog as pb
from config import MODELS_DIR, XI, seasons_to_load
from db import connect

OUTCOMES = ("H", "D", "A")


def load_matches(conn, league: str, seasons: list[str]) -> pd.DataFrame:
    marks = ",".join("?" * len(seasons))
    df = pd.read_sql_query(
        f"SELECT * FROM matches WHERE league = ? AND season IN ({marks}) ORDER BY match_date",
        conn, params=[league, *seasons],
    )
    df["match_date"] = pd.to_datetime(df["match_date"])
    return df


def fit_model(df: pd.DataFrame):
    weights = pb.models.dixon_coles_weights(df["match_date"], xi=XI)
    model = pb.models.DixonColesGoalModel(
        df["home_goals"].values, df["away_goals"].values, df["home"].values, df["away"].values, weights=weights
    )
    model.fit()
    return model


def forecast(model, home: str, away: str) -> dict:
    """Probabilities for one match. Raises ValueError if a team was not in the training data."""
    grid = model.predict(home, away)
    p_home, p_draw, p_away = (float(x) for x in grid.home_draw_away)
    return {
        "p_home": p_home, "p_draw": p_draw, "p_away": p_away,
        "p_over25": float(grid.total_goals("over", 2.5)), "p_btts": float(grid.btts_yes),
        "xg_home": float(grid.home_goal_expectation), "xg_away": float(grid.away_goal_expectation),
    }


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
            df = load_matches(conn, code, seasons)
            if len(df) < 300:
                print(f"  {code}: only {len(df)} matches stored, skipping (need at least 300)")
                continue
            model = fit_model(df)
            model.save(str(MODELS_DIR / f"{code}.pkl"))
            (MODELS_DIR / f"{code}.trained_at").write_text(datetime.now(timezone.utc).isoformat())
            print(f"  {code}: trained on {len(df)} matches, {len(model.teams)} teams")


def load_model(code: str):
    path = MODELS_DIR / f"{code}.pkl"
    if not path.exists():
        return None, None
    stamp = (MODELS_DIR / f"{code}.trained_at").read_text() if (MODELS_DIR / f"{code}.trained_at").exists() else ""
    return pb.models.DixonColesGoalModel.load(str(path)), stamp
