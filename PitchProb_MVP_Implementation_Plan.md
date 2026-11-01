# PitchProb MVP: Step-by-Step Implementation Plan

**What you will have at the end:** a small web page, running on your computer, that shows upcoming matches from five top European leagues with the model's probability for Home win, Draw, Away win, Over 2.5 goals and Both teams to score. It keeps a track record of how good those forecasts turned out to be. Up to three testers can open it.

**Who this is written for:** someone who can build web pages but has not used Python, SQLite, FastAPI or football models before. Every command is written out. Every file is given in full. You copy, run, and compare what you see with what this guide says you should see.

**Date and versions:** written 28 October 2026. Tested with Python 3.12.3, penaltyblog 1.13.1, FastAPI 0.162.0 (details in section 4).

---

## 1. Scope: what is in, what is held back

### In the MVP

| Piece | What it does |
|---|---|
| Past results | Downloads finished matches for 5 leagues for the last 4 seasons (the 3 completed ones plus the current one) |
| Model | Trains one statistical model per league (Dixon-Coles, explained in step 5) |
| Test | Replays last season month by month to check the model beats a "no model" guess before you trust it |
| Fixtures | Downloads matches for the next 7 days |
| Forecasts | Stores probabilities for each upcoming match |
| Web page | One page with upcoming forecasts and a track record |
| Grading | After matches finish, scores each forecast and shows the totals |

### Held back for later builds (do not build these now)

User accounts and payments, Telegram/WhatsApp alerts, the "lock one hour before kickoff" rule with tamper-proof history, season simulations, share cards, a public API for other developers, lineups and injuries, bookmaker odds, a mobile app, PostgreSQL, Redis, a CDN, automatic scheduling, more leagues. Section 11 maps each one to your system design document.

### The five leagues

Premier League (code `PL`), La Liga (`PD`), Serie A (`SA`), Bundesliga (`BL1`), Ligue 1 (`FL1`). You said "top European leagues, fewer than ten". These five are my choice. To change the list later you edit one dictionary in `config.py`.

---

## 2. Decisions I made for you

You gave me no preference for these, so I picked the simplest option that works for three users. Each can be changed.

| Decision | Choice | Why | How to change later |
|---|---|---|---|
| Screen | A web page opened in a browser | One technology instead of two; works on any phone | Add an Expo app that reads `/api/fixtures` |
| Language | Python 3.12 | The football model library is Python; one language for data, model and server | Not recommended to change |
| Web framework | FastAPI with an HTML template | Serves a page and a JSON API from the same small program | Put a Next.js front end in front of the same API |
| Database | SQLite (one file, built into Python) | Nothing to install, no server; plenty for 3 users | Move to PostgreSQL when you add accounts or more users |
| Past results source | football-data.co.uk, through the `penaltyblog` library | Free CSV files with 20+ years of results; the library already downloads them for you | Another provider behind the same `matches` table |
| Upcoming fixtures source | football-data.org free plan | Official, documented API with fixtures for the big leagues | Another provider |
| Model | Dixon-Coles, one per league | Standard football goals model, ready-made in `penaltyblog`, trains in seconds | Add models later and compare on the same test |
| Where it runs | Your own computer | Free, no deployment skills needed | A cheap server (section 11) |
| Sharing with testers | Cloudflare Quick Tunnel with an email lock | Free, no account, no server; official docs describe the email lock | A named tunnel or a server with a domain |

### Questions I could not ask you (the plan covers both answers)

- **Your operating system:** commands are shown for Windows and for macOS/Linux.
- **Mobile app or web:** this plan builds a web page. If you want the Expo app first, finish steps 1 to 10 first; the app reads `/api/fixtures`.

---

## 3. How the pieces fit

```
football-data.co.uk  ──(penaltyblog)──►  matches table ──►  train ──►  models/PL.pkl ...
                                                │                         │
football-data.org ──► fixtures table ──────────►└──►  predict  ──────────►  predictions table
        (next 7 days)        │                                              │
                       team-name matching                        web page + /api/fixtures
                                                                            ▲
results arrive in matches table ──► grade ──► grades table ─────────────────┘ (track record)
```

Folder layout you will create:

```
pitchprob/
├── .env                 your secret settings (never share this file)
├── .env.example
├── .gitignore
├── requirements.txt     exact library versions
├── config.py            settings and league list
├── db.py                database tables
├── names.py             matches team names between the two data sources
├── load_history.py      downloads finished matches
├── sync_fixtures.py     downloads upcoming fixtures, checks your API token
├── modeling.py          trains models, makes probabilities, scoring rules
├── evaluate.py          replays last season to test the model
├── predict.py           writes forecasts, grades them later
├── app.py               the web server
├── cli.py               the commands you will type
├── templates/index.html the web page
├── data/team_aliases.csv  team-name fixes you add by hand
├── models/              trained models are saved here
└── tests/test_pipeline.py automatic tests
```

---

## 4. What is verified and what is not

I could not reach football-data.co.uk or football-data.org from my working environment, so the live downloads were never run. Everything else was run. Nothing below is guessed silently: each unverified item has a "real-data checkpoint" in the steps, with a command that tells you the truth in a minute.

| Verified by running code (Python 3.12.3, simulated data) | Verified from official documentation | **Not verified** (checked by you in the steps) |
|---|---|---|
| Training, prediction, saving and loading models with penaltyblog 1.13.1 | football-data.org v4 endpoints, header name, filters, match fields and status values | That a file for the current season exists on football-data.co.uk and its update frequency |
| The scoring rules (log loss, RPS) with hand-calculated cases | penaltyblog's `FootballData` downloader and its column names | That your free football-data.org plan can read all five leagues |
| Database, forecast writing, grading, web page, password option | penaltyblog's Dixon-Coles example (weights, `fit`, `predict`, output fields) | Free-plan limits and delays (only third-party summaries found) |
| Parsing of the football-data.org response shape and of the penaltyblog table shape (with imitation data) | Cloudflare Quick Tunnel command and the email-lock option | The exact team-name differences between the two sources |
| 6 automated tests, all passing | | Whether the terms of both data sources allow the use you plan (fine for private testing; check before charging anyone) |

Sources are listed in section 12.

---

## 5. Before you start (one-time setup)

### 5.1 Install Python 3.12

1. Go to https://www.python.org/downloads/ and download Python **3.12** for your system (I tested 3.12.3).
2. **Windows:** in the installer, tick **Add python.exe to PATH**, then Install.
3. Open a terminal (Windows: search "Command Prompt" or "PowerShell"; macOS: "Terminal").
4. Check it worked:
   - Windows: `py -3.12 --version`
   - macOS/Linux: `python3.12 --version`

   You should see `Python 3.12.x`. If not, close and reopen the terminal, then retry.

