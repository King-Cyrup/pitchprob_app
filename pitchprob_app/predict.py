"""Write forecasts for upcoming fixtures and grade them after results are available."""

import json
from datetime import datetime, timedelta, timezone

from config import LEAGUES, LOCK_MINUTES, USE_ELO_BLEND, USE_PLATT, ELO_BLEND_WEIGHT, seasons_to_load
from db import connect
from modeling import (
    baseline_probs,
    corner_forecast,
    load_corner_model,
    load_matches,
    load_model,
    log_loss,
    outcome_of,
    rps_1x2,
)

NO_CORNERS = {"available": False, "reason": "No corner data for this competition"}


def _forecast_for(code: str, fixture, model):
    if LEAGUES[code].get("kind") == "national":
        from international import predict_match

        return predict_match(model, fixture["home"], fixture["away"], bool(fixture["neutral"]))
    from modeling import forecast

    return forecast(model, fixture["home"], fixture["away"])


def make_predictions() -> None:
    now = datetime.now(timezone.utc)
    cutoff = now + timedelta(minutes=LOCK_MINUTES)
    with connect() as conn:
        for code, competition in LEAGUES.items():
            if competition.get("kind") == "national":
                from international import load_nations_league_model

                model, trained_at = load_nations_league_model()
            else:
                model, trained_at = load_model(code)
            if model is None:
                print(f"  {code}: no trained model yet (run 'load-international' and 'train' first)")
                continue
            fixtures = conn.execute(
                """SELECT f.*, COALESCE(fm.neutral, 0) AS neutral, fm.stage
                   FROM fixtures f
                   LEFT JOIN fixture_metadata fm ON fm.fd_match_id = f.fd_match_id
                   WHERE f.league = ? AND f.status IN ('SCHEDULED', 'TIMED')
                     AND f.kickoff_utc > ? AND f.home IS NOT NULL AND f.away IS NOT NULL""",
                (code, cutoff.strftime("%Y-%m-%dT%H:%M:%SZ")),
            ).fetchall()
            locked = conn.execute(
                """SELECT COUNT(*) FROM fixtures WHERE league = ? AND status IN ('SCHEDULED', 'TIMED')
                   AND kickoff_utc <= ? AND home IS NOT NULL AND away IS NOT NULL""",
                (code, cutoff.strftime("%Y-%m-%dT%H:%M:%SZ")),
            ).fetchone()[0]
            corner_model = load_corner_model(code) if competition.get("kind") == "club" and code != "CL" else None
            
            # Step 2: if Elo blend is enabled and this is a club league, prepare EloMapper
            elo_mapper = None
            elo_ratings = None
            if USE_ELO_BLEND and competition.get("kind") == "club":
                try:
                    from elo import EloRatings, EloMapper, blend
                    matches_df = load_matches(conn, code, seasons_to_load())
                    if len(matches_df) >= 100:
                        elo_ratings = EloRatings()
                        diffs, res = [], []
                        for r in matches_df.itertuples():
                            diffs.append(elo_ratings.diff(code, r.home, r.away))
                            res.append(0 if r.home_goals > r.away_goals else 2 if r.home_goals < r.away_goals else 1)
                            elo_ratings.update(code, r.home, r.away, r.home_goals, r.away_goals)
                        import numpy as np
                        elo_mapper = EloMapper().fit(np.array(diffs), np.array(res))
                except Exception as _e:
                    elo_mapper = None

            # Step 3: if Platt calibration is enabled, prepare calibrators from backtest
            platt_calibrators = {}
            if USE_PLATT and competition.get("kind") == "club":
                try:
                    from recalibrate import PlattCalibrator
                    import numpy as np
                    bt_rows = conn.execute(
                        "SELECT forecast_json, actual_home, actual_away FROM backtest WHERE competition = ? AND model_version = 'dc'",
                        (code,)
                    ).fetchall()
                    if len(bt_rows) >= 50:
                        for mkt, (col, act_fn) in {
                            "over15": ("p_over15", lambda r: (r["actual_home"] + r["actual_away"]) > 1),
                            "over25": ("p_over25", lambda r: (r["actual_home"] + r["actual_away"]) > 2),
                            "btts": ("p_btts", lambda r: r["actual_home"] > 0 and r["actual_away"] > 0),
                        }.items():
                            p_vals, acts = [], []
                            for br in bt_rows:
                                fj = json.loads(br["forecast_json"] or "{}")
                                if col in fj and fj[col] is not None:
                                    p_vals.append(float(fj[col]))
                                    acts.append(act_fn(br))
                            if len(p_vals) >= 50:
                                platt_calibrators[mkt] = PlattCalibrator().fit(np.array(p_vals), np.array(acts))
                except Exception:
                    platt_calibrators = {}

            written = skipped = 0
            for fixture in fixtures:
                try:
                    prediction = _forecast_for(code, fixture, model)
                except ValueError as err:
                    print(f"  {code}: {fixture['home']} v {fixture['away']}: no forecast ({err})")
                    skipped += 1
                    continue

                model_ver = "dc"
                # Apply Elo blend if active
                if elo_mapper is not None and elo_ratings is not None:
                    try:
                        import numpy as np
                        d_val = np.array([elo_ratings.diff(code, fixture["home"], fixture["away"])])
                        elo_p = elo_mapper.predict(d_val)
                        dc_p = np.array([[prediction["p_home"], prediction["p_draw"], prediction["p_away"]]])
                        from elo import blend
                        blended = blend(dc_p, elo_p, weight=ELO_BLEND_WEIGHT)
                        prediction["p_home"] = float(blended[0, 0])
                        prediction["p_draw"] = float(blended[0, 1])
                        prediction["p_away"] = float(blended[0, 2])
                        model_ver = "dc_elo50"
                    except Exception:
                        pass

                # Apply Platt calibration if active
                if platt_calibrators:
                    try:
                        import numpy as np
                        if "over15" in platt_calibrators and prediction.get("p_over15") is not None:
                            prediction["p_over15"] = float(platt_calibrators["over15"].transform(np.array([prediction["p_over15"]]))[0])
                        if "over25" in platt_calibrators and prediction.get("p_over25") is not None:
                            prediction["p_over25"] = float(platt_calibrators["over25"].transform(np.array([prediction["p_over25"]]))[0])
                        if "btts" in platt_calibrators and prediction.get("p_btts") is not None:
                            prediction["p_btts"] = float(platt_calibrators["btts"].transform(np.array([prediction["p_btts"]]))[0])
                    except Exception:
                        pass

                corners = NO_CORNERS
                if corner_model is not None:
                    try:
                        corners = corner_forecast(corner_model, fixture["home"], fixture["away"])
                    except ValueError as err:
                        corners = {"available": False, "reason": f"Corner forecast unavailable: {err}"}
                markets = {
                    "over": prediction["over"],
                    "btts": prediction["btts"],
                    "top_scores": prediction["top_scores"],
                    "grid": prediction["grid"],
                    "grid_other": prediction["grid_other"],
                    "full_grid": prediction["full_grid"],
                }
                conn.execute(
                    """INSERT INTO predictions (fd_match_id, created_at, model_trained_at, p_home, p_draw, p_away,
                                                p_over25, p_btts, xg_home, xg_away, p_over15, markets_json, corners_json, model_version)
                       VALUES (:id, :now, :trained, :p_home, :p_draw, :p_away, :p_over25, :p_btts,
                               :xg_home, :xg_away, :p_over15, :markets, :corners, :model_version)
                       ON CONFLICT (fd_match_id) DO UPDATE SET
                         created_at = excluded.created_at, model_trained_at = excluded.model_trained_at,
                         p_home = excluded.p_home, p_draw = excluded.p_draw, p_away = excluded.p_away,
                         p_over15 = excluded.p_over15, p_over25 = excluded.p_over25,
                         p_btts = excluded.p_btts, xg_home = excluded.xg_home, xg_away = excluded.xg_away,
                         markets_json = excluded.markets_json, corners_json = excluded.corners_json,
                         model_version = excluded.model_version""",
                    {
                        "id": fixture["fd_match_id"],
                        "now": now.isoformat(),
                        "trained": trained_at or "",
                        **prediction,
                        "markets": json.dumps(markets, separators=(",", ":"), allow_nan=False),
                        "corners": json.dumps(corners, separators=(",", ":"), allow_nan=False),
                        "model_version": model_ver,
                    },
                )
                written += 1
            lock_note = f", {locked} inside the prediction cutoff" if locked else ""
            print(f"  {code}: {written} forecasts written, {skipped} unavailable{lock_note}")


