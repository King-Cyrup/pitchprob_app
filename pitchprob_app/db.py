"""SQLite database (a single file, built into Python - nothing to install)."""

import sqlite3
from config import DATA_DIR, DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS matches (          -- finished matches, used to train the model
    league TEXT NOT NULL, season TEXT NOT NULL, match_date TEXT NOT NULL,
    home TEXT NOT NULL, away TEXT NOT NULL,
    home_goals INTEGER NOT NULL, away_goals INTEGER NOT NULL,
    home_corners INTEGER, away_corners INTEGER,
    PRIMARY KEY (league, season, home, away)
);
CREATE TABLE IF NOT EXISTS intl_matches (
    date TEXT NOT NULL,
    home_team TEXT NOT NULL,
    away_team TEXT NOT NULL,
    home_score INTEGER NOT NULL,
    away_score INTEGER NOT NULL,
    tournament TEXT NOT NULL,
    neutral INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (date, home_team, away_team)
);
CREATE TABLE IF NOT EXISTS fixtures (         -- upcoming (and recent) matches from football-data.org
    fd_match_id INTEGER PRIMARY KEY, league TEXT NOT NULL, season TEXT NOT NULL,
    kickoff_utc TEXT NOT NULL, status TEXT NOT NULL,
    home_fd TEXT NOT NULL, away_fd TEXT NOT NULL,   -- names as football-data.org writes them
    home TEXT, away TEXT,                           -- names as our model knows them (NULL = not matched yet)
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS fixture_metadata (
    fd_match_id INTEGER PRIMARY KEY REFERENCES fixtures(fd_match_id),
    stage TEXT,
    neutral INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS team_crests (
    league TEXT NOT NULL, team_fd TEXT NOT NULL, crest_url TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (league, team_fd)
);
CREATE TABLE IF NOT EXISTS predictions (
    fd_match_id INTEGER PRIMARY KEY REFERENCES fixtures(fd_match_id),
    created_at TEXT NOT NULL, model_trained_at TEXT NOT NULL,
    p_home REAL NOT NULL, p_draw REAL NOT NULL, p_away REAL NOT NULL,
    p_over25 REAL NOT NULL, p_btts REAL NOT NULL,
    xg_home REAL NOT NULL, xg_away REAL NOT NULL,
    p_over15 REAL,
    markets_json TEXT,
    corners_json TEXT,
    model_version TEXT
);
CREATE TABLE IF NOT EXISTS grades (
    fd_match_id INTEGER PRIMARY KEY REFERENCES fixtures(fd_match_id),
    home_goals INTEGER NOT NULL, away_goals INTEGER NOT NULL, outcome TEXT NOT NULL,
    logloss_1x2 REAL NOT NULL, rps_1x2 REAL NOT NULL,
    logloss_over25 REAL NOT NULL, logloss_btts REAL NOT NULL,
    base_logloss_1x2 REAL NOT NULL, graded_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS market_grades (
    fd_match_id INTEGER NOT NULL REFERENCES fixtures(fd_match_id),
    market TEXT NOT NULL,
    model_loss REAL NOT NULL,
    graded_at TEXT NOT NULL,
    PRIMARY KEY (fd_match_id, market)
);
CREATE TABLE IF NOT EXISTS backtest (
    competition TEXT NOT NULL,
    match_date TEXT NOT NULL,
    home TEXT NOT NULL,
    away TEXT NOT NULL,
    actual_home INTEGER NOT NULL,
    actual_away INTEGER NOT NULL,
    forecast_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    model_version TEXT NOT NULL DEFAULT 'dc',
    PRIMARY KEY (competition, match_date, home, away, model_version)
);
CREATE TABLE IF NOT EXISTS market_validation (
    competition TEXT NOT NULL,
    market TEXT NOT NULL,
    n INTEGER NOT NULL,
    model_loss REAL,
    baseline_loss REAL,
    status TEXT NOT NULL,
    computed_at TEXT NOT NULL,
    PRIMARY KEY (competition, market)
);
CREATE INDEX IF NOT EXISTS idx_fixtures_kickoff ON fixtures (kickoff_utc);
"""


def connect() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def ensure_team_crests(conn: sqlite3.Connection) -> None:
    conn.execute(
        """CREATE TABLE IF NOT EXISTS team_crests (
               league TEXT NOT NULL, team_fd TEXT NOT NULL, crest_url TEXT NOT NULL,
               updated_at TEXT NOT NULL, PRIMARY KEY (league, team_fd)
           )"""
    )


def init_db() -> None:
    with connect() as conn:
        conn.executescript(SCHEMA)
        migrations = {
            "matches": {
                "home_corners": "INTEGER",
                "away_corners": "INTEGER",
            },
            "predictions": {
                "p_over15": "REAL",
                "markets_json": "TEXT",
                "corners_json": "TEXT",
                "model_version": "TEXT",
            },
            "backtest": {
                "model_version": "TEXT NOT NULL DEFAULT 'dc'",
            },
        }
        for table, columns in migrations.items():
            present = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}
            for name, declaration in columns.items():
                if name not in present:
                    conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {declaration}")
