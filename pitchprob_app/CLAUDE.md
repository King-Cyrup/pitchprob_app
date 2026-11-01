# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

PitchProb is a football match-probability forecaster. It trains Dixon-Coles models on
historical results, produces Home/Draw/Away (plus over-2.5 and both-teams-to-score)
probabilities for upcoming fixtures, and grades past forecasts against real results. It
exposes a single-page FastAPI site plus a small JSON API.

## Commands

```bash
pip install -r requirements.txt     # deps: penaltyblog, fastapi[standard], requests, pandas, numpy, scipy, pytest

python cli.py <command>             # the CLI entry point (see pipeline below)
python cli.py daily                 # run the whole pipeline end-to-end

python -m pytest -q                 # run all tests (7 tests)
python -m pytest tests/test_pipeline.py::test_metrics -q   # run a single test

uvicorn app:app --port 8080         # run the web app
```

`python cli.py` subcommands: `init-db`, `check-access`, `load-history`, `sync-fixtures`,
`check-names`, `train`, `evaluate`, `predict`, `grade`, `daily`, `status`, `teams <CODE>`.
The optional `league` argument is only used by `teams`.

## Architecture

The app is a linear pipeline over a single SQLite database. Each `cli.py` subcommand is one
stage, and `daily` runs them in order:

```
load-history -> sync-fixtures -> train -> predict -> grade
```

- **Two data sources feed the app, and their team names disagree.** Historical results come
  from football-data.co.uk via the `penaltyblog` scraper (`load_history.py`), and upcoming
  fixtures come from the football-data.org REST API (`sync_fixtures.py`, needs
  `FOOTBALL_DATA_TOKEN`). The same club is written differently in each (e.g. "Arsenal FC" vs
  "Arsenal"), so `names.py` normalizes names and resolves them against a per-league set of
  model names plus manual overrides in `data/team_aliases.csv`.

- **`config.py` is the single source of truth** and is executed at import time. `LEAGUES`
  maps a short code (`PL`, `PD`, `SA`, `BL1`, `FL1`) to three naming systems: `name` (display),
  `fd_code` (football-data.org competition code), and `pb_name` (football-data.co.uk /
  penaltyblog name). `.env` is loaded manually here (not python-dotenv) into `os.environ`, so
  any module that reads config at import assumes `.env` is already present. Other tuning knobs
  live here too: `XI` (time-decay rate), `SEASONS_BACK` (3), `FIXTURE_DAYS_AHEAD` (7).

- **SQLite schema** (`db.py`) has four tables, in pipeline order: `matches` (finished results,
  the training data), `fixtures` (upcoming matches — note the dual columns `home_fd`/`away_fd`
  for the football-data.org spelling and `home`/`away` for the model spelling, `NULL` = not yet
  matched), `predictions` (per-fixture probabilities), `grades` (scored results). `connect()`
  returns a `sqlite3.Row` connection with foreign keys on.

- **Modeling** (`modeling.py`) fits one `penaltyblog` Dixon-Coles model per league and saves it
  to `models/{CODE}.pkl` with a sibling `{CODE}.trained_at` timestamp. Training skips a league
  with fewer than 300 matches. Scoring uses log loss and ranked probability score (RPS), always
  against a "baseline" (the no-model historical home/draw/away frequency).

- **Evaluation** (`evaluate.py`) is a walk-forward backtest on the *previous* season: it refits
  every 28 days and compares the model to the baseline. The pass criterion printed by
  `python cli.py evaluate` is that the model beats the baseline on both log loss and RPS.

- **Web app** (`app.py`) serves `/` (Jinja2 template `templates/index.html`) plus
  `/api/fixtures`, `/api/ledger`, and `/healthz`. Access is gated by optional HTTP Basic auth:
  set `APP_PASSWORD` (and optionally `APP_USERNAME`) in `.env` to enable it; unset leaves it
  open. All template context is built in `app.py` from the `fixtures`/`predictions`/`grades`
  tables.

## Tests

`tests/test_pipeline.py` is the only test file. It is end-to-end and synthetic: the `env`
fixture monkeypatches `DATA_DIR`/`DB_PATH`/`MODELS_DIR`/`ALIASES_PATH` to a `tmp_path`, and
HTTP calls are faked by replacing `requests.get` / the scraper. `test_full_pipeline` exercises
the real train → evaluate → predict → grade path with invented history, then asserts the web
page renders and that auth returns 401/200 correctly.

`note.md` is a manual acceptance checklist (a "definition of done") for the deployed app —
worth consulting when verifying behavior end-to-end.