### 5.2 A text editor

Any editor works. Visual Studio Code (free, https://code.visualstudio.com) is a common choice.

### 5.3 Get a free football-data.org token

1. Open https://www.football-data.org and register for the free plan (a third-party page lists the registration page as https://www.football-data.org/client/register).
2. The token (a long string of letters and digits) arrives by email or appears on your account page. Third-party documentation describes both; I could not open the account area myself.
3. Keep it secret. You will paste it into the `.env` file in step 2.

What the free plan includes, according to third-party summaries: 12 competitions, 10 requests per minute, delayed scores. **Confirm on the official pages** https://www.football-data.org/pricing and https://www.football-data.org/coverage. Step 3 also checks it with your real token.

### 5.4 Optional, for step 11 only: cloudflared

Download from the official page https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/downloads/ and install. You can do this later.

---

## 6. Build steps

Work in order. Do not skip the "you should see" checks.

### Step 1: Create the project and install the libraries

**Windows (Command Prompt):**

```
mkdir pitchprob
cd pitchprob
py -3.12 -m venv .venv
.venv\Scripts\activate
```

If you use PowerShell and see "running scripts is disabled", run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once, answer Y, and retry (standard Windows setting; I did not test PowerShell).

**macOS / Linux:**

```
mkdir pitchprob
cd pitchprob
python3.12 -m venv .venv
source .venv/bin/activate
```

Your prompt now starts with `(.venv)`. That means the project's private Python is active. **Every time you open a new terminal, go into the `pitchprob` folder and run the activate line again.**

Create `requirements.txt`:

```text
penaltyblog==1.13.1
fastapi[standard]==0.162.0
requests==2.34.2
pandas==3.1.0
numpy==2.5.4
scipy==1.18.1
pytest==9.2.0
```

Install (this can take several minutes):

```
pip install -r requirements.txt
```

**You should see:** a long list ending with `Successfully installed ...`. Then:

```
python -c "import penaltyblog, fastapi, pandas; print('libraries ok')"
```

**You should see:** `libraries ok`.

### Step 2: Settings and the database

Create these files in the `pitchprob` folder (copy each block exactly; file names are in the headings).

**`config.py`**

```python
"""Settings for PitchProb. Edit LEAGUES to change which leagues the app covers."""
import os
from datetime import date
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
MODELS_DIR = BASE_DIR / "models"
DB_PATH = DATA_DIR / "pitchprob.db"
ALIASES_PATH = DATA_DIR / "team_aliases.csv"


def _load_dotenv():
    """Read KEY=VALUE lines from a file called .env (if it exists) into os.environ."""
    env_file = BASE_DIR / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_dotenv()

# key = our short code (also the football-data.org competition code)
# fd_code = football-data.org competition code, pb_name = penaltyblog / football-data.co.uk name
LEAGUES = {
    "PL": {"name": "Premier League", "fd_code": "PL", "pb_name": "ENG Premier League"},
    "PD": {"name": "La Liga", "fd_code": "PD", "pb_name": "ESP La Liga"},
    "SA": {"name": "Serie A", "fd_code": "SA", "pb_name": "ITA Serie A"},
    "BL1": {"name": "Bundesliga", "fd_code": "BL1", "pb_name": "DEU Bundesliga 1"},
    "FL1": {"name": "Ligue 1", "fd_code": "FL1", "pb_name": "FRA Ligue 1"},
}

FOOTBALL_DATA_TOKEN = os.environ.get("FOOTBALL_DATA_TOKEN", "")
FD_BASE_URL = "https://api.football-data.org/v4"

XI = 0.001            # time-decay rate used in penaltyblog's own Dixon-Coles example
SEASONS_BACK = 3      # how many completed seasons to train on (plus the current one)
FIXTURE_DAYS_AHEAD = 7


def season_label(d: date) -> str:
    """European seasons start in July/August: 2026-10-28 -> '2026-2027'."""
    start = d.year if d.month >= 7 else d.year - 1
    return f"{start}-{start + 1}"


def seasons_to_load(today: date | None = None) -> list[str]:
    today = today or date.today()
    start = int(season_label(today)[:4])
    return [f"{y}-{y + 1}" for y in range(start - SEASONS_BACK, start + 1)]
```

**`db.py`**

```python
"""SQLite database (a single file, built into Python - nothing to install)."""
import sqlite3
from config import DATA_DIR, DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS matches (          -- finished matches, used to train the model
    league TEXT NOT NULL, season TEXT NOT NULL, match_date TEXT NOT NULL,
    home TEXT NOT NULL, away TEXT NOT NULL,
    home_goals INTEGER NOT NULL, away_goals INTEGER NOT NULL,
    PRIMARY KEY (league, season, home, away)
);
CREATE TABLE IF NOT EXISTS fixtures (         -- upcoming (and recent) matches from football-data.org
    fd_match_id INTEGER PRIMARY KEY, league TEXT NOT NULL, season TEXT NOT NULL,
    kickoff_utc TEXT NOT NULL, status TEXT NOT NULL,
    home_fd TEXT NOT NULL, away_fd TEXT NOT NULL,   -- names as football-data.org writes them
    home TEXT, away TEXT,                           -- names as our model knows them (NULL = not matched yet)
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS predictions (
    fd_match_id INTEGER PRIMARY KEY REFERENCES fixtures(fd_match_id),
    created_at TEXT NOT NULL, model_trained_at TEXT NOT NULL,
    p_home REAL NOT NULL, p_draw REAL NOT NULL, p_away REAL NOT NULL,
    p_over25 REAL NOT NULL, p_btts REAL NOT NULL,
    xg_home REAL NOT NULL, xg_away REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS grades (
    fd_match_id INTEGER PRIMARY KEY REFERENCES fixtures(fd_match_id),
    home_goals INTEGER NOT NULL, away_goals INTEGER NOT NULL, outcome TEXT NOT NULL,
    logloss_1x2 REAL NOT NULL, rps_1x2 REAL NOT NULL,
    logloss_over25 REAL NOT NULL, logloss_btts REAL NOT NULL,
    base_logloss_1x2 REAL NOT NULL, graded_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_fixtures_kickoff ON fixtures (kickoff_utc);
"""


def connect() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    with connect() as conn:
        conn.executescript(SCHEMA)
```

**`names.py`** (used in step 7; create it now so the other files can import it)

```python
"""Match team names between football-data.org (fixtures) and football-data.co.uk (history)."""
import csv
import difflib
import re
import unicodedata
from config import ALIASES_PATH

# Words that clubs add or drop in different sources. Removed before comparing names.
NOISE = {"fc", "afc", "cf", "sc", "ac", "as", "us", "ud", "rcd", "ssc", "ss", "sv", "vfl", "vfb", "fsv", "tsg", "calcio"}


def normalize(name: str) -> str:
    text = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii").lower()
    tokens = [t for t in re.split(r"[^a-z0-9]+", text) if t and t not in NOISE]
    return " ".join(tokens)


def load_aliases() -> dict[str, str]:
    """team_aliases.csv has two columns: fd_name,model_name"""
    aliases: dict[str, str] = {}
    if ALIASES_PATH.exists():
        with open(ALIASES_PATH, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                if row.get("fd_name") and row.get("model_name"):
                    aliases[row["fd_name"].strip()] = row["model_name"].strip()
    return aliases


def resolve(fd_name: str, fd_short: str | None, model_names: set[str], aliases: dict[str, str]) -> str | None:
    """Return the model's name for a football-data.org team, or None if we cannot be sure."""
    if fd_name in aliases and aliases[fd_name] in model_names:
        return aliases[fd_name]
    by_norm = {normalize(n): n for n in model_names}
    for candidate in (fd_name, fd_short or ""):
        key = normalize(candidate)
        if key and key in by_norm:
            return by_norm[key]
    # model name's words are all inside the longer fd name, e.g. 'Newcastle' in 'Newcastle United FC'
    fd_tokens = set(normalize(fd_name).split())
    hits = [n for n in model_names if normalize(n) and set(normalize(n).split()) <= fd_tokens]
    return hits[0] if len(hits) == 1 else None


def suggest(fd_name: str, model_names: set[str]) -> list[str]:
    by_norm = {normalize(n): n for n in model_names}
    close = difflib.get_close_matches(normalize(fd_name), list(by_norm), n=3, cutoff=0.4)
    return [by_norm[c] for c in close]
```

**`cli.py`** (the commands you will type)

```python
"""Command line entry point:  python cli.py <command>"""
import argparse
from config import LEAGUES, seasons_to_load
from db import connect, init_db
from names import load_aliases, suggest


def check_names() -> None:
    """List football-data.org teams we could not match to a model team name."""
    with connect() as conn:
        rows = conn.execute(
            "SELECT league, home_fd AS fd, home AS model FROM fixtures UNION SELECT league, away_fd, away FROM fixtures"
        ).fetchall()
        bad = sorted({(r["league"], r["fd"]) for r in rows if r["model"] is None})
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
        "grade", "daily", "status", "teams"])
    parser.add_argument("league", nargs="?", help="league code, only used by the 'teams' command")
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
        print("1/5 results"); load_history(seasons_to_load()[-2:])
        print("2/5 fixtures"); sync_fixtures()
        print("3/5 train"); train_all()
        print("4/5 predict"); make_predictions()
        print("5/5 grade"); grade_predictions()


if __name__ == "__main__":
    main()
```

Create the folders and the alias file:

- Create folders named `data`, `models`, `templates`, `tests`.
- Create `data/team_aliases.csv` containing exactly one line: `fd_name,model_name`

Create `.env` (note the dot at the start of the name) containing your token:

```
FOOTBALL_DATA_TOKEN=paste-your-token-here
```

No quotes, no spaces around the `=`. Also create `.env.example` and `.gitignore` as below (they protect you from accidentally sharing secrets if you use git later).

**`.env.example`**

```text
FOOTBALL_DATA_TOKEN=paste-your-token-here
# Optional: set a password to protect the page (browser asks for username and password)
# APP_USERNAME=pitchprob
# APP_PASSWORD=choose-a-long-password
```

**`.gitignore`**

```text
.env
.venv/
__pycache__/
data/*.db
models/
```

Two more files are imported by `cli.py` only when needed, so the next command works already. Run:

```
python cli.py init-db
```

**You should see:** `Database ready.` and a new file `data/pitchprob.db`.

### Step 3: Check your token and league access (real-data checkpoint 1)

Create **`sync_fixtures.py`**. It contains two things: `check_access` (used now) and `sync_fixtures` (used in step 7).

```python
"""Fetch upcoming fixtures from football-data.org and match team names to the model's names."""
import time
from datetime import datetime, timedelta, timezone
import requests
from config import FD_BASE_URL, FIXTURE_DAYS_AHEAD, FOOTBALL_DATA_TOKEN, LEAGUES, season_label
from db import connect
from names import load_aliases, resolve


def _model_names(conn, league: str) -> set[str]:
    rows = conn.execute(
        "SELECT home AS n FROM matches WHERE league = ? UNION SELECT away FROM matches WHERE league = ?",
        (league, league),
    ).fetchall()
    return {r["n"] for r in rows}


def sync_fixtures() -> None:
    if not FOOTBALL_DATA_TOKEN:
        raise SystemExit("FOOTBALL_DATA_TOKEN is empty. Put it in the .env file (see the guide).")
    today = datetime.now(timezone.utc).date()
    params = {"dateFrom": today.isoformat(), "dateTo": (today + timedelta(days=FIXTURE_DAYS_AHEAD)).isoformat()}
    aliases = load_aliases()
    with connect() as conn:
        for code, league in LEAGUES.items():
            resp = requests.get(
                f"{FD_BASE_URL}/competitions/{league['fd_code']}/matches",
                headers={"X-Auth-Token": FOOTBALL_DATA_TOKEN}, params=params, timeout=30,
            )
            if resp.status_code != 200:
                print(f"  {code}: HTTP {resp.status_code}: {resp.text[:200]}")
                if resp.status_code == 429:
                    print("  Too many requests. Wait a minute and run again.")
                    break
                continue
            names = _model_names(conn, code)
            kept = 0
            for m in resp.json().get("matches", []):
                if m["status"] not in ("SCHEDULED", "TIMED"):
                    continue
                kickoff = m["utcDate"]  # e.g. 2026-11-01T16:30:00Z
                home = resolve(m["homeTeam"]["name"], m["homeTeam"].get("shortName"), names, aliases)
                away = resolve(m["awayTeam"]["name"], m["awayTeam"].get("shortName"), names, aliases)
                conn.execute(
                    """INSERT INTO fixtures (fd_match_id, league, season, kickoff_utc, status,
                                             home_fd, away_fd, home, away, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                       ON CONFLICT (fd_match_id) DO UPDATE SET
                         kickoff_utc = excluded.kickoff_utc, status = excluded.status,
                         home = excluded.home, away = excluded.away, updated_at = excluded.updated_at""",
                    (m["id"], code, season_label(datetime.fromisoformat(kickoff.replace("Z", "+00:00")).date()),
                     kickoff, m["status"], m["homeTeam"]["name"], m["awayTeam"]["name"], home, away,
                     datetime.now(timezone.utc).isoformat()),
                )
                kept += 1
            print(f"  {code}: {kept} upcoming fixtures stored")
            time.sleep(7)  # the free plan allows 10 requests per minute


def check_access() -> None:
    """Ask football-data.org which competitions your token may read, and compare with LEAGUES."""
    if not FOOTBALL_DATA_TOKEN:
        raise SystemExit("FOOTBALL_DATA_TOKEN is empty. Put it in the .env file (see the guide).")
    resp = requests.get(f"{FD_BASE_URL}/competitions", headers={"X-Auth-Token": FOOTBALL_DATA_TOKEN}, timeout=30)
    print("HTTP status:", resp.status_code)
    if resp.status_code != 200:
        raise SystemExit(f"Unexpected answer: {resp.text[:300]}")
    available = {c["code"]: c["name"] for c in resp.json().get("competitions", [])}
    print(f"Your token can read {len(available)} competitions: {', '.join(sorted(available))}")
    for code, league in LEAGUES.items():
        mark = "OK     " if league["fd_code"] in available else "MISSING"
        print(f"  {mark} {code} ({league['name']})")
```

Run:

```
python cli.py check-access
```

**You should see:** `HTTP status: 200`, then the competitions your token can read, then five lines starting `OK` for PL, PD, SA, BL1 and FL1.

| If you see | It means | Do this |
|---|---|---|
| `FOOTBALL_DATA_TOKEN is empty` | `.env` is missing or in the wrong folder | It must sit next to `cli.py`; check the spelling |
| `HTTP status: 400` or `403` | Token wrong or not active | Copy the token again from your email or account page |
| One or more `MISSING` lines | Your plan cannot read that league | Remove that league from `LEAGUES` in `config.py`, or check the coverage page |

### Step 4: Download past results (real-data checkpoint 2)

Create **`load_history.py`**:

```python
"""Download finished matches from football-data.co.uk (through the penaltyblog library)."""
import pandas as pd
import penaltyblog as pb
from config import LEAGUES, seasons_to_load
from db import connect


def load_history(seasons: list[str] | None = None) -> None:
    seasons = seasons or seasons_to_load()
    with connect() as conn:
        for code, league in LEAGUES.items():
            for season in seasons:
                try:
                    df = pb.scrapers.FootballData(league["pb_name"], season).get_fixtures()
                except Exception as err:  # a season file may not exist yet
                    print(f"  {code} {season}: could not download ({type(err).__name__}: {err})")
                    continue
                df = df.dropna(subset=["goals_home", "goals_away"])  # keep finished matches only
                rows = [
                    (code, season, pd.Timestamp(r.date).strftime("%Y-%m-%d"), r.team_home, r.team_away,
                     int(r.goals_home), int(r.goals_away))
                    for r in df.itertuples()
                ]
                conn.executemany(
                    """INSERT INTO matches (league, season, match_date, home, away, home_goals, away_goals)
                       VALUES (?, ?, ?, ?, ?, ?, ?)
                       ON CONFLICT (league, season, home, away) DO UPDATE SET
                         match_date = excluded.match_date,
                         home_goals = excluded.home_goals, away_goals = excluded.away_goals""",
                    rows,
                )
                print(f"  {code} {season}: {len(rows)} finished matches stored")
```

How it works: `penaltyblog.scrapers.FootballData("ENG Premier League", "2025-2026").get_fixtures()` downloads one league-season from football-data.co.uk as a table with columns `date`, `team_home`, `team_away`, `goals_home`, `goals_away` (column names from the penaltyblog documentation). The code keeps rows with a final score and stores them in the `matches` table. Running it twice is safe: it updates rows instead of duplicating them.

Run (a minute or two):

```
python cli.py load-history
python cli.py status
```

**You should see:** a line per league and season such as `PL 2025-2026: 380 finished matches stored`, then the `status` table.

**Check the counts.** Completed seasons since 2023-2024 should have **380** matches for `PL`, `PD`, `SA` and **306** for `BL1`, `FL1` (those two leagues have 18 clubs). The current season (2026-2027) is partial. If a completed season has a very different number, the download is incomplete: delete `data/pitchprob.db`, run `python cli.py init-db`, and retry.

**If a season prints "could not download"**: the file may not exist yet (most likely the current season). The plan still works with the other seasons; try again in a few days. If every season fails, copy the error text and check your internet connection first.

**Inspect the real columns once.** This confirms the library still returns the names the code expects:

```
python -c "import penaltyblog as pb; df = pb.scrapers.FootballData('ENG Premier League','2025-2026').get_fixtures(); print(df[['date','team_home','team_away','goals_home','goals_away']].head())"
```

**You should see** five rows with those five columns. If you get a `KeyError`, a column name changed: print `df.columns` and rename the names in `load_history.py` (the five used there are `date`, `team_home`, `team_away`, `goals_home`, `goals_away`).

### Step 5: Train the model

Create **`modeling.py`**:

```python
"""Train Dixon-Coles models, turn their output into probabilities, and score them."""
import math
from datetime import datetime, timezone
import numpy as np
import pandas as pd
import penaltyblog as pb
from config import MODELS_DIR, XI, seasons_to_load
from db import connect

OUTCOMES = ("H", "D", "A")


def load_matches(conn, league: str, seasons: list[str]) -> pd.DataFrame:
    marks = ",".join("?" * len(seasons))
    df = pd.read_sql_query(
        f"SELECT * FROM matches WHERE league = ? AND season IN ({marks}) ORDER BY match_date",
        conn, params=[league, *seasons],
    )
    df["match_date"] = pd.to_datetime(df["match_date"])
    return df


def fit_model(df: pd.DataFrame):
    weights = pb.models.dixon_coles_weights(df["match_date"], xi=XI)
    model = pb.models.DixonColesGoalModel(
        df["home_goals"].values, df["away_goals"].values, df["home"].values, df["away"].values, weights=weights
    )
    model.fit()
    return model


def forecast(model, home: str, away: str) -> dict:
    """Probabilities for one match. Raises ValueError if a team was not in the training data."""
    grid = model.predict(home, away)
    p_home, p_draw, p_away = (float(x) for x in grid.home_draw_away)
    return {
        "p_home": p_home, "p_draw": p_draw, "p_away": p_away,
        "p_over25": float(grid.total_goals("over", 2.5)), "p_btts": float(grid.btts_yes),
        "xg_home": float(grid.home_goal_expectation), "xg_away": float(grid.away_goal_expectation),
    }


def outcome_of(home_goals: int, away_goals: int) -> str:
    return "H" if home_goals > away_goals else "A" if home_goals < away_goals else "D"


# ---- scoring rules (lower is better) ----
def log_loss(p_event: float) -> float:
    """-ln(probability given to what actually happened)."""
    return -math.log(max(p_event, 1e-12))


def rps_1x2(probs: tuple[float, float, float], outcome: str) -> float:
    """Ranked probability score for the ordered outcomes Home, Draw, Away."""
    obs = [1.0 if o == outcome else 0.0 for o in OUTCOMES]
    cum_p, cum_o, total = 0.0, 0.0, 0.0
    for i in range(2):  # the last cumulative term is always 0
        cum_p += probs[i]
        cum_o += obs[i]
        total += (cum_p - cum_o) ** 2
    return total / 2


def baseline_probs(df: pd.DataFrame) -> tuple[float, float, float]:
    """The 'no model' forecast: how often home wins, draws and away wins happened in the training data."""
    outcomes = [outcome_of(h, a) for h, a in zip(df["home_goals"], df["away_goals"])]
    n = len(outcomes)
    return tuple(outcomes.count(o) / n for o in OUTCOMES)


def train_all() -> None:
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    from config import LEAGUES
    with connect() as conn:
        for code in LEAGUES:
            df = load_matches(conn, code, seasons_to_load())
            if len(df) < 300:
                print(f"  {code}: only {len(df)} matches stored, skipping (need at least 300)")
                continue
            model = fit_model(df)
            model.save(str(MODELS_DIR / f"{code}.pkl"))
            (MODELS_DIR / f"{code}.trained_at").write_text(datetime.now(timezone.utc).isoformat())
            print(f"  {code}: trained on {len(df)} matches, {len(model.teams)} teams")


def load_model(code: str):
    path = MODELS_DIR / f"{code}.pkl"
    if not path.exists():
        return None, None
    stamp = (MODELS_DIR / f"{code}.trained_at").read_text() if (MODELS_DIR / f"{code}.trained_at").exists() else ""
    return pb.models.DixonColesGoalModel.load(str(path)), stamp
```

**What the model does, in plain words.** The Dixon-Coles model gives every team an *attack* strength and a *defence* strength, and the league one *home advantage*. For a match, it turns those into the expected goals for each side, then into the probability of every scoreline (0-0, 1-0, 2-1, ...). Adding up scorelines gives each market: Home win is every scoreline where home goals are higher, Over 2.5 is every scoreline with 3 or more goals, Both teams to score is every scoreline where both have at least 1. `dixon_coles_weights(dates, xi=0.001)` makes older matches count less, so a match from three seasons ago matters less than last month's. The value 0.001 is the one in penaltyblog's own example. One model is trained per league because teams in different leagues never play each other, so their strengths cannot be compared.

**What the scoring rules mean.** *Log loss*: minus the natural log of the probability you gave to what actually happened. Giving 100% to the right outcome scores 0; being confident and wrong is punished hard. *RPS* (ranked probability score): like log loss but it knows Home, Draw, Away are in order. For both, **lower is better**. The *baseline* is the no-model forecast: always say "home wins X%, draw Y%, away Z%" using the overall frequencies. A model is only useful if it beats that.

Run:

```
python cli.py train
```

**You should see:** one line per league, for example `PL: trained on 1243 matches, 25 teams` (illustrative numbers). The team count is above 20 because clubs promoted or relegated during the 4 seasons are included. Files `models/PL.pkl` and `models/PL.trained_at` appear.

Training takes seconds per league (about half a second in my test with simulated data; real data is similar in size).

### Step 6: Test the model before trusting it

Create **`evaluate.py`**:

```python
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
```

What it does: it takes the last completed season and, month by month (every 28 days), trains only on matches *before* that month and forecasts the matches *in* it. This is called a walk-forward test. The model never sees the results it is being tested on.

Run (about one to two minutes; around ten refits per league):

```
python cli.py evaluate
```

**You should see** a table with one row per league, for example (numbers are an illustration of the format, not a promise):

```
league     n  logloss model  baseline  RPS model  baseline
PL       370         1.0xxx    1.0xxx     0.2xxx    0.2xxx  PASS
       over 2.5: model 0.6xxx vs constant 0.6xxx | btts: model 0.6xxx vs constant 0.6xxx
```

**Acceptance rule for the MVP:** a league is allowed on the page only if it shows `PASS` (model beats baseline on both log loss and RPS). For Over 2.5 and Both teams to score, the model should also be lower than the "constant" column; if it is not for a market, do not show that market to testers (remove its column from `templates/index.html`).

If a league says `FAIL`: remove it from `LEAGUES` in `config.py`, or leave it out of what you show. Do not hide a failure. One season is a small sample, so small gaps between model and baseline are noise; a clear win (for example 0.01 or more lower in log loss) is a good sign, a tie is not.

### Step 7: Download upcoming fixtures and match team names (real-data checkpoint 3)

`sync_fixtures.py` already exists from step 3. Run it:

```
python cli.py sync-fixtures
```

How it works: for each league it calls `GET https://api.football-data.org/v4/competitions/{code}/matches` with the header `X-Auth-Token` and the filters `dateFrom` and `dateTo` (today to 7 days ahead), as described in the football-data.org documentation. It keeps matches with status `SCHEDULED` or `TIMED`. It waits 7 seconds between leagues because the free plan reportedly allows 10 requests per minute. Times are stored in UTC.

**You should see:** a line per league such as `PL: 10 upcoming fixtures stored`. A league can legitimately show 0 (international break, off-season).

| If you see | It means | Do this |
|---|---|---|
| `HTTP 403` for a league | Your plan cannot read it | Back to step 3 |
| `HTTP 429` | Too many requests | Wait one minute and run again |
| `HTTP 400` mentioning dates | The date window is rejected | Set `FIXTURE_DAYS_AHEAD = 3` in `config.py`, rerun |

**The team-name problem.** The two sources spell clubs differently: football-data.org writes `Manchester City FC` where football-data.co.uk (and so the model) writes `Man City`. The code in `names.py` matches the easy cases automatically (it ignores words like FC and AFC, ignores accents, and accepts a short name or a name contained in the longer one). The rest you fix by hand, once.

Run:

```
python cli.py check-names
```

**You should see** either `All team names are matched.` or a list like:

```
  [PL] Wolverhampton Wanderers FC   closest model names: ['Wolves', ...]
```

For each line, pick the right model name from the suggestions and add a row to `data/team_aliases.csv`:

```
fd_name,model_name
Wolverhampton Wanderers FC,Wolves
```

The left side must be copied exactly as printed; the right side must be one of the model names (they are the names in your `matches` table, so you can also look them up with the command below). Then run `python cli.py sync-fixtures` and `python cli.py check-names` again. Repeat until it prints `All team names are matched.`

To list the names the model knows for a league, for example the Premier League:

```
python cli.py teams PL
```

**A newly promoted club** may have no matches in your 4 seasons of data. Its fixtures will show "No forecast (not enough data)" on the page. This is correct behaviour: the model cannot predict a team it has never seen. Once that club has played top-flight matches this season and you run `load-history` and `train`, it gets forecasts.

### Step 8: Write forecasts

Create **`predict.py`** (it also holds the grading code used in step 10):

```python
"""Write probabilities for upcoming fixtures, and grade them once results are known."""
from datetime import datetime, timezone
from config import LEAGUES, seasons_to_load
from db import connect
from modeling import (baseline_probs, forecast, load_matches, load_model, log_loss, outcome_of, rps_1x2)


def make_predictions() -> None:
    now = datetime.now(timezone.utc)
    with connect() as conn:
        for code in LEAGUES:
            model, trained_at = load_model(code)
            if model is None:
                print(f"  {code}: no trained model yet (run 'train' first)")
                continue
            fixtures = conn.execute(
                """SELECT * FROM fixtures WHERE league = ? AND status IN ('SCHEDULED', 'TIMED')
                   AND kickoff_utc > ? AND home IS NOT NULL AND away IS NOT NULL""",
                (code, now.strftime("%Y-%m-%dT%H:%M:%SZ")),
            ).fetchall()
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
            print(f"  {code}: {done} predictions written, {skipped} skipped (team not in training data)")


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
```

Run:

```
python cli.py train
python cli.py predict
python cli.py status
```

**You should see:** `PL: 10 predictions written, 0 skipped` style lines, and `predictions:` greater than 0 in the status. Skipped means a team the model has never seen.

Each forecast is saved with the time it was made and the time its model was trained. For this MVP, running `predict` again before kickoff replaces the forecast with a fresh one; forecasts for matches that have already kicked off are never touched. (The stricter "lock and never change" rule is in section 11.)

### Step 9: The web page

Create **`app.py`**:

```python
"""The web app: one page plus a small JSON API. Start with:  uvicorn app:app --port 8080"""
import os
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path
from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.responses import HTMLResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.templating import Jinja2Templates
from config import LEAGUES
from db import connect

app = FastAPI(title="PitchProb")
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent / "templates"))
security = HTTPBasic(auto_error=False)


def require_login(credentials: HTTPBasicCredentials | None = Depends(security)) -> None:
    """If APP_PASSWORD is set in .env, every page asks for a username and password."""
    password = os.environ.get("APP_PASSWORD", "")
    if not password:
        return  # no password configured: open access (use the Cloudflare email lock instead)
    user = os.environ.get("APP_USERNAME", "pitchprob")
    ok = credentials is not None and secrets.compare_digest(
        credentials.username.encode(), user.encode()
    ) and secrets.compare_digest(credentials.password.encode(), password.encode())
    if not ok:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Login required",
                            headers={"WWW-Authenticate": "Basic"})


def _upcoming(conn) -> list[dict]:
    since = (datetime.now(timezone.utc) - timedelta(hours=3)).strftime("%Y-%m-%dT%H:%M:%SZ")
    rows = conn.execute(
        """SELECT f.fd_match_id, f.league, f.kickoff_utc, f.home_fd, f.away_fd, f.home, f.away,
                  p.p_home, p.p_draw, p.p_away, p.p_over25, p.p_btts, p.xg_home, p.xg_away, p.created_at
           FROM fixtures f LEFT JOIN predictions p ON p.fd_match_id = f.fd_match_id
           WHERE f.status IN ('SCHEDULED', 'TIMED') AND f.kickoff_utc >= ?
           ORDER BY f.kickoff_utc""", (since,)
    ).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["league_name"] = LEAGUES.get(d["league"], {}).get("name", d["league"])
        if d["p_home"] is None:
            d["note"] = "Team name not matched yet" if d["home"] is None or d["away"] is None else "No forecast (not enough data)"
        out.append(d)
    return out


def _ledger(conn) -> dict:
    row = conn.execute(
        """SELECT COUNT(*) AS n, AVG(logloss_1x2) AS ll, AVG(base_logloss_1x2) AS base_ll, AVG(rps_1x2) AS rps
           FROM grades"""
    ).fetchone()
    recent = conn.execute(
        """SELECT f.league, f.kickoff_utc, f.home, f.away, p.p_home, p.p_draw, p.p_away,
                  g.home_goals, g.away_goals, g.outcome, g.logloss_1x2
           FROM grades g JOIN fixtures f ON f.fd_match_id = g.fd_match_id
           JOIN predictions p ON p.fd_match_id = g.fd_match_id
           ORDER BY f.kickoff_utc DESC LIMIT 20"""
    ).fetchall()
    return {"summary": dict(row), "recent": [dict(r) for r in recent]}


@app.get("/healthz")
def healthz() -> dict:
    return {"status": "ok"}


@app.get("/", response_class=HTMLResponse, dependencies=[Depends(require_login)])
def home(request: Request):
    with connect() as conn:
        context = {"fixtures": _upcoming(conn), "ledger": _ledger(conn), "leagues": LEAGUES}
    return templates.TemplateResponse(request, "index.html", context)


@app.get("/api/fixtures", dependencies=[Depends(require_login)])
def api_fixtures() -> list[dict]:
    with connect() as conn:
        return _upcoming(conn)


@app.get("/api/ledger", dependencies=[Depends(require_login)])
def api_ledger() -> dict:
    with connect() as conn:
        return _ledger(conn)
```

Create **`templates/index.html`**:

```html
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>PitchProb</title>
  <style>
    body { font-family: system-ui, sans-serif; margin: 1rem auto; max-width: 960px; padding: 0 1rem; color: #1b1b1b; }
    table { border-collapse: collapse; width: 100%; margin-bottom: 2rem; }
    th, td { text-align: left; padding: .45rem .6rem; border-bottom: 1px solid #ddd; font-size: .95rem; }
    th { background: #f4f4f4; }
    .num { text-align: right; font-variant-numeric: tabular-nums; }
    .muted { color: #666; }
    .wrap { overflow-x: auto; }
  </style>
</head>
<body>
  <h1>PitchProb</h1>
  <p class="muted">Probabilities from a statistical model. They are estimates, not betting advice. 18+ only.</p>

  <h2>Upcoming matches</h2>
  <div class="wrap">
  <table>
    <tr><th>Kickoff (UTC)</th><th>League</th><th>Match</th>
        <th class="num">Home</th><th class="num">Draw</th><th class="num">Away</th>
        <th class="num">Over 2.5</th><th class="num">Both score</th></tr>
    {% for f in fixtures %}
    <tr>
      <td>{{ f.kickoff_utc.replace("T", " ").replace("Z", "") }}</td>
      <td>{{ f.league_name }}</td>
      <td>{{ f.home or f.home_fd }} v {{ f.away or f.away_fd }}</td>
      {% if f.p_home is not none %}
        <td class="num">{{ "%.0f"|format(f.p_home * 100) }}%</td>
        <td class="num">{{ "%.0f"|format(f.p_draw * 100) }}%</td>
        <td class="num">{{ "%.0f"|format(f.p_away * 100) }}%</td>
        <td class="num">{{ "%.0f"|format(f.p_over25 * 100) }}%</td>
        <td class="num">{{ "%.0f"|format(f.p_btts * 100) }}%</td>
      {% else %}
        <td colspan="5" class="muted">{{ f.note }}</td>
      {% endif %}
    </tr>
    {% else %}
    <tr><td colspan="8" class="muted">No upcoming matches stored yet. Run the daily command.</td></tr>
    {% endfor %}
  </table>
  </div>

  <h2>Track record</h2>
  {% if ledger.summary.n %}
    <p>{{ ledger.summary.n }} graded matches. Average log loss (lower is better):
       model {{ "%.3f"|format(ledger.summary.ll) }} vs no-model baseline {{ "%.3f"|format(ledger.summary.base_ll) }}.</p>
    <div class="wrap">
    <table>
      <tr><th>Date</th><th>Match</th><th>Result</th><th class="num">Home</th><th class="num">Draw</th><th class="num">Away</th></tr>
      {% for g in ledger.recent %}
      <tr>
        <td>{{ g.kickoff_utc[:10] }}</td><td>{{ g.home }} v {{ g.away }}</td>
        <td>{{ g.home_goals }}-{{ g.away_goals }}</td>
        <td class="num">{{ "%.0f"|format(g.p_home * 100) }}%</td>
        <td class="num">{{ "%.0f"|format(g.p_draw * 100) }}%</td>
        <td class="num">{{ "%.0f"|format(g.p_away * 100) }}%</td>
      </tr>
      {% endfor %}
    </table>
    </div>
  {% else %}
    <p class="muted">No matches graded yet. Results appear here after matches finish and the daily command runs.</p>
  {% endif %}
</body>
</html>
```

Start the server:

```
uvicorn app:app --port 8080
```

**You should see:** `Uvicorn running on http://127.0.0.1:8080`. Open http://127.0.0.1:8080 in your browser.

**You should see:** the heading PitchProb, a table "Upcoming matches" with percentages, and "Track record" saying no matches graded yet. Also open http://127.0.0.1:8080/api/fixtures (the same data as JSON) and http://127.0.0.1:8080/healthz (`{"status":"ok"}`). Stop the server with Ctrl+C.

What each part does:

- `app.py` has four routes: `/` (the page), `/api/fixtures`, `/api/ledger`, `/healthz`. It reads the database on each request. Jinja2 (the template engine) escapes text automatically, so team names cannot inject HTML.
- If you add `APP_PASSWORD=...` to `.env`, the browser asks for a username (default `pitchprob`, change with `APP_USERNAME`) and that password before showing anything. Restart the server after editing `.env`.

### Step 10: Grade forecasts and set up your daily routine

Grading is already in `predict.py`. After matches finish, their results appear in the `matches` table the next time you run `load-history` (the website football-data.co.uk publishes new results on its own schedule; I could not verify how often, so expect a delay of a day or more).

```
python cli.py load-history
python cli.py grade
```

**You should see:** `N predictions graded`. N is 0 until some forecasted matches have finished and the results have been published.

For each graded match the code stores the log loss and RPS of the model and the log loss of the baseline computed only from matches played *before* that match's date. The page then shows the average model log loss next to the baseline.

**Your daily routine** is one command, run once a day while you are testing:

```
python cli.py daily
```

It runs: download recent results, download fixtures, retrain, write forecasts, grade. It re-downloads only the last two seasons to stay quick. Making this automatic (a scheduled task) is a later step.

### Step 11: Let three testers open it

Your computer must stay on and connected while they use it. The address changes every time you start the tunnel, per the Cloudflare documentation.

1. Start the app in one terminal:

   ```
   uvicorn app:app --port 8080
   ```

2. Open a **second** terminal and start the tunnel, locked to your three testers' email addresses (command and flag from Cloudflare's Quick Tunnels documentation):

   ```
   cloudflared tunnel --url http://localhost:8080 --allowed-mail tester1@example.com --allowed-mail tester2@example.com --allowed-mail tester3@example.com
   ```

