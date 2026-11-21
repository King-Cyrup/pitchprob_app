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
    "PL": {"name": "Premier League", "fd_code": "PL", "pb_name": "ENG Premier League",
           "emblem_url": "https://crests.football-data.org/PL.png", "kind": "club"},
    "PD": {"name": "La Liga", "fd_code": "PD", "pb_name": "ESP La Liga",
           "emblem_url": "https://crests.football-data.org/PD.png", "kind": "club"},
    "SA": {"name": "Serie A", "fd_code": "SA", "pb_name": "ITA Serie A",
           "emblem_url": "https://crests.football-data.org/SA.png", "kind": "club"},
    "BL1": {"name": "Bundesliga", "fd_code": "BL1", "pb_name": "DEU Bundesliga 1",
            "emblem_url": "https://crests.football-data.org/BL1.png", "kind": "club"},
    "FL1": {"name": "Ligue 1", "fd_code": "FL1", "pb_name": "FRA Ligue 1",
            "emblem_url": "https://crests.football-data.org/FL1.png", "kind": "club"},
    "CL": {"name": "Champions League", "fd_code": "CL", "pb_name": None,
           "emblem_url": "https://crests.football-data.org/CL.png", "kind": "club"},
    "UNL": {"name": "UEFA Nations League", "fd_code": "UNL", "pb_name": None,
            "emblem_url": None, "kind": "national"},
}

FOOTBALL_DATA_TOKEN = os.environ.get("FOOTBALL_DATA_TOKEN", "")
FD_BASE_URL = "https://api.football-data.org/v4"

XI = 0.0019           # time-decay rate in Dixon-Coles weighting; emphasises recent results
TRAIN_WINDOW_DAYS = 1095
SEASONS_BACK = 3      # how many completed seasons to train on (plus the current one)
FIXTURE_DAYS_AHEAD = 7
LOCK_MINUTES = 60     # forecasts are frozen this many minutes before kickoff (tamper-proof)

# ── Step feature flags ─────────────────────────────────────────────────────────
# All start False. Set to True only after `python cli.py compare` says "adopt".
USE_ELO_BLEND = False        # Step 2: blend Dixon-Coles with Elo ratings (club leagues only)
USE_PLATT = False            # Step 3: Platt recalibration for Over/Under and BTTS
USE_NB_CORNERS = False       # Step 5: negative-binomial corner model instead of Poisson
ELO_BLEND_WEIGHT = 0.5      # Step 2: weight for Elo in the blend (0.35 and 0.5 tested; both adopted)


def season_label(d: date) -> str:
    """European seasons start in July/August: 2026-10-28 -> '2026-2027'."""
    start = d.year if d.month >= 7 else d.year - 1
    return f"{start}-{start + 1}"


def seasons_to_load(today: date | None = None) -> list[str]:
    today = today or date.today()
    start = int(season_label(today)[:4])
    return [f"{y}-{y + 1}" for y in range(start - SEASONS_BACK, start + 1)]