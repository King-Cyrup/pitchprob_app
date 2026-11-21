"""Walk-forward checks for club models and requested recency settings."""
import json
import math
from datetime import date, datetime, timezone

import numpy as np
import pandas as pd

from config import LEAGUES, XI, season_label, seasons_to_load
from db import connect
from modeling import (
    baseline_probs,
    fit_corner_model,
    fit_model,
    forecast,
    load_matches,
    outcome_of,
    recent_weight_share,
)
BLOCK_DAYS = 28
RECENCY_WINDOWS = (730, 1095, 1460)
RECENCY_XIS = (0.001, 0.0019, 0.003)
BACKTEST_MARKETS = ("1x2", "over15", "over25", "btts")
CORNER_TOTAL_LINES = (7.5, 8.5, 9.5, 10.5, 11.5)
CORNER_TEAM_LINES = (2.5, 3.5, 4.5, 5.5, 6.5)


def _market_loss(p_valid: float, actual: bool) -> float:
    """Log loss for a single binary market: -ln(probability of the actual outcome)."""
    p = min(max(p_valid, 1e-12), 1.0 - 1e-12)
    return -math.log(p if actual else 1 - p)


def _previous_season() -> str:
    start = int(season_label(date.today())[:4]) - 1
    return f"{start}-{start + 1}"


def _validation_status(n: int, model_loss: float, baseline_loss: float) -> str:
    if n >= 200 and model_loss < baseline_loss:
        return "validated"
    if n >= 30:
        return "experimental"
    return "unavailable"


def _market_baseline(df: pd.DataFrame, market: str):
    """Constant (no-model) baseline for a market.

    For 1X2 this is the historical home/draw/away frequency of the training data
    (a vector of three probabilities). For the two-sided goal markets it is the
    single frequency that always happened.
    """
    if market == "1x2":
        outcomes = [outcome_of(h, a) for h, a in zip(df["home_goals"], df["away_goals"])]
        n = float(len(outcomes))
        return [outcomes.count(o) / n for o in ("H", "D", "A")]
    if market == "over15":
        return float((df["home_goals"] + df["away_goals"] > 1).mean())
    if market == "over25":
        return float((df["home_goals"] + df["away_goals"] > 2).mean())
    if market == "btts":
        return float(((df["home_goals"] > 0) & (df["away_goals"] > 0)).mean())
    if market == "correct_score":
        counts: dict[tuple[int, int], int] = {}
        for h, a in zip(df["home_goals"], df["away_goals"]):
            counts[(int(h), int(a))] = counts.get((int(h), int(a)), 0) + 1
        total = float(sum(counts.values()))
        best = max(counts.values()) / total
        return best
    if market == "corners_total":
        total = df["home_corners"].fillna(0).astype(int) + df["away_corners"].fillna(0).astype(int)
        return float((total > 9.5).mean())
    raise ValueError(f"Unknown market: {market}")


def evaluate_league(
    conn,
    code: str,
    test_season: str,
    window_days: int | None = None,
    xi: float | None = None,
) -> dict | None:
    from config import TRAIN_WINDOW_DAYS, XI as _XI

    window_days = TRAIN_WINDOW_DAYS if window_days is None else window_days
    xi = _XI if xi is None else xi
    df = load_matches(conn, code, seasons_to_load())
    test = df[df["season"] == test_season]
    if test.empty:
        return None

    results = []
    shares = []
    start = test["match_date"].min()
    while start <= test["match_date"].max():
        end = start + pd.Timedelta(days=BLOCK_DAYS)
        train = df[df["match_date"] < start]
        block = test[(test["match_date"] >= start) & (test["match_date"] < end)]
        if window_days is not None and not train.empty:
            train = train[train["match_date"] >= train["match_date"].max() - pd.Timedelta(days=window_days)]
        start = end
        if len(train) < 300 or block.empty:
            continue
        model = fit_model(train, xi=xi, window_days=None)
        base = baseline_probs(train)
        shares.append(recent_weight_share(train, xi=xi))
        for row in block.itertuples():
            try:
                prediction = forecast(model, row.home, row.away)
            except ValueError:
                continue
            actual = outcome_of(row.home_goals, row.away_goals)
            probabilities = (prediction["p_home"], prediction["p_draw"], prediction["p_away"])
            results.append({
                "model_logloss": log_loss(probabilities["HDA".index(actual)]),
                "base_logloss": log_loss(base["HDA".index(actual)]),
                "model_rps": rps_1x2(probabilities, actual),
                "base_rps": rps_1x2(base, actual),
            })

    if not results:
        return None
    frame = pd.DataFrame(results)
    return {
        "competition": code,
        "n": len(frame),
        "logloss_model": float(frame["model_logloss"].mean()),
        "logloss_baseline": float(frame["base_logloss"].mean()),
        "rps_model": float(frame["model_rps"].mean()),
        "rps_baseline": float(frame["base_rps"].mean()),
        "recent_weight_share": float(np.mean(shares)) if shares else 0.0,
    }