3. `cloudflared` prints a random `https://....trycloudflare.com` address. Send it to your testers. Each visitor enters their email and a one-time PIN sent to that email before the page opens, and the documentation says they do not need a Cloudflare account.
4. Stop sharing by pressing Ctrl+C in the tunnel terminal: access ends for everyone.

Notes from the documentation: Quick Tunnels have no uptime guarantee, are meant for testing, and email authentication needs a browser (not a script). A third-party guide says `--allowed-mail` needs a `cloudflared` release from October 2026 or later: check with `cloudflared --version`, and update if the flag is not recognised. As a second lock (or if the flag is unavailable), set `APP_PASSWORD` in `.env` and give your testers that password.

If the page shows an error through the tunnel but works locally, try `http://127.0.0.1:8080` instead of `localhost` in the tunnel command (a Cloudflare-related guide mentions this fix for systems where `localhost` resolves to IPv6 first).

### Step 12: Run the automatic tests

Create **`tests/test_pipeline.py`**:

```python
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
    assert client.get("/healthz").json() == {"status": "ok"}
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
            team = lambda i, n, s: {"id": i, "name": n, "shortName": s, "tla": "XXX"}
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
    assert len(rows) == 1 and rows[0]["home"] == "Arsenal" and rows[0]["away"] == "Chelsea"


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


def test_teams_command(env, capsys):
    import cli
    store(make_history(datetime.now(timezone.utc).date()))
    cli.teams("PL")
    assert "Man City" in capsys.readouterr().out
    with pytest.raises(SystemExit):
        cli.teams(None)
```

