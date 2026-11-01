"""Walk-forward test: pretend it is the past, forecast each block of matches using only earlier matches."""
import numpy as np
import pandas as pd
from config import LEAGUES, season_label, seasons_to_load
from datetime import date
from db import connect
from modeling import baseline_probs, fit_model, forecast, load_matches, log_loss, outcome_of, rps_1x2

BLOCK_DAYS = 28


def evaluate_league(conn, code: str, test_season: str) -> dict | None:
    df = load_matches(conn, code, seasons_to_load())
    test = df[df["season"] == test_season]
    if test.empty:
        return None
    rows = []
    start = test["match_date"].min()
    end_all = test["match_date"].max()
    while start <= end_all:
        end = start + pd.Timedelta(days=BLOCK_DAYS)
        train = df[df["match_date"] < start]
        block = test[(test["match_date"] >= start) & (test["match_date"] < end)]
        start = end
        if len(train) < 300 or block.empty:
            continue
        model = fit_model(train)
        base = baseline_probs(train)
        for r in block.itertuples():
            try:
                f = forecast(model, r.home, r.away)
            except ValueError:  # team not in the training data (e.g. just promoted)
                continue
            oc = outcome_of(r.home_goals, r.away_goals)
            p3 = (f["p_home"], f["p_draw"], f["p_away"])
            over = (r.home_goals + r.away_goals) > 2
            btts = r.home_goals > 0 and r.away_goals > 0
            rows.append({
                "ll_model": log_loss(p3["HDA".index(oc)]), "ll_base": log_loss(base["HDA".index(oc)]),
                "rps_model": rps_1x2(p3, oc), "rps_base": rps_1x2(base, oc),
                "ll_over_model": log_loss(f["p_over25"] if over else 1 - f["p_over25"]),
                "ll_btts_model": log_loss(f["p_btts"] if btts else 1 - f["p_btts"]),
                "over": over, "btts": btts,
            })
    if not rows:
        return None
    r = pd.DataFrame(rows)
    over_rate, btts_rate = r["over"].mean(), r["btts"].mean()  # simple 'always the average' baselines
    return {
        "league": code, "matches": len(r),
        "logloss_model": r["ll_model"].mean(), "logloss_base": r["ll_base"].mean(),
        "rps_model": r["rps_model"].mean(), "rps_base": r["rps_base"].mean(),
        "over25_logloss_model": r["ll_over_model"].mean(),
        "over25_logloss_base": float(-(over_rate * np.log(over_rate) + (1 - over_rate) * np.log(1 - over_rate))),
        "btts_logloss_model": r["ll_btts_model"].mean(),
        "btts_logloss_base": float(-(btts_rate * np.log(btts_rate) + (1 - btts_rate) * np.log(1 - btts_rate))),
    }


def run_evaluation() -> None:
    previous = f"{int(season_label(date.today())[:4]) - 1}-{int(season_label(date.today())[:4])}"
    print(f"Walk-forward test on season {previous} (refit every {BLOCK_DAYS} days)")
    print(f"{'league':6} {'n':>5} {'logloss model':>14} {'baseline':>9} {'RPS model':>10} {'baseline':>9}")
    with connect() as conn:
        for code in LEAGUES:
            res = evaluate_league(conn, code, previous)
            if not res:
                print(f"{code:6} no data"); continue
            verdict = "PASS" if res["logloss_model"] < res["logloss_base"] and res["rps_model"] < res["rps_base"] else "FAIL"
            print(f"{code:6} {res['matches']:5d} {res['logloss_model']:14.4f} {res['logloss_base']:9.4f} "
                  f"{res['rps_model']:10.4f} {res['rps_base']:9.4f}  {verdict}")
            print(f"       over 2.5: model {res['over25_logloss_model']:.4f} vs constant {res['over25_logloss_base']:.4f}"
                  f" | btts: model {res['btts_logloss_model']:.4f} vs constant {res['btts_logloss_base']:.4f}")
