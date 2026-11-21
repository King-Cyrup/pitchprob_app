"""The web app: one page plus a small JSON API. Start with:  uvicorn app:app --port 8080"""
import json
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
from modeling import home_advantage, load_model
from report import calibration_by_spread, fetch_results

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


def _league_accuracy(conn) -> list[dict]:
    rows = conn.execute(
        """SELECT f.league,
                  COUNT(*) AS n,
                  AVG(CASE WHEN g.outcome =
                       CASE WHEN p.p_home >= p.p_draw AND p.p_home >= p.p_away THEN 'H'
                            WHEN p.p_draw >= p.p_away THEN 'D' ELSE 'A' END
                       THEN 1.0 ELSE 0.0 END) AS pick_rate,
                  AVG(g.logloss_1x2) AS avg_logloss
           FROM grades g
           JOIN fixtures f ON f.fd_match_id = g.fd_match_id
           JOIN predictions p ON p.fd_match_id = g.fd_match_id
           GROUP BY f.league
           ORDER BY f.league"""
    ).fetchall()
    out = []
    for row in rows:
        out.append({
            "league": row["league"],
            "league_name": LEAGUES.get(row["league"], {}).get("name", row["league"]),
            "n": row["n"],
            "pick_rate": row["pick_rate"],
            "avg_logloss": row["avg_logloss"],
        })
    return out


def _matchday_summary(conn) -> list[dict]:
    columns = {row["name"] for row in conn.execute("PRAGMA table_info(fixtures)")}
    if "matchday" not in columns:
        return []
    rows = conn.execute(
        """SELECT f.matchday,
                  COUNT(*) AS n,
                  SUM(CASE WHEN g.outcome =
                        CASE WHEN p.p_home >= p.p_draw AND p.p_home >= p.p_away THEN 'H'
                             WHEN p.p_draw >= p.p_away THEN 'D' ELSE 'A' END
                        THEN 1 ELSE 0 END) AS hits
           FROM grades g
           JOIN fixtures f ON f.fd_match_id = g.fd_match_id
           JOIN predictions p ON p.fd_match_id = g.fd_match_id
           WHERE f.matchday IS NOT NULL
           GROUP BY f.matchday
           ORDER BY f.matchday DESC
           LIMIT 3"""
    ).fetchall()
    out = []
    for row in rows:
        n = row["n"]
        hits = row["hits"] or 0
        out.append({
            "matchday": row["matchday"],
            "n": n,
            "hits": hits,
            "accuracy": hits / n if n else None,
        })
    return out


def _home_advantage_summary() -> list[dict]:
    rows = []
    for code in LEAGUES:
        model, _ = load_model(code)
        adv = home_advantage(model=model) if model is not None else None
        if adv is not None:
            rows.append({
                "league": code,
                "league_name": LEAGUES.get(code, {}).get("name", code),
                "home_advantage": adv,
            })
    return rows


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
    return {
        "summary": summary,
        "recent": [dict(r) for r in recent],
        "league_accuracy": _league_accuracy(conn),
        "matchdays": _matchday_summary(conn),
        "home_advantages": _home_advantage_summary(),
        "spread_calibration": calibration_by_spread(fetch_results(conn)),
    }


def _competition_payload(code: str) -> dict:
    info = LEAGUES.get(code, {})
    return {
        "code": code,
        "name": info.get("name", code),
        "kind": info.get("kind", "club"),
        "emblem_url": info.get("emblem_url"),
    }