Run:

```
python -m pytest -q
```

**You should see:** `7 passed`. NumPy deprecation warnings may appear; they come from a library and do not affect results (they were present in my runs). The tests use invented data in a temporary folder, so they never touch your real database.

The tests are your safety net: after any change to the code, run them again.

---

## 7. Final acceptance checklist

Tick every item before showing the page to testers.

- [ ] `python cli.py check-access` shows `OK` for every league you kept
- [ ] `python cli.py status` shows 380 (PL, PD, SA) or 306 (BL1, FL1) matches for each completed season
- [ ] `python cli.py train` trained a model for every league you kept
- [ ] `python cli.py evaluate` shows `PASS` for every league you kept, and over-2.5 and both-teams-to-score columns beat the constant (or those columns are removed from the page)
- [ ] `python cli.py check-names` prints `All team names are matched.`
- [ ] The page lists upcoming matches with probabilities that add to about 100% across Home, Draw, Away
- [ ] The page says forecasts are estimates, not betting advice, and 18+ only
- [ ] `python -m pytest -q` shows `7 passed`
- [ ] The page is protected (Cloudflare email lock or `APP_PASSWORD`)
- [ ] You ran `python cli.py daily` successfully at least once from start to end

---

## 8. Troubleshooting

| Problem | Likely cause | Fix |
|---|---|---|
| `python: command not found` / `'python' is not recognized` | Virtual environment not active | Activate it (step 1); the prompt must start with `(.venv)` |
| `ModuleNotFoundError: No module named 'penaltyblog'` | Libraries not installed in this environment | Activate `.venv`, then `pip install -r requirements.txt` |
| `ModuleNotFoundError: No module named 'config'` | Running from the wrong folder | `cd` into `pitchprob` first |
| `could not download (...)` in step 4 | Season file missing or no internet | See step 4; try again later |
| `train` says no finished matches are stored | History has not been loaded for the training seasons | Run `python cli.py load-history`, check `python cli.py status`, then retry `python cli.py train` |
| `train` says "only N matches stored, skipping" | Not enough data loaded | Run `load-history`; check `status` counts |
| Forecasts show "Team name not matched yet" | Name differs between sources | Step 7 alias file |
| Forecasts show "No forecast (not enough data)" | Team has no history (newly promoted) | Normal; wait for matches, then `load-history` + `train` |
| Page empty | No fixtures stored or forecasts not written | Run `daily`; check `status` |
| Address already in use | Port 8080 taken | Use another port, e.g. `--port 8090`, and use it in the tunnel too |
| `database is locked` | Two programs writing at once | Stop the other program, retry |

