"""Tests for the match-details API shape and the helpers behind it."""
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config, db, scoreline  # noqa: E402


@pytest.fixture()
def env(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "t.db")
    db.init_db()
    return tmp_path


def _kickoff(offset_days: int = 1) -> str:
    return (datetime.now(timezone.utc) + timedelta(days=offset_days)).strftime("%Y-%m-%dT%H:%M:%SZ")


def _store_match(conn, *, home="Arsenal", away="Chelsea", home_goals=2, away_goals=1,
                 home_corners=7, away_corners=3, season=None, date="2026-08-20"):
    season = season or config.season_label(datetime.now(timezone.utc).date())
    conn.execute(
        """INSERT OR REPLACE INTO matches
           (league, season, match_date, home, away, home_goals, away_goals, home_corners, away_corners)
           VALUES ('PL', ?, ?, ?, ?, ?, ?, ?, ?)""",
        (season, date, home, away, home_goals, away_goals, home_corners, away_corners),
    )


def test_scoreline_grid_sums_to_one_with_grid_other():
    grid = [[0.1] * 7 for _ in range(7)]
    summary = scoreline.summarize_grid(grid)
    assert len(summary["grid"]) == 7 and len(summary["grid"][0]) == 7
    # each cell is rounded to 5 decimals, so 49 cells can drift by a little
    assert sum(sum(row) for row in summary["grid"]) + summary["grid_other"] == pytest.approx(1.0, abs=1e-3)
    over = [summary["over"][key] for key in ("0.5", "1.5", "2.5", "3.5", "4.5")]
    assert over == sorted(over, reverse=True)


def test_match_details_shape_for_a_club_match(env, monkeypatch):
    """The details endpoint must return every block the tabs read."""
    from fastapi.testclient import TestClient
    import app as webapp

    monkeypatch.delenv("APP_PASSWORD", raising=False)
    kickoff = _kickoff()
    season = config.season_label(datetime.now(timezone.utc).date())
    with db.connect() as conn:
        conn.execute(
            """INSERT INTO fixtures VALUES
               (7101, 'PL', ?, ?, 'TIMED', 'Arsenal FC', 'Chelsea FC', 'Arsenal', 'Chelsea', ?)""",
            (season, kickoff, kickoff),
        )
        conn.execute(
            """INSERT INTO predictions
               (fd_match_id, created_at, model_trained_at, p_home, p_draw, p_away,
                p_over25, p_btts, xg_home, xg_away, p_over15, markets_json)
               VALUES (7101, ?, ?, 0.48, 0.27, 0.25, 0.55, 0.52, 1.7, 1.1, 0.7, ?)""",
            (kickoff, kickoff, json.dumps({
                "over": {"0.5": 1.0, "1.5": 0.7, "2.5": 0.55, "3.5": 0.05, "4.5": 0.0},
                "btts": 0.52,
                "top_scores": [{"score": "1-1", "p": 0.118}, {"score": "2-1", "p": 0.09}],
                "grid": [[0.1] * 7 for _ in range(7)],
                "grid_other": 0.16,
            })),
        )

    client = TestClient(webapp.app)
    response = client.get("/api/matches/7101")
    assert response.status_code == 200
    details = response.json()

    # the blocks the four tabs read
    assert details["competition"]["code"] == "PL"
    assert details["home"] == {"name": "Arsenal", "badge_url": None}
    assert details["away"] == {"name": "Chelsea", "badge_url": None}
    assert details["forecast"]["pick"] == "H"
    assert details["forecast"]["lead_points"] == 21
    assert details["goals"]["over"]["2.5"] == 0.55
    assert details["goals"]["exp_total"] == pytest.approx(2.8, abs=1e-6)
    assert len(details["correct_score"]["top"]) == 2
    assert len(details["correct_score"]["grid"]) == 7
    assert details["correct_score"]["grid_other"] == 0.16
    assert details["result"] is None
    assert set(details["validation"]) >= {"1x2", "over15", "over25", "btts", "correct_score"}
    # context for the Form and H2H tab
    assert "form_home" in details["context"]
    assert "h2h" in details["context"]
    # a club match has corners
    assert details["corners"]["available"] is True


def test_match_details_reports_unavailable_corners_for_national_teams(env, monkeypatch):
    """A competition without corner data returns available: false, not an error."""
    from fastapi.testclient import TestClient
    import app as webapp

    monkeypatch.delenv("APP_PASSWORD", raising=False)
    kickoff = _kickoff()
    season = config.season_label(datetime.now(timezone.utc).date())
    with db.connect() as conn:
        conn.execute(
            """INSERT INTO fixtures VALUES
               (7102, 'UNL', ?, ?, 'TIMED', 'England', 'Croatia', 'England', 'Croatia', ?)""",
            (season, kickoff, kickoff),
        )

    client = TestClient(webapp.app)
    details = client.get("/api/matches/7102")
    assert details.status_code == 200
    corners = details.json()["corners"]
    assert corners["available"] is False
    assert corners["reason"]
    # no zeros are invented for a competition without data
    assert "expected" not in corners