def log_loss(p_event: float) -> float:
    """-ln(probability given to what actually happened)."""
    return -math.log(max(p_event, 1e-12))


def rps_1x2(probs: tuple[float, float, float], outcome: str) -> float:
    """Ranked probability score for the ordered outcomes Home, Draw, Away."""
    obs = [1.0 if o == outcome else 0.0 for o in ("H", "D", "A")]
    cum_p, cum_o, total = 0.0, 0.0, 0.0
    for i in range(2):
        cum_p += probs[i]
        cum_o += obs[i]
        total += (cum_p - cum_o) ** 2
    return total / 2


def run_evaluation() -> None:
    previous = _previous_season()
    print(f"Walk-forward test on season {previous} (refit every {BLOCK_DAYS} days)")
    print(f"{'league':6} {'n':>5} {'logloss model':>14} {'baseline':>9} {'RPS model':>10} {'baseline':>9}")
    with connect() as conn:
        for code, competition in LEAGUES.items():
            if competition.get("kind") == "national" or competition.get("pb_name") is None:
                continue
            result = evaluate_league(conn, code, previous)
            if not result:
                print(f"{code:6} no data")
                continue
            verdict = "PASS" if (
                result["logloss_model"] < result["logloss_baseline"]
                and result["rps_model"] < result["rps_baseline"]
            ) else "CHECK"
            print(
                f"{code:6} {result['n']:5d} {result['logloss_model']:14.4f} "
                f"{result['logloss_baseline']:9.4f} {result['rps_model']:10.4f} "
                f"{result['rps_baseline']:9.4f}  {verdict}"
            )


def run_recency_compare() -> None:
    """Step 4: compare recency window + decay settings on the previous season.

    Prints a table of log-loss per setting so the user can decide whether to change config.py.
    """
    from config import TRAIN_WINDOW_DAYS as CFG_WINDOW, XI as CFG_XI

    previous = _previous_season()
    print(f"Recency comparison on season {previous} (refit every {BLOCK_DAYS} days)")
    print(f"{'window':>8} {'xi':>7} {'logloss':>8} {'delta vs current':>18} {'730d weight':>12}")

    # Collect losses per (window, xi) across all club leagues
    settings: dict[tuple, list] = {}
    with connect() as conn:
        for code, competition in LEAGUES.items():
            if competition.get("kind") == "national" or competition.get("pb_name") is None:
                continue
            for window in RECENCY_WINDOWS:
                for xi in RECENCY_XIS:
                    result = evaluate_league(conn, code, previous, window_days=window, xi=xi)
                    if result is None:
                        continue
                    key = (window, xi)
                    settings.setdefault(key, []).append(result["logloss_model"])

    current_loss: float | None = None
    rows_summary = []
    with connect() as conn2:
        for (window, xi), losses in sorted(settings.items()):
            mean_loss = float(np.mean(losses))
            shares = []
            for code, competition in LEAGUES.items():
                if competition.get("kind") == "national" or competition.get("pb_name") is None:
                    continue
                df = load_matches(conn2, code, seasons_to_load())
                if not df.empty:
                    shares.append(recent_weight_share(df, xi=xi, days=730))
            mean_share = float(np.mean(shares)) if shares else 0.0
            rows_summary.append((window, xi, mean_loss, mean_share))
            if window == CFG_WINDOW and abs(xi - CFG_XI) < 1e-6:
                current_loss = mean_loss

    best_loss = min(r[2] for r in rows_summary) if rows_summary else None
    for window, xi, mean_loss, mean_share in rows_summary:
        marker = " ← current" if (window == CFG_WINDOW and abs(xi - CFG_XI) < 1e-6) else ""
        delta = f"{mean_loss - current_loss:+.4f}" if current_loss is not None else "    n/a"
        print(f"{window:>8} {xi:>7.4f} {mean_loss:>8.4f} {delta:>18} {mean_share:>11.1%}{marker}")

    if current_loss is not None and best_loss is not None:
        gap = current_loss - best_loss
        verdict = "KEEP (gap < 0.005)" if gap < 0.005 else "REVIEW (gap >= 0.005)"
        print(f"\nCurrent vs best: {gap:.4f}  →  {verdict}")


