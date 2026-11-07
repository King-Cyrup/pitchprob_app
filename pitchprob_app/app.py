"""The web app: one page plus a small JSON API. Start with:  uvicorn app:app --port 8080"""
import os
import secrets
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from fastapi import Depends, FastAPI, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.templating import Jinja2Templates
from config import LEAGUES, LOCK_MINUTES
from db import connect, ensure_team_crests

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
    ensure_team_crests(conn)
    since = (datetime.now(timezone.utc) - timedelta(hours=3)).strftime("%Y-%m-%dT%H:%M:%SZ")
    rows = conn.execute(
        """SELECT f.fd_match_id, f.league, f.kickoff_utc, f.home_fd, f.away_fd, f.home, f.away,
                  home_crest.crest_url AS home_crest, away_crest.crest_url AS away_crest,
                  p.p_home, p.p_draw, p.p_away, p.p_over25, p.p_btts, p.xg_home, p.xg_away, p.created_at
           FROM fixtures f
           LEFT JOIN team_crests home_crest
             ON home_crest.league = f.league AND home_crest.team_fd = f.home_fd
           LEFT JOIN team_crests away_crest
             ON away_crest.league = f.league AND away_crest.team_fd = f.away_fd
           LEFT JOIN predictions p ON p.fd_match_id = f.fd_match_id
           WHERE f.status IN ('SCHEDULED', 'TIMED') AND f.kickoff_utc >= ?
           ORDER BY f.kickoff_utc""", (since,)
    ).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["league_name"] = LEAGUES.get(d["league"], {}).get("name", d["league"])
        d["kickoff_date"] = datetime.strptime(d["kickoff_utc"][:10], "%Y-%m-%d").strftime("%d %b")
        d["home_badge"] = _team_initials(d["home"] or d["home_fd"])
        d["away_badge"] = _team_initials(d["away"] or d["away_fd"])
        lock_cutoff = (datetime.now(timezone.utc) + timedelta(minutes=LOCK_MINUTES)).strftime("%Y-%m-%dT%H:%M:%SZ")
        d["locked"] = d["kickoff_utc"] <= lock_cutoff and d["p_home"] is not None
        if d["p_home"] is None:
            d["note"] = "Team name not matched yet" if d["home"] is None or d["away"] is None else "No forecast (not enough data)"
        out.append(d)
    _add_match_context(conn, out)
    return out


def _team_initials(name: str) -> str:
    words = [word for word in name.replace("&", " ").split() if word.casefold() not in {"fc", "afc", "cf", "sc"}]
    if len(words) < 2:
        return (words[0] if words else name)[:2].upper()
    return "".join(word[0] for word in words[:2]).upper()


def _add_match_context(conn, fixtures: list[dict]) -> None:
    """Attach recent team form and head-to-head results from the local match history."""
    teams = {
        (fixture["league"], team)
        for fixture in fixtures
        for team in (fixture.get("home"), fixture.get("away"))
        if team
    }
    pairs = {
        (fixture["league"], frozenset((fixture["home"], fixture["away"])))
        for fixture in fixtures
        if fixture.get("home") and fixture.get("away")
    }
    for fixture in fixtures:
        fixture["home_form"] = []
        fixture["away_form"] = []
        fixture["h2h"] = []
    if not teams:
        return

    leagues = sorted({league for league, _ in teams})
    placeholders = ",".join("?" for _ in leagues)
    history = conn.execute(
        f"""SELECT league, match_date, home, away, home_goals, away_goals
            FROM matches WHERE league IN ({placeholders})
            ORDER BY match_date DESC""",
        leagues,
    ).fetchall()

    forms: dict[tuple[str, str], list[str]] = {team: [] for team in teams}
    meetings: dict[tuple[str, frozenset[str]], list[dict]] = {pair: [] for pair in pairs}
    for row in history:
        match = dict(row)
        league = match["league"]
        for team, goals_for, goals_against in (
            (match["home"], match["home_goals"], match["away_goals"]),
            (match["away"], match["away_goals"], match["home_goals"]),
        ):
            form = forms.get((league, team))
            if form is not None and len(form) < 5:
                form.append("W" if goals_for > goals_against else "L" if goals_for < goals_against else "D")

        pair = (league, frozenset((match["home"], match["away"])))
        previous_meetings = meetings.get(pair)
        if previous_meetings is not None and len(previous_meetings) < 10:
            match["home_outcome"] = (
                "W" if match["home_goals"] > match["away_goals"]
                else "L" if match["home_goals"] < match["away_goals"]
                else "D"
            )
            previous_meetings.append(match)

    for fixture in fixtures:
        league = fixture["league"]
        home, away = fixture.get("home"), fixture.get("away")
        if home:
            fixture["home_form"] = forms.get((league, home), [])
        if away:
            fixture["away_form"] = forms.get((league, away), [])
        if home and away:
            fixture["h2h"] = []
            for match in meetings.get((league, frozenset((home, away))), []):
                outcome = match["home_outcome"]
                if match["home"] != home:
                    outcome = {"W": "L", "D": "D", "L": "W"}[outcome]
                fixture["h2h"].append({**match, "fixture_outcome": outcome})


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
                    "emblem_url": LEAGUES.get(code, {}).get("emblem_url"),
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