def _match_context(conn, league: str, home: str, away: str, before_date: str) -> dict:
    """Recent form and previous meetings for one fixture, read from the local history.

    Only matches played before the fixture are counted, so the panel never shows
    a result that had not happened yet. National-team competitions use the
    separate intl_matches table.
    """
    context = {"form_home": [], "form_away": [], "h2h": [], "season_ppg_home": None,
               "season_ppg_away": None, "league_gpm": None}
    if not home or not away:
        return context

    if LEAGUES.get(league, {}).get("kind") == "national":
        rows = conn.execute(
            """SELECT date, home_team AS home, away_team AS away, home_score AS home_goals,
                      away_score AS away_goals
               FROM intl_matches
               WHERE date < ? AND (home_team IN (?, ?) OR away_team IN (?, ?))
               ORDER BY date DESC LIMIT 40""",
            (before_date, home, away, home, away),
        ).fetchall()
    else:
        rows = conn.execute(
            """SELECT match_date AS date, home, away, home_goals, away_goals
               FROM matches
               WHERE league = ? AND match_date < ?
                 AND (home IN (?, ?) OR away IN (?, ?))
               ORDER BY match_date DESC LIMIT 40""",
            (league, before_date, home, away, home, away),
        ).fetchall()

    forms: dict[str, list[str]] = {home: [], away: []}
    meetings: list[dict] = []
    for row in rows:
        match = dict(row)
        for team, goals_for, goals_against in (
            (match["home"], match["home_goals"], match["away_goals"]),
            (match["away"], match["away_goals"], match["home_goals"]),
        ):
            form = forms.get(team)
            if form is not None and len(form) < 5:
                form.append("W" if goals_for > goals_against else "L" if goals_for < goals_against else "D")
        if (match["home"] == home and match["away"] == away) or (match["home"] == away and match["away"] == home):
            outcome = ("W" if match["home_goals"] > match["away_goals"]
                       else "L" if match["home_goals"] < match["away_goals"] else "D")
            if match["home"] != home:
                outcome = {"W": "L", "D": "D", "L": "W"}[outcome]
            meetings.append({**match, "score": f"{match['home_goals']}-{match['away_goals']}",
                             "fixture_outcome": outcome})
            if len(meetings) >= 10:
                break

    context["form_home"] = forms.get(home, [])
    context["form_away"] = forms.get(away, [])
    context["h2h"] = meetings

    # points per match and goals per match for the current season (club leagues only)
    if LEAGUES.get(league, {}).get("kind") != "national":
        season_rows = conn.execute(
            """SELECT home, away, home_goals, away_goals FROM matches
               WHERE league = ? AND match_date < ? AND (home IN (?, ?) OR away IN (?, ?))""",
            (league, before_date, home, away, home, away),
        ).fetchall()
        totals = {home: [0, 0], away: [0, 0]}
        goals = 0
        for row in season_rows:
            goals += row["home_goals"] + row["away_goals"]
            for team, scored, conceded in (
                (row["home"], row["home_goals"], row["away_goals"]),
                (row["away"], row["away_goals"], row["home_goals"]),
            ):
                if team in totals:
                    totals[team][0] += 3 if scored > conceded else 1 if scored == conceded else 0
                    totals[team][1] += 1
        for team, key in ((home, "season_ppg_home"), (away, "season_ppg_away")):
            points, played = totals[team]
            if played:
                context[key] = round(points / played, 2)
        if season_rows:
            context["league_gpm"] = round(goals / len(season_rows), 2)
    return context