def test_match_details_without_a_forecast_explains_why(env, monkeypatch):
    from fastapi.testclient import TestClient
    import app as webapp

    monkeypatch.delenv("APP_PASSWORD", raising=False)
    kickoff = _kickoff()
    season = config.season_label(datetime.now(timezone.utc).date())
    with db.connect() as conn:
        conn.execute(
            """INSERT INTO fixtures VALUES
               (7103, 'PL', ?, ?, 'TIMED', 'Mystery FC', 'Arsenal', NULL, 'Arsenal', ?)""",
            (season, kickoff, kickoff),
        )

    client = TestClient(webapp.app)
    details = client.get("/api/matches/7103").json()
    assert details["forecast"] is None
    assert details["note"] == "Team name not matched yet"


def test_dates_endpoint_reports_counts_per_competition(env, monkeypatch):
    from fastapi.testclient import TestClient
    import app as webapp

    monkeypatch.delenv("APP_PASSWORD", raising=False)
    kickoff = _kickoff()
    season = config.season_label(datetime.now(timezone.utc).date())
    day = kickoff[:10]
    with db.connect() as conn:
        conn.executemany(
            "INSERT INTO fixtures VALUES (?, ?, ?, ?, 'TIMED', ?, ?, ?, ?, ?)",
            [
                (8001, "PL", season, kickoff, "Arsenal FC", "Chelsea FC", "Arsenal", "Chelsea", kickoff),
                (8002, "PL", season, kickoff, "Chelsea FC", "Arsenal FC", "Chelsea", "Arsenal", kickoff),
                (8003, "UNL", season, kickoff, "England", "Croatia", "England", "Croatia", kickoff),
            ],
        )

    client = TestClient(webapp.app)
    dates = client.get("/api/dates", params={"from": day, "days": 3}).json()
    assert len(dates) == 1
    assert dates[0]["date"] == day
    assert dates[0]["total"] == 3
    assert dates[0]["by_competition"] == {"PL": 2, "UNL": 1}


def test_season_and_head_to_head_corner_averages_are_separate(env, monkeypatch):
    """The two averages must never be merged into one number."""
    from fastapi.testclient import TestClient
    import app as webapp

    monkeypatch.delenv("APP_PASSWORD", raising=False)
    kickoff = _kickoff()
    season = config.season_label(datetime.now(timezone.utc).date())
    with db.connect() as conn:
        conn.execute(
            """INSERT INTO fixtures VALUES
               (7104, 'PL', ?, ?, 'TIMED', 'Arsenal FC', 'Chelsea FC', 'Arsenal', 'Chelsea', ?)""",
            (season, kickoff, kickoff),
        )
        # this season: two matches for Arsenal
        _store_match(conn, home="Arsenal", away="Chelsea", home_corners=7, away_corners=3,
                     season=season, date="2026-08-20")
        _store_match(conn, home="Everton", away="Arsenal", home_corners=2, away_corners=8,
                     season=season, date="2026-09-10")
        # an earlier meeting, in another season, with a different corner count
        _store_match(conn, home="Chelsea", away="Arsenal", home_corners=10, away_corners=6,
                     season="2025-2026", date="2026-03-01")

    client = TestClient(webapp.app)
    details = client.get("/api/matches/7104").json()
    corners = details["corners"]
    assert corners["available"] is True
    season_average = corners["season_average"]
    h2h = corners["h2h"]
    # two separate objects, each with its own numbers
    assert set(season_average) == {"home_team", "away_team"}
    assert season_average["home_team"]["matches"] == 2
    assert season_average["home_team"]["corners_for"] == pytest.approx(7.5, abs=0.01)
    assert season_average["home_team"]["total_per_match"] == pytest.approx(10.0, abs=0.01)
    assert h2h["meetings"] == 2  # both meetings have corner data
    # Arsenal's corners in the two meetings: 7 (home) and 6 (away) -> 6.5
    assert h2h["corners_for_home_team"] == pytest.approx(6.5, abs=0.01)
    # Chelsea's corners: 3 (away) and 10 (home) -> 6.5
    assert h2h["corners_for_away_team"] == pytest.approx(6.5, abs=0.01)
    # the season card and the head-to-head card are not the same numbers
    assert season_average["home_team"]["total_per_match"] != h2h["total_per_match"]


def test_match_context_counts_form_and_meetings(env, monkeypatch):
    from app import _match_context

    with db.connect() as conn:
        _store_match(conn, home="Arsenal", away="Liverpool", home_goals=2, away_goals=1,
                     date="2026-08-15")
        _store_match(conn, home="Chelsea", away="Arsenal", home_goals=1, away_goals=0,
                     date="2026-09-10")
        _store_match(conn, home="Arsenal", away="Chelsea", home_goals=1, away_goals=1,
                     date="2026-10-01")

    with db.connect() as conn:
        context = _match_context(conn, "PL", "Arsenal", "Chelsea", "2026-11-01")

    assert context["form_home"] == ["D", "L", "W"]  # newest first
    assert context["form_away"] == ["D", "W"]
    # only the two Arsenal v Chelsea meetings count as head-to-head
    assert len(context["h2h"]) == 2
    assert context["h2h"][0]["score"] == "1-1"


def test_validation_status_follows_the_rule():
    from evaluate import _validation_status

    assert _validation_status(200, 0.9, 1.0) == "validated"
    assert _validation_status(200, 1.1, 1.0) == "experimental"
    assert _validation_status(30, 1.1, 1.0) == "experimental"
    assert _validation_status(10, 0.5, 1.0) == "unavailable"