def _api_match(row) -> dict:
    match = dict(row)
    probabilities = None
    pick = None
    if match["p_home"] is not None:
        values = {
            "H": match["p_home"],
            "D": match["p_draw"],
            "A": match["p_away"],
        }
        pick = max(values, key=values.get)
        probabilities = {
            "p_home": match["p_home"],
            "p_draw": match["p_draw"],
            "p_away": match["p_away"],
            "p_over25": match["p_over25"],
            "p_btts": match["p_btts"],
            "xg_home": match["xg_home"],
            "xg_away": match["xg_away"],
            "model": "Dixon-Coles",
            "pick": pick,
            "pick_prob": values[pick],
        }

    result = None
    if match["home_goals"] is not None:
        result = {
            "home_goals": match["home_goals"],
            "away_goals": match["away_goals"],
            "outcome": match["outcome"],
        }

    return {
        "id": match["fd_match_id"],
        "league": match["league"],
        "league_name": LEAGUES.get(match["league"], {}).get("name", match["league"]),
        "league_emblem_url": LEAGUES.get(match["league"], {}).get("emblem_url"),
        "kickoff_utc": match["kickoff_utc"],
        "status": match["status"],
        "matchday": match["matchday"],
        "home": match["home"] or match["home_fd"],
        "away": match["away"] or match["away_fd"],
        "home_crest": match["home_crest"],
        "away_crest": match["away_crest"],
        "forecast": probabilities,
        "result": result,
        "pick_hit": pick == match["outcome"] if result and pick else None,
        "flags": [],
        "note": (
            "Team name not matched yet"
            if match["home"] is None or match["away"] is None
            else "No forecast available"
        ) if probabilities is None else None,
        "updated_at": match["prediction_created_at"] or match["updated_at"],
    }


_MATCH_SELECT = """
    SELECT f.fd_match_id, f.league, f.kickoff_utc, f.status, {matchday_select} AS matchday,
           f.home_fd, f.away_fd, f.home, f.away, f.updated_at,
           home_crest.crest_url AS home_crest, away_crest.crest_url AS away_crest,
           p.created_at AS prediction_created_at, p.p_home, p.p_draw, p.p_away,
           p.p_over25, p.p_btts, p.xg_home, p.xg_away,
           g.home_goals, g.away_goals, g.outcome
    FROM fixtures f
    LEFT JOIN team_crests home_crest
      ON home_crest.league = f.league AND home_crest.team_fd = f.home_fd
    LEFT JOIN team_crests away_crest
      ON away_crest.league = f.league AND away_crest.team_fd = f.away_fd
    LEFT JOIN predictions p ON p.fd_match_id = f.fd_match_id
    LEFT JOIN grades g ON g.fd_match_id = f.fd_match_id
"""


def _match_select(conn) -> str:
    ensure_team_crests(conn)
    columns = {row["name"] for row in conn.execute("PRAGMA table_info(fixtures)")}
    matchday_select = "f.matchday" if "matchday" in columns else "NULL"
    return _MATCH_SELECT.format(matchday_select=matchday_select)


def _parse_api_date(value: str | None) -> date:
    if value is None:
        return datetime.now(timezone.utc).date()
    try:
        parsed = date.fromisoformat(value)
    except ValueError as err:
        raise HTTPException(status_code=400, detail="date must use YYYY-MM-DD format") from err
    if parsed.isoformat() != value:
        raise HTTPException(status_code=400, detail="date must use YYYY-MM-DD format")
    return parsed