---

## 9. How long this should take

My estimate, not a measured figure: about two to three evenings if copy-pasting carefully: setup and data (1 evening), model and tests (1 evening), fixtures, names, page and sharing (1 evening). Name matching can take longer in the first week of a season, when promoted clubs appear.

---

## 10. Plain-language glossary

- **API:** a way for programs to ask another service for data over the internet.
- **Token:** a password-like string that identifies you to an API.
- **Virtual environment (`.venv`):** a private folder of Python libraries for one project.
- **SQLite:** a database stored in one file.
- **Endpoint:** one web address of an API, such as `/api/fixtures`.
- **Probability:** a number between 0 and 1 (or 0% and 100%) for how likely something is. These forecasts are probabilities, not predictions of what *will* happen.
- **Baseline:** the simple forecast a model must beat to be worth using.
- **Walk-forward test:** replaying the past one step at a time so the model never sees the future.
- **Log loss / RPS:** scores for forecasts; lower is better.
- **UTC:** the standard time zone used for stored kickoff times.

---

## 11. Held for later: how this MVP grows into your system design

| Later feature (from your design) | First step when you are ready |
|---|---|
| Lock forecasts one hour before kickoff, tamper-proof history | Stop updating a forecast within 60 minutes of kickoff, add a `locked_at` column and a database rule that refuses edits |
| Scheduler and job queue | Windows Task Scheduler or cron running `python cli.py daily`; later a job table in PostgreSQL |
| Accounts, free and Pro, payments | Move to PostgreSQL, add sign-in, then a payment provider |
| Alerts (Telegram, WhatsApp) | A notifications table plus a sender job |
| Match cards, season simulations | New jobs reading the same tables |
| Public API and embeds | Add keys and rate limits to `/api/*` |
| CDN and caching | Put Cloudflare in front of a real server |
| More leagues, lineups, injuries | Add to `LEAGUES`; a paid data source for lineups |
| Hosting on a server | A small Linux server running `uvicorn` and a scheduled `daily` job |

