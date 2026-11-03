# PitchProb

Football match probability forecasting — trains Dixon-Coles statistical models on
historical results and shows Home / Draw / Away, Over 2.5, and Both Teams to Score
probabilities for upcoming matches from Europe's top five leagues and the Champions League.

Built with Python, [FastAPI](https://fastapi.tiangolo.com), SQLite, and
[penaltyblog](https://penaltyblog.readthedocs.io).

## Quick start

```bash
# 1. Install
pip install -r requirements.txt

# 2. Add your football-data.org API token to .env
echo 'FOOTBALL_DATA_TOKEN=your-token' > .env          # Linux / Mac / WSL
# or:  Set-Content .env 'FOOTBALL_DATA_TOKEN=your-token'   (PowerShell)

# 3. Initialize the database
python cli.py init-db

# 4. Check your token can read the configured leagues
python cli.py check-access

# 5. Run the full pipeline (one-time bare-metal test)
python cli.py daily

# 6. Start the web server
uvicorn app:app --port 8080
```

Open http://127.0.0.1:8080 in a browser.

## CLI pipeline

Every command below works standalone. `daily` chains them.

```
load-history     Download finished matches from football-data.co.uk
sync-fixtures    Fetch upcoming fixtures from football-data.org
train            Train one Dixon-Coles model per league
predict          Write probabilities for upcoming fixtures
grade            Score old predictions against actual results

init-db          Create database tables
check-access     Verify your football-data.org API token
check-names      Find team names that need manual aliases
evaluate         Walk-forward backtest on the previous season
report [LEAGUE]  Print a results report with calibration bands
status           Show table counts
teams <CODE>     List the team names the model knows for a league
daily            Run the full pipeline end-to-end
```

The Champions League uses its bundled model (`models/CL.pkl`) for forecasts; its
upcoming fixtures are fetched from football-data.org. Domestic historical results
continue to be loaded from football-data.co.uk.

### Editing the league list

Edit `LEAGUES` in `config.py`. Each entry maps a short code to:
- `name` — display name
- `fd_code` — football-data.org competition code
- `pb_name` — football-data.co.uk / penaltyblog competition name

## Database

A single SQLite file at `data/pitchprob.db`. Four tables:

| Table       | Purpose                                             |
|-------------|-----------------------------------------------------|
| `matches`   | Finished results — the training data               |
| `fixtures`  | Upcoming matches from the API                       |
| `predictions` | Per-fixture probabilities from the model         |
| `grades`    | Scored predictions (log loss + RPS vs baseline)     |

## Tests

```bash
python -m pytest -q           # all tests (synthetic data, no live API calls)
python -m pytest tests/test_pipeline.py::test_metrics -q  # single test
```

## Optional: password-protect the page

Set in `.env`:

```
APPP_PASSWORD=choose-a-long-password
APPP_USERNAME=pitchprob     # default; change if you like
```

Restart the server after editing `.env`. The browser will ask for username + password.
Unset `APP_PASSWORD` (or remove the line) to leave the page open.

## Data sources

- **Historical results** from [football-data.co.uk](https://www.football-data.co.uk/) via the
  `penaltyblog` library.
- **Upcoming fixtures** from the [football-data.org](https://www.football-data.org/) free API.

## Disclaimer

Probabilities are estimates from a statistical model — not betting advice. 18+ only.