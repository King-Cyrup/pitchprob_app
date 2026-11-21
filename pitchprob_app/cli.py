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
                if LEAGUES.get(league, {}).get("kind") == "national":
                    names_by_league[league] = {
                        r["n"] for r in conn.execute(
                            """SELECT home_team AS n FROM intl_matches
                               WHERE tournament = 'UEFA Nations League'
                               UNION SELECT away_team FROM intl_matches
                               WHERE tournament = 'UEFA Nations League'"""
                        )
                    }
                else:
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
        intl = conn.execute("SELECT COUNT(*) AS n, MAX(date) AS latest FROM intl_matches").fetchone()
        print(f"International matches: {intl['n']} (latest {intl['latest'] or 'none'})")
        for table in ("fixtures", "predictions", "grades"):
            print(f"{table}: {conn.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0]}")
        print(f"Backtest rows: {conn.execute('SELECT COUNT(*) FROM backtest').fetchone()[0]}")


def teams(league: str | None) -> None:
    """Print the team names the model knows (names as written by football-data.co.uk)."""
    if league not in LEAGUES:
        raise SystemExit(f"Give a league code: python cli.py teams PL   (one of {', '.join(LEAGUES)})")
    with connect() as conn:
        if LEAGUES[league].get("kind") == "national":
            rows = conn.execute(
                """SELECT home_team AS n FROM intl_matches WHERE tournament = 'UEFA Nations League'
                   UNION SELECT away_team FROM intl_matches WHERE tournament = 'UEFA Nations League' ORDER BY n"""
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT home AS n FROM matches WHERE league = ? UNION SELECT away FROM matches WHERE league = ? ORDER BY n",
                (league, league)).fetchall()
    print(", ".join(r["n"] for r in rows))


def main() -> None:
    parser = argparse.ArgumentParser(description="PitchProb tools")
    parser.add_argument("command", choices=[
        "init-db", "check-access", "load-history", "sync-fixtures", "check-names", "train", "evaluate",
        "predict", "grade", "daily", "status", "teams", "report", "compare-recency", "load-international",
        "backtest", "compare", "market-check"])
    parser.add_argument("league", nargs="?", help="league code, used by 'teams' and 'report' commands")
    parser.add_argument("--old", default=None, help="old model version for 'compare' command")
    parser.add_argument("--new", default=None, help="new model version for 'compare' command")
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
        from sync_fixtures import load_international_results, sync_fixtures

        stages = [
            ("1/6 international results", load_international_results),
            ("2/6 club results", lambda: load_history(seasons_to_load()[-2:])),
            ("3/6 fixtures", sync_fixtures),
            ("4/6 train", train_all),
            ("5/6 predict", make_predictions),
            ("6/6 grade", grade_predictions),
        ]
        failed = 0
        errored = []
        for label, fn in stages:
            print(label)
            try:
                fn()
            except Exception:
                traceback.print_exc()
                failed += 1
                errored.append(label)
        if failed:
            raise SystemExit(
                f"{failed} stage(s) failed: {', '.join(errored)} — see errors above."
            )
    elif args.command == "report":
        from report import print_report
        print_report(args.league)
    elif args.command == "compare-recency":
        from evaluate import run_recency_compare
        run_recency_compare()
    elif args.command == "load-international":
        from sync_fixtures import load_international_results
        load_international_results()
    elif args.command == "backtest":
        from evaluate import run_backtest
        run_backtest()
    elif args.command == "compare":
        _run_compare(args)
    elif args.command == "market-check":
        _run_market_check()