def _graded_rows(conn, day: str | None = None) -> list[dict]:
    filters = ["g.fd_match_id IS NOT NULL", "p.fd_match_id IS NOT NULL"]
    params: list[str] = []
    if day is not None:
        filters.append("substr(f.kickoff_utc, 1, 10) = ?")
        params.append(day)
    rows = conn.execute(
        _match_select(conn)
        + " WHERE " + " AND ".join(filters)
        + " ORDER BY f.kickoff_utc DESC",
        params,
    ).fetchall()
    return [_api_match(row) for row in rows]


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


@app.get("/api/matches", dependencies=[Depends(require_login)])
def api_matches(date_param: str | None = Query(default=None, alias="date")) -> dict:
    match_day = _parse_api_date(date_param)
    with connect() as conn:
        rows = conn.execute(
            _match_select(conn)
            + """ WHERE substr(f.kickoff_utc, 1, 10) = ?
                  ORDER BY f.kickoff_utc, f.league, f.home_fd""",
            (match_day.isoformat(),),
        ).fetchall()
    return {
        "date": match_day.isoformat(),
        "matches": [_api_match(row) for row in rows],
        "leagues": [
            {
                "code": code,
                "name": league["name"],
                "emblem_url": league.get("emblem_url"),
            }
            for code, league in LEAGUES.items()
        ],
    }