def _intl_df(conn) -> pd.DataFrame:
    rows = conn.execute("SELECT * FROM intl_matches").fetchall()
    return pd.DataFrame([dict(r) for r in rows])


def _unl_frame(conn, since: str = "2024-09-01") -> pd.DataFrame:
    """National-team results in the same shape the club backtest expects.

    The whole history is kept so the model can be trained on it; `since` marks the
    first match that is *forecast*. Matches before that are training data only.
    """
    df = _intl_df(conn)
    df["date"] = pd.to_datetime(df["date"])
    df["home_goals"] = df["home_score"]
    df["away_goals"] = df["away_score"]
    df["neutral"] = df["neutral"].astype(bool)
    df = df.rename(columns={"home_team": "home", "away_team": "away"})
    df = df[["date", "home", "away", "home_goals", "away_goals", "neutral", "tournament"]].rename(
        columns={"date": "match_date"})
    df.attrs["forecast_from"] = pd.Timestamp(since)
    return df


def _run_backtest_league(conn, code: str, df: pd.DataFrame) -> None:
    """Walk-forward: refit every 28 days, store backtest rows and market_validation."""
    df = df.sort_values("match_date").reset_index(drop=True)
    is_national = code == "UNL"
    corner_baseline = None

    if not is_national:
        total = df["home_corners"].fillna(0).astype(int) + df["away_corners"].fillna(0).astype(int)
        corner_baseline = float((total > 9.5).mean())

    uefa = None
    forecast_from = df.attrs.get("forecast_from")
    if is_national:
        from international import uefa_teams
        uefa = uefa_teams(df.rename(columns={"home": "home_team", "away": "away_team"}))
        df = df[df["home"].isin(uefa) | df["away"].isin(uefa)]

    start = df["match_date"].min()
    if forecast_from is not None:
        # start walking forward at the test window; everything before it is training data
        start = max(start, forecast_from)
    all_future: list[dict] = []

    # Step 2: pre-compute Elo differences across the whole sorted df (no leakage: each diff
    # is computed before the match it belongs to).
    if not is_national:
        from elo import pre_match_diffs as _elo_diffs, EloMapper as _EloMapper, blend as _elo_blend
        import numpy as _np_elo
        _elo_df = df[["match_date", "home", "away", "home_goals", "away_goals"]].copy()
        _elo_df = _elo_df.rename(columns={"home_goals": "hg", "away_goals": "ag"})
        _elo_df["league"] = code
        _elo_diffs_series = _elo_diffs(_elo_df[["league", "home", "away", "hg", "ag"]])
    else:
        _EloMapper = None
        _elo_blend = None
        _elo_diffs_series = None

    while start <= df["match_date"].max():
        end = start + pd.Timedelta(days=BLOCK_DAYS)
        past = df[df["match_date"] < start]
        future = df[(df["match_date"] >= start) & (df["match_date"] < end)]
        start = end
        if future.empty:
            continue
        if forecast_from is not None:
            # only forecast matches from the window we test on; earlier ones stay training data
            future = future[future["match_date"] >= forecast_from]
            if future.empty:
                continue
        if is_national:
            from international import fit_international, training_rows
            as_of = past["match_date"].max() + pd.Timedelta(days=1)
            rows = training_rows(
                past.rename(columns={
                    "match_date": "date", "home": "home_team", "away": "away_team",
                    "home_goals": "home_score", "away_goals": "away_score",
                }),
                as_of, uefa)
            if len(rows) < 300:
                continue
            model = fit_international(rows)
        else:
            if len(past) < 300:
                continue
            model = fit_model(past, xi=XI)
        # the corner model is refitted on the same past-only data, so the corner
        # forecast cannot see the match it is forecasting
        block_corner_model = None
        if not is_national:
            block_corner_model = fit_corner_model(past)
        # Step 2: fit EloMapper on past matches for this block
        block_elo_mapper = None
        if not is_national and _elo_diffs_series is not None and len(past) >= 100:
            try:
                from elo import EloMapper as _EloMapper2
                past_idx = past.index
                _diffs_past = _elo_diffs_series.loc[past_idx].to_numpy()
                _res_past = np.where(
                    past["home_goals"].to_numpy() > past["away_goals"].to_numpy(), 0,
                    np.where(past["home_goals"].to_numpy() < past["away_goals"].to_numpy(), 2, 1)
                ).astype(int)
                block_elo_mapper = _EloMapper2().fit(_diffs_past, _res_past)
            except Exception:
                block_elo_mapper = None

        for row in future.itertuples():
            # Step 2: get pre-match Elo diff for this row
            block_elo_diff = None
            if block_elo_mapper is not None and _elo_diffs_series is not None:
                try:
                    block_elo_diff = _elo_diffs_series.loc[row.Index:row.Index].to_numpy()
                except Exception:
                    block_elo_diff = None
            try:
                if is_national:
                    from international import predict_match
                    pred = predict_match(model, row.home, row.away, bool(getattr(row, "neutral", False)))
                else:
                    pred = forecast(model, row.home, row.away)
            except (ValueError, KeyError):
                continue
            record = {
                "match_date": row.match_date, "home": row.home, "away": row.away,
                "actual_home": int(row.home_goals), "actual_away": int(row.away_goals),
                "p_home": pred["p_home"], "p_draw": pred["p_draw"], "p_away": pred["p_away"],
                "p_over15": pred.get("p_over15"), "p_over25": pred["p_over25"], "p_btts": pred["p_btts"],
                "grid": pred["grid"], "top_scores": pred["top_scores"], "grid_other": pred["grid_other"],
                "p_corners_total_over_9_5": None,
            }
            if block_corner_model is not None:
                try:
                    g = np.asarray(block_corner_model.predict(row.home, row.away, max_goals=30).grid, dtype=float)
                    g = g / g.sum()
                    total_goals = np.add.outer(np.arange(g.shape[0]), np.arange(g.shape[1]))
                    record["p_corners_total_over_9_5"] = float(g[total_goals > 9.5].sum())
                except ValueError:
                    pass
            all_future.append(record)
            forecast_json = json.dumps({
                "p_home": pred["p_home"], "p_draw": pred["p_draw"], "p_away": pred["p_away"],
                "p_over15": pred.get("p_over15"), "p_over25": pred["p_over25"], "p_btts": pred["p_btts"],
                "top_scores": pred["top_scores"], "grid": pred["grid"], "grid_other": pred["grid_other"],
            }, separators=(",", ":"))
            conn.execute(
                """INSERT OR REPLACE INTO backtest (competition, match_date, home, away, actual_home, actual_away, forecast_json, created_at, model_version)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (code, row.match_date.strftime("%Y-%m-%d"), row.home, row.away,
                 int(row.home_goals), int(row.away_goals), forecast_json, datetime.now(timezone.utc).isoformat(), "dc"),
            )
            # Step 2: store Elo-blend (dc_elo50) if elo_mapper is fitted
            if block_elo_mapper is not None and block_elo_diff is not None:
                try:
                    elo_probs = block_elo_mapper.predict(block_elo_diff)
                    dc_probs = np.array([[pred["p_home"], pred["p_draw"], pred["p_away"]]])
                    blended = _elo_blend(dc_probs, elo_probs)
                    elo_forecast_json = json.dumps({
                        "p_home": float(blended[0, 0]), "p_draw": float(blended[0, 1]), "p_away": float(blended[0, 2]),
                        "p_over15": pred.get("p_over15"), "p_over25": pred["p_over25"], "p_btts": pred["p_btts"],
                        "top_scores": pred["top_scores"], "grid": pred["grid"], "grid_other": pred["grid_other"],
                    }, separators=(",", ":"))
                    conn.execute(
                        """INSERT OR REPLACE INTO backtest (competition, match_date, home, away, actual_home, actual_away, forecast_json, created_at, model_version)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (code, row.match_date.strftime("%Y-%m-%d"), row.home, row.away,
                         int(row.home_goals), int(row.away_goals), elo_forecast_json,
                         datetime.now(timezone.utc).isoformat(), "dc_elo50"),
                    )
                except Exception:
                    pass

    if not all_future:
        print("    no forecastable matches")
        return
    fdf = pd.DataFrame(all_future)

    # ---- binary markets ----
    column_for_market = {"over15": "p_over15", "over25": "p_over25", "btts": "p_btts"}
    for market in ("over15", "over25", "btts"):
        if market == "over15":
            actual = (fdf["actual_home"] + fdf["actual_away"] > 1).to_numpy()
        elif market == "over25":
            actual = (fdf["actual_home"] + fdf["actual_away"] > 2).to_numpy()
        else:
            actual = ((fdf["actual_home"] > 0) & (fdf["actual_away"] > 0)).to_numpy()
        p = fdf[column_for_market[market]].to_numpy(dtype=float)
        loss_m = float(np.mean([_market_loss(p[i], bool(actual[i])) for i in range(len(p))]))
        loss_b = float(np.mean([_market_loss(_market_baseline(df, market), bool(actual[i])) for i in range(len(p))]))
        n = len(p)
        status = _validation_status(n, loss_m, loss_b)
        conn.execute(
            """INSERT OR REPLACE INTO market_validation (competition, market, n, model_loss, baseline_loss, status, computed_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (code, market, n, loss_m, loss_b, status, datetime.now(timezone.utc).isoformat()),
        )
        print(f"    {market:12} model {loss_m:.4f} baseline {loss_b:.4f} -> {status}")

    # 1x2
    probs = np.column_stack([fdf["p_home"], fdf["p_draw"], fdf["p_away"]])
    actual_idx = np.array([("H", "D", "A").index(outcome_of(h, a)) for h, a in zip(fdf["actual_home"], fdf["actual_away"])])
    base = _market_baseline(df, "1x2")
    loss_m = float(np.mean([-math.log(probs[i, j]) for i, j in enumerate(actual_idx)]))
    loss_b = float(np.mean([-math.log(base[j]) for j in actual_idx]))
    n = len(p)
    status = _validation_status(n, loss_m, loss_b)
    conn.execute(
        """INSERT OR REPLACE INTO market_validation (competition, market, n, model_loss, baseline_loss, status, computed_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (code, "1x2", n, loss_m, loss_b, status, datetime.now(timezone.utc).isoformat()),
    )
    print(f"    1x2          model {loss_m:.4f} baseline {loss_b:.4f} -> {status}")

    # correct_score: the model's probability for the score that happened, against a
    # baseline that always gives the overall frequency of that exact score.
    counts: dict[tuple[int, int], int] = {}
    for record in all_future:
        key = (record["actual_home"], record["actual_away"])
        counts[key] = counts.get(key, 0) + 1
    total = float(sum(counts.values()))
    ll_model = 0.0
    ll_baseline = 0.0
    n_sc = 0
    for record in all_future:
        h, a = record["actual_home"], record["actual_away"]
        grid = record["grid"]
        if h >= len(grid) or a >= len(grid[h]):
            continue
        ll_model -= math.log(max(grid[h][a], 1e-12))
        ll_baseline -= math.log(max(counts[(h, a)] / total, 1e-12))
        n_sc += 1
    if n_sc:
        ll_model /= n_sc
        ll_baseline /= n_sc
        status = _validation_status(n_sc, ll_model, ll_baseline)
        conn.execute(
            """INSERT OR REPLACE INTO market_validation (competition, market, n, model_loss, baseline_loss, status, computed_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (code, "correct_score", n_sc, ll_model, ll_baseline, status, datetime.now(timezone.utc).isoformat()),
        )
        print(f"    correct_score {ll_model:.4f} baseline {ll_baseline:.4f} -> {status}")

    # corners_total (clubs only)
    if not is_national and corner_baseline is not None:
        idx = [i for i, r in enumerate(all_future) if r["p_corners_total_over_9_5"] is not None]
        if idx:
            pvals = np.array([all_future[i]["p_corners_total_over_9_5"] for i in idx])
            act = np.array([(all_future[i]["actual_home"] + all_future[i]["actual_away"]) > 9.5 for i in idx])
            loss_m = float(np.mean([_market_loss(pvals[i], bool(act[i])) for i in range(len(idx))]))
            loss_b = corner_baseline
            status = _validation_status(len(idx), loss_m, loss_b)
            conn.execute(
                """INSERT OR REPLACE INTO market_validation (competition, market, n, model_loss, baseline_loss, status, computed_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (code, "corners_total_9.5", len(idx), loss_m, loss_b, status, datetime.now(timezone.utc).isoformat()),
            )
            print(f"    corners_total_9.5  {loss_m:.4f} baseline {loss_b:.4f} -> {status}")

    # Step 3: Platt calibration for over15/over25/btts (applied retroactively on all_future)
    if not is_national and len(all_future) >= 50:
        try:
            from recalibrate import PlattCalibrator
            platt_markets = {
                "over15": ("p_over15", lambda r: (r["actual_home"] + r["actual_away"]) > 1),
                "over25": ("p_over25", lambda r: (r["actual_home"] + r["actual_away"]) > 2),
                "btts": ("p_btts", lambda r: r["actual_home"] > 0 and r["actual_away"] > 0),
            }
            half = len(all_future) // 2
            for mkt, (col, actual_fn) in platt_markets.items():
                raw_all = np.array([r[col] for r in all_future if r[col] is not None], dtype=float)
                y_all = np.array([actual_fn(r) for r in all_future if r[col] is not None], dtype=bool)
                if len(raw_all) < 50:
                    continue
                # train on first half, evaluate on second half (time-ordered)
                cal = PlattCalibrator().fit(raw_all[:half], y_all[:half])
                cal_p = cal.transform(raw_all[half:])
                y_test = y_all[half:]
                loss_platt = float(np.mean([_market_loss(float(cal_p[i]), bool(y_test[i])) for i in range(len(y_test))]))
                loss_raw = float(np.mean([_market_loss(float(raw_all[half + i]), bool(y_test[i])) for i in range(len(y_test))]))
                loss_b_platt = float(np.mean([_market_loss(_market_baseline(df, mkt), bool(y_test[i])) for i in range(len(y_test))]))
                status_platt = _validation_status(len(y_test), loss_platt, loss_b_platt)
                conn.execute(
                    """INSERT OR REPLACE INTO market_validation (competition, market, n, model_loss, baseline_loss, status, computed_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (code, f"{mkt}_platt", len(y_test), loss_platt, loss_b_platt, status_platt, datetime.now(timezone.utc).isoformat()),
                )
                print(f"    {mkt}_platt    raw {loss_raw:.4f} -> platt {loss_platt:.4f} baseline {loss_b_platt:.4f} -> {status_platt}")
        except Exception as _platt_err:
            print(f"    Platt calibration skipped: {_platt_err}")


def run_backtest() -> None:
    """Walk-forward backtest, refit every 28 days, storing results in `backtest` and
    computing per-market losses in `market_validation`."""
    with connect() as conn:
        for code, competition in LEAGUES.items():
            if code == "UNL":
                df = _unl_frame(conn)
            elif competition.get("kind") == "national":
                continue
            else:
                df = load_matches(conn, code, seasons_to_load())
            if df.empty:
                print(f"  {code}: no data for backtest")
                continue
            print(f"\n{code} — {competition['name']}: backtest")
            _run_backtest_league(conn, code, df)
