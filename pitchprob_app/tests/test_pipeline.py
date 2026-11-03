"""End-to-end test with invented data. Run with:  python -m pytest -q"""
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config, db, modeling, names, predict, evaluate, sync_fixtures, load_history  # noqa: E402

TEAMS = ["Man City", "Man United", "Arsenal", "Chelsea", "Liverpool", "Tottenham", "Newcastle", "Wolves",
         "Brighton", "Everton", "Fulham", "Leeds", "Nott'm Forest", "West Ham", "Aston Villa", "Brentford",
         "Burnley", "Sunderland", "Bournemouth", "Crystal Palace"]


@pytest.fixture()
def env(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "t.db")
    monkeypatch.setattr(modeling, "MODELS_DIR", tmp_path / "models")
    monkeypatch.setattr(names, "ALIASES_PATH", tmp_path / "aliases.csv")
    db.init_db()
    return tmp_path


def make_history(today: date, current_pairs: int = 150) -> pd.DataFrame:
    rng = np.random.default_rng(7)
    att, dfn = rng.normal(0, .25, 20), rng.normal(0, .25, 20)
    rows, start_year = [], int(config.season_label(today)[:4])
    for sy in range(start_year - 3, start_year + 1):
        pairs = [(i, j) for i in range(20) for j in range(20) if i != j]
        rng.shuffle(pairs)
        if sy == start_year:
            pairs = pairs[:current_pairs]
        d0 = date(sy, 8, 10)
        for k, (i, j) in enumerate(pairs):
            d = d0 + timedelta(days=k * 280 // len(pairs) if sy < start_year else k * 2 // 3)
            rows.append(dict(season=f"{sy}-{sy + 1}", match_date=d.isoformat(), home=TEAMS[i], away=TEAMS[j],
                             home_goals=int(rng.poisson(np.exp(.35 + att[i] - dfn[j]))),
                             away_goals=int(rng.poisson(np.exp(.1 + att[j] - dfn[i])))))
    return pd.DataFrame(rows)


def store(df: pd.DataFrame):
    with db.connect() as conn:
        conn.executemany("INSERT INTO matches VALUES ('PL', ?, ?, ?, ?, ?, ?)",
                         [(r.season, r.match_date, r.home, r.away, r.home_goals, r.away_goals) for r in df.itertuples()])


def test_metrics():
    assert modeling.log_loss(1.0) == pytest.approx(0.0, abs=1e-9)
    assert modeling.log_loss(0.5) == pytest.approx(0.6931, abs=1e-3)
    assert modeling.rps_1x2((1.0, 0.0, 0.0), "H") == pytest.approx(0.0)
    assert modeling.rps_1x2((0.0, 0.0, 1.0), "H") == pytest.approx(1.0)  # worst case
    assert modeling.rps_1x2((1/3, 1/3, 1/3), "D") == pytest.approx(1/9)   # hand-calculated: 0.5*((1/3)^2+(1/3)^2)


def test_fixture_days_grouping():
    from app import _fixture_days

    today = date(2026, 10, 30)
    fixtures = [
        {"kickoff_utc": "2026-10-30T12:00:00Z", "league": "BL1"},
        {"kickoff_utc": "2026-10-30T14:00:00Z", "league": "FL1"},
        {"kickoff_utc": "2026-10-30T16:00:00Z", "league": "CL"},
        {"kickoff_utc": "2026-10-31T12:00:00Z", "league": "PL"},
        {"kickoff_utc": "2026-11-06T12:00:00Z", "league": "SA"},
    ]

    days = _fixture_days(fixtures, today)

    assert len(days) == 7
    assert [day["label"] for day in days[:4]] == ["Today", "Tomorrow", "Sun", "Mon"]
    assert [league["code"] for league in days[0]["leagues"]] == ["FL1", "BL1", "CL"]
    assert days[0]["leagues"][-1]["name"] == "Champions League"
    assert [league["code"] for league in days[1]["leagues"]] == ["PL"]
    assert all(league["code"] != "SA" for day in days for league in day["leagues"])


def test_champions_league_uses_bundled_model_team_names(env, monkeypatch):
    class FakeModel:
        teams = ["Real Madrid", "Paris Saint-Germain"]

    monkeypatch.setattr(sync_fixtures, "load_model", lambda league: (FakeModel(), "trained"))
    with db.connect() as conn:
        names = sync_fixtures._model_names(conn, "CL")

    assert names == {"Real Madrid", "Paris Saint-Germain"}


def test_champions_league_fixture_renders_in_app(env, monkeypatch):
    kickoff = (datetime.now(timezone.utc) + timedelta(days=1)).strftime("%Y-%m-%dT15:00:00Z")
    season = config.season_label(datetime.now(timezone.utc).date())
    with db.connect() as conn:
        conn.execute(
            """INSERT INTO fixtures VALUES
               (7001, 'CL', ?, ?, 'TIMED', 'Real Madrid', 'Arsenal FC',
                'Real Madrid', 'Arsenal FC', ?)""",
            (season, kickoff, kickoff),
        )

    from fastapi.testclient import TestClient
    import app as webapp
    monkeypatch.delenv("APP_PASSWORD", raising=False)
    response = TestClient(webapp.app).get("/")

    assert response.status_code == 200
    assert "Champions League" in response.text
    assert "Real Madrid" in response.text and "Arsenal FC" in response.text


def test_load_history_skips_leagues_without_a_source(env, monkeypatch):
    monkeypatch.setattr(load_history, "LEAGUES", {
        "CL": {"name": "Champions League", "fd_code": "CL", "pb_name": None},
    })

    def unexpected_scraper(*args, **kwargs):
        raise AssertionError("no football-data.co.uk scraper should be created for CL")

    monkeypatch.setattr(load_history.pb.scrapers, "FootballData", unexpected_scraper)
    load_history.load_history(["2025-2026"])


def test_match_context_uses_recent_history(env):
    from app import _add_match_context

    history = [
        ("2025-08-15", "Arsenal", "Chelsea", 2, 1),
        ("2025-09-10", "Chelsea", "Arsenal", 1, 0),
        ("2025-10-01", "Arsenal", "Chelsea", 1, 1),
        ("2025-11-12", "Chelsea", "Arsenal", 0, 2),
    ]
    with db.connect() as conn:
        conn.executemany(
            "INSERT INTO matches VALUES ('PL', ?, ?, ?, ?, ?, ?)",
            [(f"2025-{index}", *match) for index, match in enumerate(history)],
        )
        fixtures = [
            {"league": "PL", "home": "Arsenal", "away": "Chelsea"},
            {"league": "PL", "home": "Chelsea", "away": "Arsenal"},
        ]
        _add_match_context(conn, fixtures)

    assert fixtures[0]["home_form"] == ["W", "D", "L", "W"]
    assert fixtures[0]["away_form"] == ["L", "D", "W", "L"]
    assert [match["fixture_outcome"] for match in fixtures[0]["h2h"]] == ["W", "D", "L", "W"]
    assert [match["fixture_outcome"] for match in fixtures[1]["h2h"]] == ["L", "D", "W", "L"]


def test_name_matching(env):
    model_names = set(TEAMS)
    aliases = {"Manchester City FC": "Man City"}
    assert names.resolve("Arsenal FC", "Arsenal", model_names, aliases) == "Arsenal"
    assert names.resolve("Newcastle United FC", "Newcastle", model_names, aliases) == "Newcastle"
    assert names.resolve("Manchester City FC", "Man City", model_names, aliases) == "Man City"
    assert names.resolve("AFC Bournemouth", "Bournemouth", model_names, aliases) == "Bournemouth"
    assert names.resolve("Wolverhampton Wanderers FC", "Wolves", model_names, {}) == "Wolves"  # short name matches
    assert names.resolve("Wolverhampton Wanderers FC", None, model_names, {}) is None  # no short name: needs an alias
    assert names.resolve("Wolverhampton Wanderers FC", None, model_names, {"Wolverhampton Wanderers FC": "Wolves"}) == "Wolves"


def test_full_pipeline(env, monkeypatch):
    today = datetime.now(timezone.utc).date()
    hist = make_history(today)
    store(hist)
    modeling.train_all()
    assert (modeling.MODELS_DIR / "PL.pkl").exists()
    evaluate.run_evaluation()
    # invent two upcoming fixtures among pairs not yet played this season
    cur = hist[hist.season == config.season_label(today)]
    played = set(zip(cur.home, cur.away))
    todo = [(h, a) for h in TEAMS for a in TEAMS if h != a and (h, a) not in played][:2]
    kick = (datetime.now(timezone.utc) + timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    with db.connect() as conn:
        for n, (h, a) in enumerate(todo, start=1):
            conn.execute("INSERT INTO fixtures VALUES (?, 'PL', ?, ?, 'TIMED', ?, ?, ?, ?, ?)",
                         (n, config.season_label(today), kick, h, a, h, a, kick))
        conn.executemany(
            "INSERT INTO team_crests VALUES ('PL', ?, ?, ?)",
            [(todo[0][0], "https://example.test/home.png", kick),
             (todo[0][1], "https://example.test/away.png", kick)],
        )
        conn.execute("INSERT INTO fixtures VALUES (99, 'PL', ?, ?, 'TIMED', 'Mystery FC', 'Arsenal', NULL, 'Arsenal', ?)",
                     (config.season_label(today), kick, kick))
    predict.make_predictions()
    with db.connect() as conn:
        preds = conn.execute("SELECT * FROM predictions").fetchall()
        assert len(preds) == 2
        for p in preds:
            assert p["p_home"] + p["p_draw"] + p["p_away"] == pytest.approx(1.0, abs=1e-6)
            assert 0 < p["p_over25"] < 1 and 0 < p["p_btts"] < 1
        # results arrive later
        for n, (h, a) in enumerate(todo, start=1):
            conn.execute("INSERT INTO matches VALUES ('PL', ?, ?, ?, ?, 2, 1)", (config.season_label(today), today.isoformat(), h, a))
    predict.grade_predictions()
    with db.connect() as conn:
        g = conn.execute("SELECT * FROM grades").fetchall()
        assert len(g) == 2 and g[0]["outcome"] == "H"
        assert g[0]["logloss_1x2"] > 0
    # web app
    from fastapi.testclient import TestClient
    import app as webapp
    monkeypatch.delenv("APP_PASSWORD", raising=False)
    client = TestClient(webapp.app)
    r = client.get("/")
    assert r.status_code == 200 and "Track record" in r.text and "Team name not matched yet" in r.text
    assert "Asian handicap" in r.text and "Head-to-head" in r.text
    assert "https://example.test/home.png" in r.text and "https://example.test/away.png" in r.text
    assert 'class="collapsible-panel league-fixtures is-open"' in r.text
    assert 'class="lg-toggle" type="button" aria-expanded="true"' in r.text
    hz = client.get("/healthz").json()
    assert hz["status"] == "ok"
    assert "fixtures" in hz.get("db", {}) and "predictions" in hz.get("db", {})
    assert len(client.get("/api/ledger").json()["recent"]) == 2
    monkeypatch.setenv("APP_PASSWORD", "secret")
    assert client.get("/").status_code == 401
    assert client.get("/", auth=("pitchprob", "wrong")).status_code == 401
    assert client.get("/", auth=("pitchprob", "secret")).status_code == 200


def test_sync_fixtures_parsing(env, monkeypatch):
    store(make_history(datetime.now(timezone.utc).date()))
    monkeypatch.setattr(sync_fixtures, "FOOTBALL_DATA_TOKEN", "x")
    monkeypatch.setattr(sync_fixtures, "LEAGUES", {"PL": config.LEAGUES["PL"]})
    monkeypatch.setattr(sync_fixtures.time, "sleep", lambda s: None)
    tomorrow = (datetime.now(timezone.utc) + timedelta(days=1)).strftime("%Y-%m-%dT15:00:00Z")

    class FakeResp:
        status_code = 200
        def json(self):
            team = lambda i, n, s: {
                "id": i, "name": n, "shortName": s, "tla": "XXX",
                "crest": f"https://example.test/crests/{i}.png",
            }
            return {"matches": [
                {"id": 5001, "utcDate": tomorrow, "status": "TIMED", "matchday": 10,
                 "homeTeam": team(1, "Arsenal FC", "Arsenal"), "awayTeam": team(2, "Chelsea FC", "Chelsea"),
                 "score": {"winner": None, "fullTime": {"home": None, "away": None}}},
                {"id": 5002, "utcDate": tomorrow, "status": "FINISHED", "matchday": 10,
                 "homeTeam": team(3, "Everton FC", "Everton"), "awayTeam": team(4, "Fulham FC", "Fulham"),
                 "score": {"winner": "DRAW", "fullTime": {"home": 1, "away": 1}}}]}

    monkeypatch.setattr(sync_fixtures.requests, "get", lambda *a, **k: FakeResp())
    sync_fixtures.sync_fixtures()
    with db.connect() as conn:
        rows = conn.execute("SELECT * FROM fixtures").fetchall()
        crests = conn.execute("SELECT team_fd, crest_url FROM team_crests ORDER BY team_fd").fetchall()
    assert len(rows) == 1 and rows[0]["home"] == "Arsenal" and rows[0]["away"] == "Chelsea"
    assert [(row["team_fd"], row["crest_url"]) for row in crests] == [
        ("Arsenal FC", "https://example.test/crests/1.png"),
        ("Chelsea FC", "https://example.test/crests/2.png"),
    ]


def test_load_history_shape(env, monkeypatch):
    df = pd.DataFrame({
        "date": pd.to_datetime(["2025-08-16", "2025-08-17", "2025-08-18"]),
        "team_home": ["Arsenal", "Chelsea", "Everton"], "team_away": ["Fulham", "Leeds", "Wolves"],
        "goals_home": [2.0, 1.0, np.nan], "goals_away": [0.0, 1.0, np.nan]})

    class FakeScraper:
        def __init__(self, comp, season, *a): pass
        def get_fixtures(self): return df

    monkeypatch.setattr(load_history.pb.scrapers, "FootballData", FakeScraper)
    monkeypatch.setattr(load_history, "LEAGUES", {"PL": config.LEAGUES["PL"]})
    load_history.load_history(["2025-2026"])
    with db.connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM matches").fetchone()[0] == 2  # the unplayed row is dropped


def test_load_history_strict_failure(env, monkeypatch):
    class BrokenScraper:
        def __init__(self, comp, season, *args):
            raise OSError("source unavailable")

    monkeypatch.setattr(load_history.pb.scrapers, "FootballData", BrokenScraper)
    monkeypatch.setattr(load_history, "LEAGUES", {"PL": config.LEAGUES["PL"]})

    with pytest.raises(RuntimeError, match="Could not refresh PL results"):
        load_history.load_history(["2025-2026"], strict=True)


def test_sync_fixtures_strict_failure(env, monkeypatch):
    class FailedResponse:
        status_code = 503
        text = "temporarily unavailable"

    monkeypatch.setattr(sync_fixtures, "FOOTBALL_DATA_TOKEN", "test-token")
    monkeypatch.setattr(sync_fixtures, "LEAGUES", {"PL": config.LEAGUES["PL"]})
    monkeypatch.setattr(sync_fixtures.requests, "get", lambda *args, **kwargs: FailedResponse())
    monkeypatch.setattr(sync_fixtures.time, "sleep", lambda seconds: None)

    with pytest.raises(RuntimeError, match="Could not fetch PL fixtures: HTTP 503"):
        sync_fixtures.sync_fixtures(strict=True)


def test_sync_fixtures_strict_fails_when_no_competitions_are_accessible(env, monkeypatch):
    class ForbiddenResponse:
        status_code = 403
        text = "competition unavailable"

    monkeypatch.setattr(sync_fixtures, "FOOTBALL_DATA_TOKEN", "test-token")
    monkeypatch.setattr(sync_fixtures, "LEAGUES", {"PL": config.LEAGUES["PL"]})
    monkeypatch.setattr(sync_fixtures.requests, "get", lambda *args, **kwargs: ForbiddenResponse())

    with pytest.raises(RuntimeError, match="No football-data.org competitions"):
        sync_fixtures.sync_fixtures(strict=True)


def test_streamlit_dashboard_smoke():
    from streamlit.testing.v1 import AppTest

    script = Path(__file__).resolve().parents[1] / "streamlit_app.py"
    result = AppTest.from_file(str(script), default_timeout=30).run()

    assert not result.exception
    page_html = result.html[0].proto.body
    assert "<title>PitchProb" in page_html
    assert "Track record" in page_html
    assert "Champions League" in page_html
    assert not result.radio and not result.multiselect


def test_check_access_and_status(env, monkeypatch, capsys):
    monkeypatch.setattr(sync_fixtures, "FOOTBALL_DATA_TOKEN", "x")

    class FakeResp:
        status_code = 200
        def json(self):
            return {"competitions": [{"code": c, "name": c} for c in ("PL", "PD", "SA", "BL1", "CL")]}

    monkeypatch.setattr(sync_fixtures.requests, "get", lambda *a, **k: FakeResp())
    sync_fixtures.check_access()
    out = capsys.readouterr().out
    assert "OK      PL" in out and "MISSING FL1" in out
    import cli
    store(make_history(datetime.now(timezone.utc).date()))
    cli.status()
    assert "PL" in capsys.readouterr().out


def test_lock_before_kickoff(env, monkeypatch):
    """A fixture inside the lock window must not be written by make_predictions."""
    today = datetime.now(timezone.utc).date()
    store(make_history(today))
    modeling.train_all()
    kick_future = (datetime.now(timezone.utc) + timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
    kick_locked = (datetime.now(timezone.utc) + timedelta(minutes=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
    season = config.season_label(today)
    with db.connect() as conn:
        conn.execute("INSERT INTO fixtures VALUES (1, 'PL', ?, ?, 'TIMED', 'Man City', 'Arsenal', 'Man City', 'Arsenal', ?)",
                     (season, kick_future, kick_future))
        conn.execute("INSERT INTO fixtures VALUES (2, 'PL', ?, ?, 'TIMED', 'Chelsea', 'Liverpool', 'Chelsea', 'Liverpool', ?)",
                     (season, kick_locked, kick_locked))
    predict.make_predictions()
    with db.connect() as conn:
        preds = conn.execute("SELECT fd_match_id FROM predictions").fetchall()
        ids = {p["fd_match_id"] for p in preds}
    assert 1 in ids, "fixture outside lock window should be predicted"
    assert 2 not in ids, "fixture inside lock window must not be predicted"


def test_teams_command(env, capsys):
    import cli
    store(make_history(datetime.now(timezone.utc).date()))
    cli.teams("PL")
    assert "Man City" in capsys.readouterr().out
    with pytest.raises(SystemExit):
        cli.teams(None)