@app.get("/api/matches/{match_id}", dependencies=[Depends(require_login)])
def api_match(match_id: int) -> dict:
    with connect() as conn:
        row = conn.execute(
            _match_select(conn) + " WHERE f.fd_match_id = ?",
            (match_id,),
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Match not found")

        match = _api_match(row)
        context_fixture = {
            "league": match["league"],
            "home": row["home"],
            "away": row["away"],
        }
        _add_match_context(conn, [context_fixture])
        season_rows = conn.execute(
            """SELECT home, away, home_goals, away_goals
               FROM matches
               WHERE league = ? AND season = (
                   SELECT season FROM fixtures WHERE fd_match_id = ?
               ) AND match_date < ?
               ORDER BY match_date DESC""",
            (match["league"], match_id, match["kickoff_utc"][:10]),
        ).fetchall()

        points = defaultdict(int)
        games = defaultdict(int)
        goals = goals_against = 0
        for result in season_rows:
            home_goals, away_goals = result["home_goals"], result["away_goals"]
            goals += home_goals + away_goals
            games[result["home"]] += 1
            games[result["away"]] += 1
            if home_goals > away_goals:
                points[result["home"]] += 3
            elif home_goals < away_goals:
                points[result["away"]] += 3
            else:
                points[result["home"]] += 1
                points[result["away"]] += 1

        forecast = match["forecast"]
        details = {
            "goal_lines": {"2.5": forecast["p_over25"]} if forecast else {},
            "handicap": [],
            "scorelines": [],
            "context": {
                "form_home": context_fixture["home_form"],
                "form_away": context_fixture["away_form"],
                "h2h": [
                    {
                        "date": previous["match_date"],
                        "home": previous["home"],
                        "away": previous["away"],
                        "score": f'{previous["home_goals"]}-{previous["away_goals"]}',
                    }
                    for previous in context_fixture["h2h"][:5]
                ],
                "season_ppg_home": (
                    points[row["home"]] / games[row["home"]]
                    if row["home"] and games[row["home"]] else None
                ),
                "season_ppg_away": (
                    points[row["away"]] / games[row["away"]]
                    if row["away"] and games[row["away"]] else None
                ),
                "league_gpm": goals / len(season_rows) if season_rows else None,
            },
        }
    return {**match, "extras": details}


@app.get("/api/results/days", dependencies=[Depends(require_login)])
def api_result_days() -> list[dict]:
    with connect() as conn:
        rows = _graded_rows(conn)
    days: dict[str, dict[str, int]] = {}
    for match in rows:
        day = match["kickoff_utc"][:10]
        summary = days.setdefault(day, {"n": 0, "hits": 0})
        summary["n"] += 1
        summary["hits"] += int(bool(match["pick_hit"]))
    return [{"date": day, **summary} for day, summary in sorted(days.items(), reverse=True)]


@app.get("/api/results", dependencies=[Depends(require_login)])
def api_results(date_param: str | None = Query(default=None, alias="date")) -> dict:
    result_day = _parse_api_date(date_param)
    with connect() as conn:
        matches = _graded_rows(conn, result_day.isoformat())
    grouped: dict[str, dict] = {}
    for match in matches:
        group = grouped.setdefault(match["league"], {
            "code": match["league"],
            "name": match["league_name"],
            "emblem_url": match["league_emblem_url"],
            "matches": [],
        })
        group["matches"].append(match)
    hits = sum(bool(match["pick_hit"]) for match in matches)
    return {
        "date": result_day.isoformat(),
        "summary": {"n": len(matches), "hits": hits, "accuracy": hits / len(matches) if matches else None},
        "leagues": list(grouped.values()),
    }


@app.get("/api/insights", dependencies=[Depends(require_login)])
def api_insights(source: str = "live") -> dict:
    if source not in {"live", "backtest"}:
        raise HTTPException(status_code=400, detail="source must be live or backtest")

    if source == "backtest":
        return {
            "source": source,
            "available": False,
            "n": 0,
            "note": "Walk-forward backtest forecasts are not stored in this database.",
            "confidence": [],
            "thresholds": [],
            "calibration": [],
            "comparison": [],
            "leagues": [],
        }

    with connect() as conn:
        rows = conn.execute(
            """SELECT f.league, p.p_home, p.p_draw, p.p_away,
                      g.outcome, g.logloss_1x2, g.base_logloss_1x2
               FROM predictions p
               JOIN grades g ON g.fd_match_id = p.fd_match_id
               JOIN fixtures f ON f.fd_match_id = p.fd_match_id
               ORDER BY f.kickoff_utc"""
        ).fetchall()
        goal_rows = conn.execute(
            """SELECT league, COUNT(*) AS n,
                      AVG(home_goals + away_goals) AS goals_per_match
               FROM matches GROUP BY league ORDER BY league"""
        ).fetchall()

    scored = []
    for row in rows:
        probs = {"H": row["p_home"], "D": row["p_draw"], "A": row["p_away"]}
        pick = max(probs, key=probs.get)
        scored.append({
            "league": row["league"],
            "confidence": probs[pick],
            "lead": probs[pick] - sorted(probs.values())[-2],
            "hit": pick == row["outcome"],
            "logloss": row["logloss_1x2"],
            "baseline_logloss": row["base_logloss_1x2"],
        })

    confidence_bands = [(0.30, 0.40), (0.40, 0.50), (0.50, 0.60), (0.60, 0.70), (0.70, 1.01)]
    confidence = []
    for low, high in confidence_bands:
        band = [item for item in scored if low <= item["confidence"] < high]
        if band:
            confidence.append({
                "from": low,
                "to": min(high, 1.0),
                "n": len(band),
                "confidence": sum(item["confidence"] for item in band) / len(band),
                "hit_rate": sum(item["hit"] for item in band) / len(band),
            })

    lead_bands = [(0, 0.05), (0.05, 0.10), (0.10, 0.15), (0.15, 0.20), (0.20, 0.30), (0.30, 1.01)]
    thresholds = []
    for low, high in lead_bands:
        band = [item for item in scored if low <= item["lead"] < high]
        if band:
            thresholds.append({
                "from": low,
                "to": min(high, 1.0),
                "n": len(band),
                "hit_rate": sum(item["hit"] for item in band) / len(band),
            })

    calibration = confidence
    count = len(scored)
    comparison = []
    if scored:
        comparison = [
            {
                "model": "Dixon-Coles",
                "n": count,
                "logloss": sum(item["logloss"] for item in scored) / count,
                "pick_rate": sum(item["hit"] for item in scored) / count,
            },
            {
                "model": "Historical baseline",
                "n": count,
                "logloss": sum(item["baseline_logloss"] for item in scored) / count,
                "pick_rate": None,
            },
        ]

    return {
        "source": source,
        "available": True,
        "n": count,
        "confidence": confidence,
        "thresholds": thresholds,
        "calibration": calibration,
        "comparison": comparison,
        "leagues": [
            {
                "league": row["league"],
                "league_name": LEAGUES.get(row["league"], {}).get("name", row["league"]),
                "n": row["n"],
                "goals_per_match": row["goals_per_match"],
            }
            for row in goal_rows
        ],
    }
