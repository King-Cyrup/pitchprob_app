"""Write probabilities for upcoming fixtures, and grade them once results are known."""
from datetime import datetime, timedelta, timezone
from config import LEAGUES, LOCK_MINUTES, seasons_to_load
from db import connect
from modeling import (baseline_probs, forecast, load_matches, load_model, log_loss, outcome_of, rps_1x2)


def make_predictions() -> None:
    now = datetime.now(timezone.utc)
    cutoff = now + timedelta(minutes=LOCK_MINUTES)
    with connect() as conn:
        for code in LEAGUES:
            model, trained_at = load_model(code)
            if model is None:
                print(f"  {code}: no trained model yet (run 'train' first)")
                continue
            fixtures = conn.execute(
                """SELECT * FROM fixtures WHERE league = ? AND status IN ('SCHEDULED', 'TIMED')
                   AND kickoff_utc > ? AND home IS NOT NULL AND away IS NOT NULL""",
                (code, cutoff.strftime("%Y-%m-%dT%H:%M:%SZ")),
            ).fetchall()
            locked = conn.execute(
                """SELECT COUNT(*) FROM fixtures WHERE league = ? AND status IN ('SCHEDULED', 'TIMED')
                   AND kickoff_utc <= ? AND home IS NOT NULL AND away IS NOT NULL""",
                (code, cutoff.strftime("%Y-%m-%dT%H:%M:%SZ")),
            ).fetchone()[0]
            done = skipped = 0
            for fx in fixtures:
                try:
                    f = forecast(model, fx["home"], fx["away"])
                except ValueError:
                    skipped += 1  # a team the model has never seen
                    continue
                conn.execute(
                    """INSERT INTO predictions (fd_match_id, created_at, model_trained_at, p_home, p_draw, p_away,
                                                p_over25, p_btts, xg_home, xg_away)
                       VALUES (:id, :now, :trained, :p_home, :p_draw, :p_away, :p_over25, :p_btts, :xg_home, :xg_away)
                       ON CONFLICT (fd_match_id) DO UPDATE SET
                         created_at = excluded.created_at, model_trained_at = excluded.model_trained_at,
                         p_home = excluded.p_home, p_draw = excluded.p_draw, p_away = excluded.p_away,
                         p_over25 = excluded.p_over25, p_btts = excluded.p_btts,
                         xg_home = excluded.xg_home, xg_away = excluded.xg_away""",
                    {"id": fx["fd_match_id"], "now": now.isoformat(), "trained": trained_at, **f},
                )
                done += 1
            note = f", {locked} locked (within {LOCK_MINUTES} min of kickoff)" if locked else ""
            print(f"  {code}: {done} predictions written, {skipped} skipped (team not in training data){note}")


def grade_predictions() -> None:
    """Score every prediction whose match now appears in the 'matches' table."""
    now = datetime.now(timezone.utc).isoformat()
    with connect() as conn:
        rows = conn.execute(
            """SELECT f.fd_match_id, f.league, f.kickoff_utc, p.p_home, p.p_draw, p.p_away, p.p_over25, p.p_btts,
                      m.home_goals, m.away_goals
               FROM predictions p
               JOIN fixtures f ON f.fd_match_id = p.fd_match_id
               JOIN matches m ON m.league = f.league AND m.season = f.season AND m.home = f.home AND m.away = f.away
               WHERE p.fd_match_id NOT IN (SELECT fd_match_id FROM grades)"""
        ).fetchall()
        count = 0
        for r in rows:
            history = load_matches(conn, r["league"], seasons_to_load())
            history = history[history["match_date"] < r["kickoff_utc"][:10]]
            if len(history) < 100:
                continue
            base = baseline_probs(history)
            oc = outcome_of(r["home_goals"], r["away_goals"])
            p3 = (r["p_home"], r["p_draw"], r["p_away"])
            over = r["home_goals"] + r["away_goals"] > 2
            btts = r["home_goals"] > 0 and r["away_goals"] > 0
            conn.execute(
                "INSERT INTO grades VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (r["fd_match_id"], r["home_goals"], r["away_goals"], oc,
                 log_loss(p3["HDA".index(oc)]), rps_1x2(p3, oc),
                 log_loss(r["p_over25"] if over else 1 - r["p_over25"]),
                 log_loss(r["p_btts"] if btts else 1 - r["p_btts"]),
                 log_loss(base["HDA".index(oc)]), now),
            )
            count += 1
        print(f"  {count} predictions graded")
