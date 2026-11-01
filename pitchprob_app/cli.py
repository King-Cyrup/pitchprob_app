"""Command line entry point:  python cli.py <command>"""
import argparse
import traceback
from config import LEAGUES, seasons_to_load
from db import connect, init_db
from names import load_aliases, resolve, suggest


def check_names() -> None:
    """List football-data.org teams we could not match to a model team name."""
    with connect() as conn:
        rows = conn.execute(
            "SELECT league, home_fd AS fd, home AS model FROM fixtures UNION SELECT league, away_fd, away FROM fixtures"
        ).fetchall()
        aliases = load_aliases()
        names_by_league: dict[str, set[str]] = {}
        bad = set()
        for row in rows:
            league, fd = row["league"], row["fd"]
            if row["model"] is not None:
                continue
            if league not in names_by_league:
                names_by_league[league] = {
                    r["n"] for r in conn.execute(
                        "SELECT home AS n FROM matches WHERE league = ? UNION SELECT away FROM matches WHERE league = ?",
                        (league, league),
                    )
                }
            if resolve(fd, None, names_by_league[league], aliases) is None:
                bad.add((league, fd))
        bad = sorted(bad)
        if not bad:
            print("All team names are matched.")
            return
        print("Unmatched teams. Add one line per team to data/team_aliases.csv  (fd_name,model_name):\n")
        for league, fd in bad:
            names = {r["n"] for r in conn.execute(
                "SELECT home AS n FROM matches WHERE league = ? UNION SELECT away FROM matches WHERE league = ?",
                (league, league))}
            print(f"  [{league}] {fd}   closest model names: {suggest(fd, names) or 'none found'}")


def status() -> None:
    """Show what is stored: a quick health check of every step."""
    with connect() as conn:
        print("Finished matches stored (league, season, count):")
        for r in conn.execute("SELECT league, season, COUNT(*) AS n FROM matches GROUP BY league, season ORDER BY league, season"):
            print(f"  {r['league']:4} {r['season']}  {r['n']}")
        for table in ("fixtures", "predictions", "grades"):
            print(f"{table}: {conn.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0]}")


def teams(league: str | None) -> None:
    """Print the team names the model knows (names as written by football-data.co.uk)."""
    if league not in LEAGUES:
        raise SystemExit(f"Give a league code: python cli.py teams PL   (one of {', '.join(LEAGUES)})")
    with connect() as conn:
        rows = conn.execute(
            "SELECT home AS n FROM matches WHERE league = ? UNION SELECT away FROM matches WHERE league = ? ORDER BY n",
            (league, league)).fetchall()
    print(", ".join(r["n"] for r in rows))


def main() -> None:
    parser = argparse.ArgumentParser(description="PitchProb tools")
    parser.add_argument("command", choices=[
        "init-db", "check-access", "load-history", "sync-fixtures", "check-names", "train", "evaluate", "predict",
        "grade", "daily", "status", "teams", "report"])
    parser.add_argument("league", nargs="?", help="league code, used by 'teams' and 'report' commands")
    args = parser.parse_args()
    init_db()
    if args.command == "init-db":
        print("Database ready.")
    elif args.command == "check-access":
        from sync_fixtures import check_access; check_access()
    elif args.command == "status":
        status()
    elif args.command == "teams":
        teams(args.league)
    elif args.command == "load-history":
        from load_history import load_history; load_history()
    elif args.command == "sync-fixtures":
        from sync_fixtures import sync_fixtures; sync_fixtures()
    elif args.command == "check-names":
        check_names()
    elif args.command == "train":
        from modeling import train_all; train_all()
    elif args.command == "evaluate":
        from evaluate import run_evaluation; run_evaluation()
    elif args.command == "predict":
        from predict import make_predictions; make_predictions()
    elif args.command == "grade":
        from predict import grade_predictions; grade_predictions()
    elif args.command == "daily":
        from load_history import load_history
        from modeling import train_all
        from predict import grade_predictions, make_predictions
        from sync_fixtures import sync_fixtures

        stages = [
            ("1/5 results",  lambda: load_history(seasons_to_load()[-2:])),
            ("2/5 fixtures", sync_fixtures),
            ("3/5 train",    train_all),
            ("4/5 predict",  make_predictions),
            ("5/5 grade",    grade_predictions),
        ]
        failed = 0
        for label, fn in stages:
            print(label)
            try:
                fn()
            except Exception:
                traceback.print_exc()
                failed += 1
        if failed:
            raise SystemExit(f"{failed} stage(s) failed — see errors above.")
    elif args.command == "report":
        from report import print_report
        print_report(args.league)


if __name__ == "__main__":
    main()
