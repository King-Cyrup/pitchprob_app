"""Refresh results, fixtures, forecasts, and model artifacts for deployment."""
from config import FOOTBALL_DATA_TOKEN, LEAGUES, seasons_to_load
from db import connect
from load_history import load_history
from modeling import MODELS_DIR, train_all
from predict import grade_predictions, make_predictions
from sync_fixtures import sync_fixtures


def main() -> None:
    if not FOOTBALL_DATA_TOKEN:
        raise SystemExit(
            "FOOTBALL_DATA_TOKEN is missing. Add it as a GitHub Actions repository secret."
        )

    seasons = seasons_to_load()
    print("1/5 Refreshing historical results")
    load_history(seasons[-2:], strict=True)
    print("2/5 Refreshing upcoming fixtures")
    sync_fixtures(strict=True)
    print("3/5 Training league models")
    train_all()

    missing_models = [code for code in LEAGUES if not (MODELS_DIR / f"{code}.pkl").is_file()]
    if missing_models:
        raise RuntimeError(f"Model artifacts are missing for: {', '.join(missing_models)}")

    print("4/5 Writing forecasts")
    make_predictions()
    print("5/5 Grading completed predictions")
    grade_predictions()

    with connect() as conn:
        matches = conn.execute("SELECT COUNT(*) FROM matches").fetchone()[0]
        fixtures = conn.execute("SELECT COUNT(*) FROM fixtures").fetchone()[0]
        predictions = conn.execute("SELECT COUNT(*) FROM predictions").fetchone()[0]
        grades = conn.execute("SELECT COUNT(*) FROM grades").fetchone()[0]
    print(
        f"Refresh complete: {matches} results, {fixtures} fixtures, "
        f"{predictions} forecasts, {grades} graded matches."
    )


if __name__ == "__main__":
    main()