def _run_compare(args) -> None:
    """Step 0 / V1: compare two model versions from the backtest table.

    Usage:  python cli.py compare --old dc --new dc_elo50
    Returns gain (old - new log loss), 95% interval, and the decision (adopt/shadow/reject).
    A self-comparison (--old dc --new dc) should print gain 0.000.
    """
    import json as _json
    import math as _math
    from decide import paired_gain, decide

    old_ver = args.old or "dc"
    new_ver = args.new or "dc"
    with connect() as conn:
        old_rows = conn.execute(
            "SELECT competition, match_date, home, away, actual_home, actual_away, forecast_json FROM backtest WHERE model_version = ?",
            (old_ver,),
        ).fetchall()
        new_rows = conn.execute(
            "SELECT competition, match_date, home, away, actual_home, actual_away, forecast_json FROM backtest WHERE model_version = ?",
            (new_ver,),
        ).fetchall()

    # Index new rows by (competition, match_date, home, away)
    new_index = {}
    for r in new_rows:
        key = (r["competition"], r["match_date"], r["home"], r["away"])
        new_index[key] = r

    losses_old, losses_new = [], []
    for r in old_rows:
        key = (r["competition"], r["match_date"], r["home"], r["away"])
        if key not in new_index:
            continue
        def _ll(row):
            fc = _json.loads(row["forecast_json"])
            ph, pd_, pa = fc["p_home"], fc["p_draw"], fc["p_away"]
            hg, ag = row["actual_home"], row["actual_away"]
            if hg > ag:
                p = ph
            elif hg < ag:
                p = pa
            else:
                p = pd_
            return -_math.log(max(p, 1e-12))
        losses_old.append(_ll(r))
        losses_new.append(_ll(new_index[key]))

    if not losses_old:
        print(f"No matched pairs found for versions '{old_ver}' and '{new_ver}'. Run 'python cli.py backtest' first.")
        return

    result = paired_gain(losses_old, losses_new)
    decision = decide(result)
    print(f"\nCompare  {old_ver!r}  vs  {new_ver!r}")
    print(f"  Matches  : {result['n']}")
    print(f"  Gain     : {result['gain']:+.4f}  (positive = {new_ver!r} is better)")
    print(f"  95% CI   : [{result['low']:+.4f}, {result['high']:+.4f}]")
    print(f"  Decision : {decision.upper()}")


def _run_market_check() -> None:
    """Step 1: compare the model's 1X2 probabilities against bookmaker closing odds.

    Reads closing-odds columns from the backtest table's forecast_json (mk_h, mk_d, mk_a).
    If those columns are absent, prints a message explaining how to add them.
    """
    import json as _json
    import math as _math
    import numpy as _np
    from market_check import devig, compare_with_market

    with connect() as conn:
        rows = conn.execute(
            "SELECT competition, actual_home, actual_away, forecast_json FROM backtest WHERE model_version = 'dc'"
        ).fetchall()

    # Check if any rows have market odds stored
    mkt_rows = [r for r in rows if _json.loads(r["forecast_json"] or "{}").get("mk_h") is not None]

    if not mkt_rows:
        print("No bookmaker closing odds found in the backtest table.")
        print("To enable the market check:")
        print("  1. Run: python -c \"import penaltyblog as pb; df = pb.scrapers.FootballData('ENG Premier League','2025-2026').get_fixtures(); print([c for c in df.columns if c.startswith(('avg','psc','psch','b365','max'))])\"")
        print("  2. If odds columns exist, re-run the backtest: python cli.py backtest")
        print("  3. The backtest pipeline will store mk_h/mk_d/mk_a in forecast_json when available.")
        return

    # Group by competition
    by_competition: dict[str, list] = {}
    for r in mkt_rows:
        by_competition.setdefault(r["competition"], []).append(r)

    for comp, comp_rows in sorted(by_competition.items()):
        model_p, market_p, results = [], [], []
        for r in comp_rows:
            fc = _json.loads(r["forecast_json"])
            ph, pd_, pa = fc["p_home"], fc["p_draw"], fc["p_away"]
            odds = _np.array([[fc["mk_h"], fc["mk_d"], fc["mk_a"]]])
            mkt = devig(odds)[0]
            hg, ag = r["actual_home"], r["actual_away"]
            outcome = 0 if hg > ag else 2 if hg < ag else 1
            model_p.append([ph, pd_, pa])
            market_p.append(mkt.tolist())
            results.append(outcome)
        df_out = compare_with_market(_np.array(model_p), _np.array(market_p), _np.array(results))
        print(f"\n{comp} (n={len(results)}):")
        print(df_out.to_string())


if __name__ == "__main__":
    main()
