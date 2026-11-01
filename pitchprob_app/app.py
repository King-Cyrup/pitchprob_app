"""The web app: one page plus a small JSON API. Start with:  uvicorn app:app --port 8080"""
import os
import secrets
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.responses import HTMLResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.templating import Jinja2Templates
from config import LEAGUES, LOCK_MINUTES
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
        lock_cutoff = (datetime.now(timezone.utc) + timedelta(minutes=LOCK_MINUTES)).strftime("%Y-%m-%dT%H:%M:%SZ")
        d["locked"] = d["kickoff_utc"] <= lock_cutoff and d["p_home"] is not None
        if d["p_home"] is None:
            d["note"] = "Team name not matched yet" if d["home"] is None or d["away"] is None else "No forecast (not enough data)"
        out.append(d)
    return out


def _fixture_days(fixtures: list[dict], today: date | None = None) -> list[dict]:
    today = today or datetime.now(timezone.utc).date()
    weekdays = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
    preferred_order = ("FL1", "BL1", "PD", "PL")
    by_date: dict[str, dict[str, list[dict]]] = {}
    for fixture in fixtures:
        day = fixture["kickoff_utc"][:10]
        by_date.setdefault(day, {}).setdefault(fixture["league"], []).append(fixture)

    days = []
    for offset in range(7):
        current = today + timedelta(days=offset)
        league_fixtures = by_date.get(current.isoformat(), {})
        league_codes = [code for code in preferred_order if code in league_fixtures]
        league_codes.extend(code for code in LEAGUES if code in league_fixtures and code not in preferred_order)
        days.append({
            "date": current.isoformat(),
            "label": ("Today", "Tomorrow")[offset] if offset < 2 else weekdays[current.weekday()],
            "month": current.strftime("%b"),
            "day": current.day,
            "leagues": [
                {
                    "code": code,
                    "name": LEAGUES.get(code, {}).get("name", code),
                    "fixtures": league_fixtures[code],
                }
                for code in league_codes
            ],
        })
    return days


def _ledger(conn) -> dict:
    row = conn.execute(
        """SELECT COUNT(*) AS n, AVG(logloss_1x2) AS ll, AVG(base_logloss_1x2) AS base_ll, AVG(rps_1x2) AS rps
           FROM grades"""
    ).fetchone()
    summary = dict(row)
    pr = conn.execute(
        """SELECT AVG(CASE WHEN g.outcome =
                   CASE WHEN p.p_home >= p.p_draw AND p.p_home >= p.p_away THEN 'H'
                        WHEN p.p_draw >= p.p_away THEN 'D' ELSE 'A' END
                   THEN 1.0 ELSE 0.0 END)
           FROM grades g JOIN predictions p ON p.fd_match_id = g.fd_match_id"""
    ).fetchone()
    summary["pick_rate"] = pr[0]
    recent = conn.execute(
        """SELECT f.league, f.kickoff_utc, f.home, f.away, p.p_home, p.p_draw, p.p_away,
                  g.home_goals, g.away_goals, g.outcome, g.logloss_1x2
           FROM grades g JOIN fixtures f ON f.fd_match_id = g.fd_match_id
           JOIN predictions p ON p.fd_match_id = g.fd_match_id
           ORDER BY f.kickoff_utc DESC LIMIT 20"""
    ).fetchall()
    return {"summary": summary, "recent": [dict(r) for r in recent]}


@app.get("/healthz")
def healthz() -> dict:
    from config import MODELS_DIR, LEAGUES as _LEAGUES
    try:
        with connect() as conn:
            n_fixtures = conn.execute("SELECT COUNT(*) FROM fixtures").fetchone()[0]
            n_predictions = conn.execute("SELECT COUNT(*) FROM predictions").fetchone()[0]
            n_grades = conn.execute("SELECT COUNT(*) FROM grades").fetchone()[0]
    except Exception:
        return {"status": "degraded", "db": "unreachable"}
    models = {}
    for code in _LEAGUES:
        stamp = MODELS_DIR / f"{code}.trained_at"
        if stamp.exists():
            models[code] = stamp.read_text().strip()[:19]  # ISO timestamp
        else:
            models[code] = None
    return {
        "status": "ok",
        "db": {"fixtures": n_fixtures, "predictions": n_predictions, "grades": n_grades},
        "models": models,
    }


@app.get("/", response_class=HTMLResponse, dependencies=[Depends(require_login)])
def home(request: Request):
    with connect() as conn:
        fixtures = _upcoming(conn)
        context = {
            "fixture_days": _fixture_days(fixtures),
            "ledger": _ledger(conn),
            "leagues": LEAGUES,
        }
    return templates.TemplateResponse(request, "index.html", context)


@app.get("/api/fixtures", dependencies=[Depends(require_login)])
def api_fixtures() -> list[dict]:
    with connect() as conn:
        return _upcoming(conn)


@app.get("/api/ledger", dependencies=[Depends(require_login)])
def api_ledger() -> dict:
    with connect() as conn:
        return _ledger(conn)