def _api_match(row) -> dict:
    match = dict(row)
    competition = _competition_payload(match["league"])
    probabilities = None
    pick = None
    if match["p_home"] is not None:
        values = {
            "H": match["p_home"],
            "D": match["p_draw"],
            "A": match["p_away"],
        }
        pick = max(values, key=values.get)
        xg_total = None
        if match["xg_home"] is not None and match["xg_away"] is not None:
            xg_total = float(match["xg_home"]) + float(match["xg_away"])
        probabilities = {
            "p_home": match["p_home"],
            "p_draw": match["p_draw"],
            "p_away": match["p_away"],
            "p_over25": match["p_over25"],
            "p_btts": match["p_btts"],
            "over15": match.get("p_over15"),
            "exp_total": xg_total,
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
        "league_name": competition["name"],
        "league_emblem_url": competition["emblem_url"],
        "competition": {
            "code": competition["code"],
            "name": competition["name"],
            "kind": competition["kind"],
            "stage": match.get("matchday") if match.get("matchday") is not None else None,
            "emblem_url": competition["emblem_url"],
        },
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
    SELECT f.fd_match_id, f.league, f.season, f.kickoff_utc, f.status, {matchday_select} AS matchday,
           f.home_fd, f.away_fd, f.home, f.away, f.updated_at,
           home_crest.crest_url AS home_crest, away_crest.crest_url AS away_crest,
           p.created_at AS prediction_created_at, p.p_home, p.p_draw, p.p_away,
           p.p_over25, p.p_btts, p.xg_home, p.xg_away, p.p_over15,
           p.markets_json, p.corners_json,
           g.home_goals, g.away_goals, g.outcome,
           COALESCE(fm.neutral, 0) AS neutral,
           fm.stage AS stage
    FROM fixtures f
    LEFT JOIN team_crests home_crest
      ON home_crest.league = f.league AND home_crest.team_fd = f.home_fd
    LEFT JOIN team_crests away_crest
      ON away_crest.league = f.league AND away_crest.team_fd = f.away_fd
    LEFT JOIN predictions p ON p.fd_match_id = f.fd_match_id
    LEFT JOIN grades g ON g.fd_match_id = f.fd_match_id
    LEFT JOIN fixture_metadata fm ON fm.fd_match_id = f.fd_match_id
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


@app.get("/api/competitions", dependencies=[Depends(require_login)])
def api_competitions() -> list[dict]:
    return [
        {"code": code, "name": league.get("name", code), "kind": league.get("kind", "club"), "emblem_url": league.get("emblem_url")}
        for code, league in LEAGUES.items()
    ]


@app.get("/api/dates", dependencies=[Depends(require_login)])
def api_dates(from_date: str | None = Query(default=None, alias="from"), days: int = Query(default=14, ge=1, le=31)) -> list[dict]:
    start = _parse_api_date(from_date) if from_date else datetime.now(timezone.utc).date()
    with connect() as conn:
        rows = conn.execute(
            """SELECT substr(f.kickoff_utc, 1, 10) AS date, f.league, COUNT(*) AS n
                 FROM fixtures f
                 WHERE substr(f.kickoff_utc, 1, 10) BETWEEN ? AND ?
                 GROUP BY substr(f.kickoff_utc, 1, 10), f.league
                 ORDER BY substr(f.kickoff_utc, 1, 10), f.league""",
            (start.isoformat(), (start + timedelta(days=days - 1)).isoformat()),
        ).fetchall()
    by_date: dict[str, dict[str, object]] = {}
    for row in rows:
        day = row["date"]
        entry = by_date.setdefault(day, {"date": day, "total": 0, "by_competition": {}})
        entry["total"] = int(entry["total"]) + int(row["n"])
        entry["by_competition"][row["league"]] = int(row["n"])
    return [
        {"date": date_value, "total": int(item["total"]), "by_competition": item["by_competition"]}
        for date_value, item in sorted(by_date.items())
    ]


@app.get("/api/fixtures", dependencies=[Depends(require_login)])
def api_fixtures() -> list[dict]:
    with connect() as conn:
        return _upcoming(conn)


@app.get("/api/ledger", dependencies=[Depends(require_login)])
def api_ledger() -> dict:
    with connect() as conn:
        return _ledger(conn)


@app.get("/api/matches", dependencies=[Depends(require_login)])
def api_matches(date_param: str | None = Query(default=None, alias="date"), competition: str | None = None) -> dict:
    match_day = _parse_api_date(date_param)
    params: list[str] = [match_day.isoformat()]
    where = "substr(f.kickoff_utc, 1, 10) = ?"
    if competition:
        where += " AND f.league = ?"
        params.append(competition)
    with connect() as conn:
        rows = conn.execute(
            _match_select(conn)
            + f" WHERE {where} ORDER BY f.kickoff_utc, f.league, f.home_fd",
            params,
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


def _validation_for(conn, competition: str, market: str) -> dict | None:
    row = conn.execute(
        "SELECT n, model_loss, baseline_loss, status FROM market_validation WHERE competition = ? AND market = ?",
        (competition, market),
    ).fetchone()
    if row is None:
        return None
    return {
        "n": row["n"],
        "model_loss": row["model_loss"],
        "baseline_loss": row["baseline_loss"],
        "status": row["status"],
    }


def _forecast_with_lead(pred: dict) -> dict:
    """Add lead_points to a forecast dict."""
    values = [pred["p_home"], pred["p_draw"], pred["p_away"]]
    top = max(values)
    second = sorted(values)[-2]
    return {
        **pred,
        "pick": ("H" if top == pred["p_home"] else "D" if top == pred["p_draw"] else "A"),
        "lead_points": round((top - second) * 100),
        "model": "dixon_coles",
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

        # ---- base forecast ----
        p_home = row["p_home"]; p_draw = row["p_draw"]; p_away = row["p_away"]
        forecast = None
        pick = None
        if p_home is not None:
            values = {"H": p_home, "D": p_draw, "A": p_away}
            pick = max(values, key=values.get)
            xg_total = float(row["xg_home"]) + float(row["xg_away"]) if row["xg_home"] is not None and row["xg_away"] is not None else None
            forecast = {
                "p_home": p_home, "p_draw": p_draw, "p_away": p_away,
                "p_over25": row["p_over25"], "p_btts": row["p_btts"],
                "over15": row["p_over15"], "exp_total": xg_total,
                "xg_home": row["xg_home"], "xg_away": row["xg_away"],
                "pick": pick, "pick_prob": values[pick],
            }
        trained_at = ""
        if row["league"] == "UNL":
            import international
            _, trained_at = international.load_nations_league_model()
        else:
            from modeling import load_model
            _, trained_at = load_model(row["league"])
        lead_points = 0
        if forecast:
            values = [forecast["p_home"], forecast["p_draw"], forecast["p_away"]]
            top = max(values); second = sorted(values)[-2]
            lead_points = round((top - second) * 100)
            forecast = {
                **forecast, "pick": pick, "lead_points": lead_points, "trained_through": trained_at or None,
            }
        result = None
        if row["home_goals"] is not None:
            result = {
                "home_goals": row["home_goals"], "away_goals": row["away_goals"], "outcome": row["outcome"],
            }

        # ---- correct score ----
        markets = {}
        if row["markets_json"]:
            try:
                markets = json.loads(row["markets_json"])
            except (TypeError, ValueError):
                markets = {}
        correct_score = {
            "top": markets.get("top_scores", []),
            "grid": markets.get("grid", []),
            "grid_note": "7 by 7 table: row = home goals 0 to 6, column = away goals 0 to 6",
            "grid_other": markets.get("grid_other"),
        }

        # ---- corners ----
        if row["league"] in ("UNL", "CL"):
            corners = {"available": False, "reason": "No corner data for this competition"}
        else:
            corners = {"available": True}
            from modeling import corner_forecast, load_corner_model
            try:
                corner_model = load_corner_model(row["league"])
                if corner_model is not None:
                    corners.update(corner_forecast(corner_model, row["home"], row["away"]))
                else:
                    corners["available"] = False
                    corners["reason"] = "No corner model has been trained for this competition"
            except ValueError as err:
                corners["available"] = False
                corners["reason"] = f"Corner forecast unavailable: {err}"
            # season average + head-to-head, kept separate
            if corners["available"]:
                try:
                    import corner_stats
                    before = row["kickoff_utc"][:10]
                    corners["season_average"] = {
                        "home_team": corner_stats.season_corner_averages(
                            conn, row["league"], row["season"], row["home"], before),
                        "away_team": corner_stats.season_corner_averages(
                            conn, row["league"], row["season"], row["away"], before),
                    }
                    corners["h2h"] = corner_stats.h2h_corner_averages(
                        conn, row["league"], row["home"], row["away"], before)
                except Exception:
                    corners["season_average"] = None
                    corners["h2h"] = None
            # validation (club leagues only)
            corners["validation"] = _validation_for(conn, row["league"], "corners_total")

        # ---- validation per market ----
        validation = {
            market: _validation_for(conn, row["league"], market)
            for market in ("1x2", "over15", "over25", "btts", "correct_score")
        }
        if row["league"] not in ("UNL", "CL"):
            validation["corners_total"] = _validation_for(conn, row["league"], "corners_total")
        else:
            validation["corners_total"] = None

        # ---- flags ----
        flags = []
        if row["league"] == "CL" and row["matchday"] is not None and row["kickoff_utc"]:
            try:
                kickoff = datetime.strptime(row["kickoff_utc"][:10], "%Y-%m-%d")
            except ValueError:
                kickoff = None
            if kickoff is not None and (kickoff.date() - date.today()).days <= 3:
                flags.append({"side": "cl", "type": "cl_ahead", "days": (kickoff.date() - date.today()).days})

        competition = {
            "code": row["league"],
            "name": LEAGUES.get(row["league"], {}).get("name", row["league"]),
            "stage": row["stage"] or None,
            "emblem_url": LEAGUES.get(row["league"], {}).get("emblem_url"),
            "kind": LEAGUES.get(row["league"], {}).get("kind", "club"),
        }
        goals = {"exp_home": None, "exp_away": None, "exp_total": None, "over": {}, "btts": None}
        if forecast and markets.get("over"):
            goals = {
                "exp_home": forecast.get("xg_home"),
                "exp_away": forecast.get("xg_away"),
                "exp_total": forecast.get("exp_total"),
                "over": {k: v for k, v in markets.get("over", {}).items()},
                "btts": forecast.get("p_btts"),
            }

        home_name = row["home"] or row["home_fd"]
        away_name = row["away"] or row["away_fd"]
        context = _match_context(conn, row["league"], row["home"], row["away"], row["kickoff_utc"][:10])

        return {
            "id": row["fd_match_id"],
            "competition": competition,
            "kickoff_utc": row["kickoff_utc"],
            "home": {"name": home_name, "badge_url": row["home_crest"]},
            "away": {"name": away_name, "badge_url": row["away_crest"]},
            "neutral": bool(row["neutral"]),
            "forecast": forecast,
            "goals": goals,
            "correct_score": correct_score,
            "corners": corners,
            "validation": validation,
            "flags": flags,
            "result": result,
            "context": context,
            "note": None if forecast else (
                "Team name not matched yet"
                if row["home"] is None or row["away"] is None
                else "No forecast (not enough data)"
            ),
        }


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
            "spread_calibration": [],
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

    spread_rows = []
    for row in rows:
        probs = {"H": row["p_home"], "D": row["p_draw"], "A": row["p_away"]}
        spread_rows.append({
            "p_home": row["p_home"],
            "p_draw": row["p_draw"],
            "p_away": row["p_away"],
            "outcome": row["outcome"],
            "pick_hit": max(probs, key=probs.get) == row["outcome"],
        })
    spread_calibration = calibration_by_spread(spread_rows)

    return {
        "source": source,
        "available": True,
        "n": count,
        "confidence": confidence,
        "thresholds": thresholds,
        "calibration": calibration,
        "spread_calibration": spread_calibration,
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


@app.get("/api/simulation")
def get_simulation(competition: str = Query("PL", description="League code, e.g. PL, PD, SA, BL1, FL1")):
    """Step 6: Monte Carlo season simulation: title, top 4, and relegation probabilities."""
    import numpy as np
    from season_sim import simulate
    from config import season_label, seasons_to_load

    curr_season = season_label(date.today())
    with connect() as conn:
        # 1. Build current standings table from finished matches
        matches = conn.execute(
            """SELECT home, away, home_goals, away_goals FROM matches
               WHERE league = ? AND season = ?""",
            (competition, curr_season)
        ).fetchall()

        table: dict[str, dict[str, int]] = {}
        for m in matches:
            h, a, hg, ag = m["home"], m["away"], m["home_goals"], m["away_goals"]
            for team in (h, a):
                if team not in table:
                    table[team] = {"points": 0, "gd": 0, "gf": 0}
            table[h]["gf"] += hg
            table[h]["gd"] += (hg - ag)
            table[a]["gf"] += ag
            table[a]["gd"] += (ag - hg)
            if hg > ag:
                table[h]["points"] += 3
            elif hg < ag:
                table[a]["points"] += 3
            else:
                table[h]["points"] += 1
                table[a]["points"] += 1

        if not table:
            # If no matches in current season, try previous season or all known teams for this league
            prev_season = seasons_to_load()[-1]
            matches = conn.execute(
                """SELECT home, away, home_goals, away_goals FROM matches
                   WHERE league = ? AND season = ?""",
                (competition, prev_season)
            ).fetchall()
            for m in matches:
                for team in (m["home"], m["away"]):
                    if team not in table:
                        table[team] = {"points": 0, "gd": 0, "gf": 0}

        if not table:
            return {"competition": competition, "available": False, "reason": "No teams found for league"}

        # 2. Get remaining fixtures and their score grids
        upcoming = conn.execute(
            """SELECT f.home, f.away, p.markets_json
               FROM fixtures f
               LEFT JOIN predictions p ON p.fd_match_id = f.fd_match_id
               WHERE f.league = ? AND f.status IN ('SCHEDULED', 'TIMED')
                 AND f.home IS NOT NULL AND f.away IS NOT NULL""",
            (competition,)
        ).fetchall()

        model, _ = load_model(competition)
        sim_fixtures = []
        for fx in upcoming:
            h, a = fx["home"], fx["away"]
            if h not in table:
                table[h] = {"points": 0, "gd": 0, "gf": 0}
            if a not in table:
                table[a] = {"points": 0, "gd": 0, "gf": 0}

            grid = None
            if fx["markets_json"]:
                try:
                    mj = json.loads(fx["markets_json"])
                    grid = mj.get("full_grid") or mj.get("grid")
                except Exception:
                    grid = None

            if grid is None and model is not None:
                try:
                    pred = model.predict(h, a, max_goals=10)
                    grid = np.asarray(pred.grid, dtype=float).tolist()
                except Exception:
                    pass

            if grid is None:
                # Default average grid if no model available
                grid = np.full((6, 6), 1.0 / 36.0).tolist()

            sim_fixtures.append({"home": h, "away": a, "grid": grid})

        n_teams = len(table)
        results = simulate(table, sim_fixtures, n_sims=5000)

        standings = []
        for team, probs in results.items():
            probs_list = [float(p) for p in probs]
            standings.append({
                "team": team,
                "current_points": table[team]["points"],
                "current_gd": table[team]["gd"],
                "p_title": float(probs_list[0]) if len(probs_list) > 0 else 0.0,
                "p_top4": float(sum(probs_list[:4])) if len(probs_list) >= 4 else float(sum(probs_list)),
                "p_relegation": float(sum(probs_list[-3:])) if len(probs_list) >= 3 else 0.0,
                "positions": probs_list,
            })

        standings.sort(key=lambda x: (-x["p_title"], -x["p_top4"], x["p_relegation"]))

        return {
            "competition": competition,
            "competition_name": LEAGUES.get(competition, {}).get("name", competition),
            "available": True,
            "n_simulations": 5000,
            "n_teams": n_teams,
            "remaining_fixtures": len(sim_fixtures),
            "teams": standings,
        }