---

## 12. Sources and what each one confirmed

- football-data.org v4 documentation, competition resource: https://docs.football-data.org/general/v4/competition.html (matches endpoint, `season`, `status`, `dateFrom`, `dateTo`, `X-Auth-Token`, competition list shows which competitions your token can access)
- football-data.org v4 documentation, match resource: https://docs.football-data.org/general/v4/match.html (fields `utcDate`, `status`, `homeTeam.name`, `homeTeam.shortName`, `score.fullTime`; statuses SCHEDULED, TIMED, IN_PLAY, PAUSED, FINISHED, SUSPENDED, POSTPONED, CANCELLED, AWARDED)
- football-data.org API policies (date defaults to UTC, current season = latest start date): https://docs.football-data.org/general/v4/policies.html
- Free-plan limits (third-party summaries, **confirm officially**): https://www.thestatsapi.com/blog/football-data-org-free-tier-limits-2026 and https://bruin-data.github.io/ingestr/soccer-sources/football-data-org.html; official pages https://www.football-data.org/pricing and https://www.football-data.org/coverage
- penaltyblog downloader for football-data.co.uk: https://penaltyblog.readthedocs.io/en/latest/scrapers/footballdata.html (competition names, season format `2021-2022`, column names)
- penaltyblog goal models end-to-end example: https://penaltyblog.readthedocs.io/en/latest/models/example.html (`dixon_coles_weights`, `DixonColesGoalModel`, `fit`, `predict`, `home_draw_away`, `total_goals("over", 2.5)`, `btts_yes`, `home_goal_expectation`, `save`/`load`)
- Cloudflare Quick Tunnels: https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/ and https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/do-more-with-tunnels/trycloudflare/ (command, random address, email lock option, limitations)
- Cloudflare tunnel downloads: https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/downloads/
- Python downloads: https://www.python.org/downloads/ ; FastAPI: https://fastapi.tiangolo.com (not fetched this session; the code was verified by running it instead)

**Still unverified, listed once more:** live downloads from both providers; existence of the current-season file; free-plan access to your five leagues (step 3 checks it); team-name differences (step 7 handles it); PowerShell activation behaviour; the licence and terms of both data sources for anything beyond private testing.