def _grade_one(conn, fixture, prediction, home_goals: int, away_goals: int, trained_history) -> None:
    now = datetime.now(timezone.utc).isoformat()
    outcome = outcome_of(home_goals, away_goals)
    probabilities = (prediction["p_home"], prediction["p_draw"], prediction["p_away"])
    baseline = baseline_probs(trained_history)
    over15 = home_goals + away_goals > 1
    over25 = home_goals + away_goals > 2
    btts = home_goals > 0 and away_goals > 0
    conn.execute(
        """INSERT OR IGNORE INTO grades
           (fd_match_id, home_goals, away_goals, outcome, logloss_1x2, rps_1x2,
            logloss_over25, logloss_btts, base_logloss_1x2, graded_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            fixture["fd_match_id"], home_goals, away_goals, outcome,
            log_loss(probabilities["HDA".index(outcome)]), rps_1x2(probabilities, outcome),
            log_loss(prediction["p_over25"] if over25 else 1 - prediction["p_over25"]),
            log_loss(prediction["p_btts"] if btts else 1 - prediction["p_btts"]),
            log_loss(baseline["HDA".index(outcome)]), now,
        ),
    )
    market_losses = {
        "over15": log_loss(prediction["p_over15"] if over15 else 1 - prediction["p_over15"])
        if prediction["p_over15"] is not None else None,
        "over25": log_loss(prediction["p_over25"] if over25 else 1 - prediction["p_over25"]),
        "btts": log_loss(prediction["p_btts"] if btts else 1 - prediction["p_btts"]),
    }
    try:
        markets = json.loads(prediction["markets_json"] or "{}")
        full_grid = markets.get("full_grid", [])
        if home_goals < len(full_grid) and away_goals < len(full_grid[home_goals]):
            actual_probability = full_grid[home_goals][away_goals]
            market_losses["correct_score"] = log_loss(actual_probability)
    except (TypeError, ValueError, json.JSONDecodeError):
        markets = {}
    for market, loss in market_losses.items():
        if loss is not None:
            conn.execute(
                """INSERT OR REPLACE INTO market_grades (fd_match_id, market, model_loss, graded_at)
                   VALUES (?, ?, ?, ?)""",
                (fixture["fd_match_id"], market, loss, now),
            )


def grade_predictions() -> None:
    """Grade club forecasts by season and Nations League forecasts by teams/date."""
    with connect() as conn:
        rows = conn.execute(
            """SELECT f.*, p.p_home, p.p_draw, p.p_away, p.p_over15, p.p_over25, p.p_btts,
                      p.markets_json, p.corners_json
               FROM predictions p JOIN fixtures f ON f.fd_match_id = p.fd_match_id
               WHERE f.league != 'UNL' AND p.fd_match_id NOT IN (SELECT fd_match_id FROM grades)
               ORDER BY f.kickoff_utc"""
        ).fetchall()
        graded = 0
        for row in rows:
            fixture = dict(row)
            history = load_matches(conn, fixture["league"], seasons_to_load())
            actual = conn.execute(
                """SELECT home_goals, away_goals FROM matches
                   WHERE league = ? AND season = ? AND home = ? AND away = ?""",
                (fixture["league"], fixture["season"], fixture["home"], fixture["away"]),
            ).fetchone()
            if actual is None:
                continue
            history = history[history["match_date"] < fixture["kickoff_utc"][:10]]
            if len(history) < 100:
                continue
            _grade_one(conn, fixture, row, actual["home_goals"], actual["away_goals"], history)
            graded += 1

        national_rows = conn.execute(
            """SELECT f.*, p.p_home, p.p_draw, p.p_away, p.p_over15, p.p_over25, p.p_btts,
                      p.markets_json, p.corners_json
               FROM predictions p JOIN fixtures f ON f.fd_match_id = p.fd_match_id
               WHERE f.league = 'UNL' AND f.fd_match_id NOT IN (SELECT fd_match_id FROM grades)
               ORDER BY f.kickoff_utc"""
        ).fetchall()
        national_graded = 0
        for row in national_rows:
            fixture = dict(row)
            day = fixture["kickoff_utc"][:10]
            actual = conn.execute(
                """SELECT home_score, away_score FROM intl_matches
                   WHERE tournament = 'UEFA Nations League'
                     AND home_team = ? AND away_team = ?
                     AND date BETWEEN date(?, '-1 day') AND date(?, '+1 day')
                   ORDER BY ABS(julianday(date) - julianday(?)) LIMIT 1""",
                (fixture["home"], fixture["away"], day, day, day),
            ).fetchone()
            if actual is None:
                continue
            training = load_matches(conn, "PL", seasons_to_load())
            if len(training) < 100:
                # The grade table's baseline fields are legacy 1X2 metrics; use the
                # international history as the forecast baseline for this competition.
                international_history = conn.execute(
                    """SELECT home_score, away_score FROM intl_matches
                       WHERE date < ? AND tournament = 'UEFA Nations League'""",
                    (day,),
                ).fetchall()
                if not international_history:
                    continue
                import pandas as pd

                training = pd.DataFrame([
                    {
                        "home_goals": item["home_score"],
                        "away_goals": item["away_score"],
                    }
                    for item in international_history
                ])
            _grade_one(conn, fixture, row, actual["home_score"], actual["away_score"], training)
            national_graded += 1
        print(f"  {graded} club forecasts and {national_graded} Nations League forecasts graded")
