"""Fetch upcoming fixtures from football-data.org and match team names to the model's names."""
import io
import time
from datetime import datetime, timedelta, timezone
import requests
import pandas as pd
from config import DATA_DIR, FD_BASE_URL, FIXTURE_DAYS_AHEAD, FOOTBALL_DATA_TOKEN, LEAGUES, season_label
from db import connect, ensure_team_crests
from modeling import load_model
from names import load_aliases, resolve
from manual_fixtures import read_manual_fixtures


def _fetch_with_retry(url: str, headers: dict[str, str], params: dict | None = None,
                      timeout: int = 30, retries: int = 3) -> requests.Response | None:
    """GET with exponential backoff for transient errors (429, 5xx, connection, DNS).
    Bounded by retries to guarantee no infinite loops. Returns None on persistent failure."""
    for attempt in range(retries + 1):
        if attempt > 0:
            time.sleep(2)  # brief pause before retrying
        try:
            resp = requests.get(url, headers=headers, params=params, timeout=timeout)
        except requests.RequestException as err:
            if attempt < retries:
                wait = 10 * (2 ** attempt)  # 10s, 20s, 40s
                print(f"  {type(err).__name__}, retrying in {wait}s (attempt {attempt + 1}/{retries})")
                time.sleep(wait)
                continue
            print(f"  Connection failed after {retries + 1} attempts: {err}")
            return None
        if resp.status_code == 429 or 500 <= resp.status_code < 600:
            if attempt < retries:
                # Respect server rate limit reset header if present
                resp_headers = getattr(resp, "headers", {}) or {}
                reset_sec = resp_headers.get("X-RequestCounter-Reset") or resp_headers.get("Retry-After")
                try:
                    wait = int(reset_sec) if reset_sec else 10 * (2 ** attempt)
                    wait = max(wait, 5)
                    wait = min(wait, 65)
                except (ValueError, TypeError):
                    wait = 10 * (2 ** attempt)
                print(f"  HTTP {resp.status_code}, rate-limited, waiting {wait}s (attempt {attempt + 1}/{retries})")
                time.sleep(wait)
                continue
        return resp
    return None


def _model_names(conn, league: str) -> set[str]:
    rows = conn.execute(
        "SELECT home AS n FROM matches WHERE league = ? UNION SELECT away FROM matches WHERE league = ?",
        (league, league),
    ).fetchall()
    names = {r["n"] for r in rows}
    model, _ = load_model(league)
    if model is not None:
        names.update(model.teams)
    return names


def _international_model_names(conn) -> set[str]:
    rows = conn.execute(
        """SELECT home_team AS name FROM intl_matches
           WHERE tournament = 'UEFA Nations League'
           UNION SELECT away_team FROM intl_matches
           WHERE tournament = 'UEFA Nations League'"""
    ).fetchall()
    return {row["name"] for row in rows}


def sync_nations_league_fixtures(conn, now: datetime | None = None) -> int:
    """Load verified manual fixtures, preserving existing fixtures if the file is absent."""
    path = DATA_DIR / "nations_league_fixtures.csv"
    if not path.exists():
        latest = conn.execute(
            "SELECT MAX(updated_at) FROM fixtures WHERE league = 'UNL'"
        ).fetchone()[0]
        if latest:
            print(f"  UNL: fixture source unavailable; keeping existing fixtures (last updated {latest})")
        else:
            print(f"  UNL: no fixture file at {path}; no fixtures changed")
        return 0

    teams = _international_model_names(conn)
    if not teams:
        raise RuntimeError("Cannot validate Nations League fixtures: load international results first.")
    fixtures = read_manual_fixtures(path, teams, load_aliases())
    now = now or datetime.now(timezone.utc)
    season = season_label(now.date())
    inserted = 0
    for fixture in fixtures:
        kickoff = fixture["kickoff_utc"]
        match_id = _stable_fixture_id(kickoff, fixture["home"], fixture["away"])
        conn.execute(
            """INSERT INTO fixtures (fd_match_id, league, season, kickoff_utc, status,
                                     home_fd, away_fd, home, away, updated_at)
               VALUES (?, 'UNL', ?, ?, 'TIMED', ?, ?, ?, ?, ?)
               ON CONFLICT (fd_match_id) DO UPDATE SET
                 kickoff_utc = excluded.kickoff_utc, status = excluded.status,
                 home_fd = excluded.home_fd, away_fd = excluded.away_fd,
                 home = excluded.home, away = excluded.away, updated_at = excluded.updated_at""",
            (
                match_id, season_label(datetime.fromisoformat(kickoff.replace("Z", "+00:00")).date()),
                kickoff, fixture["home"], fixture["away"], fixture["home"], fixture["away"],
                now.isoformat(),
            ),
        )
        conn.execute(
            """INSERT INTO fixture_metadata (fd_match_id, stage, neutral) VALUES (?, ?, ?)
               ON CONFLICT (fd_match_id) DO UPDATE SET stage = excluded.stage, neutral = excluded.neutral""",
            (match_id, fixture["group"], int(fixture["neutral"])),
        )
        inserted += 1
    print(f"  UNL: {inserted} fixtures loaded from data/nations_league_fixtures.csv")
    return inserted


def _stable_fixture_id(kickoff: str, home: str, away: str) -> int:
    import hashlib

    digest = hashlib.sha256(f"UNL|{kickoff}|{home}|{away}".encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big") & 0x7FFFFFFFFFFFFFFF


def _sync_team_crests(conn, code: str, fd_code: str, headers: dict[str, str]) -> bool:
    # Avoid redundant requests: check if crests are already cached for this league
    existing = conn.execute("SELECT COUNT(*) FROM team_crests WHERE league = ?", (code,)).fetchone()[0]
    if existing >= 10:
        return False  # Already cached, skip to stay within rate limits

    resp = _fetch_with_retry(
        f"{FD_BASE_URL}/competitions/{fd_code}/teams", headers=headers, timeout=30,
    )
    if resp is None:
        print(f"  {code}: team crest refresh failed (network error)")
        return False
    if resp.status_code != 200:
        print(f"  {code}: team crest refresh failed with HTTP {resp.status_code}: {resp.text[:200]}")
        return resp.status_code == 429

    now = datetime.now(timezone.utc).isoformat()
    updated = 0
    for team in resp.json().get("teams", []):
        crest_url = team.get("crest")
        team_name = team.get("name")
        if not team_name or not crest_url:
            continue
        conn.execute(
            """INSERT INTO team_crests (league, team_fd, crest_url, updated_at)
               VALUES (?, ?, ?, ?)
               ON CONFLICT (league, team_fd) DO UPDATE SET
                 crest_url = excluded.crest_url, updated_at = excluded.updated_at""",
            (code, team_name, crest_url, now),
        )
        updated += 1
    print(f"  {code}: {updated} team crests refreshed")
    return False


def sync_fixtures(*, strict: bool = False) -> None:
    if not FOOTBALL_DATA_TOKEN:
        raise SystemExit("FOOTBALL_DATA_TOKEN is empty. Put it in the .env file (see the guide).")
    today = datetime.now(timezone.utc).date()
    params = {"dateFrom": today.isoformat(), "dateTo": (today + timedelta(days=FIXTURE_DAYS_AHEAD)).isoformat()}
    aliases = load_aliases()
    successful_competitions = 0
    with connect() as conn:
        ensure_team_crests(conn)
        for code, league in LEAGUES.items():
            if league.get("kind") == "national":
                continue
            headers = {"X-Auth-Token": FOOTBALL_DATA_TOKEN}
            if _sync_team_crests(conn, code, league["fd_code"], headers):
                print("  Too many requests. Wait a minute and run again.")
                break
            time.sleep(7)  # Keep within football-data.org's free-plan request limit.
            resp = _fetch_with_retry(
                f"{FD_BASE_URL}/competitions/{league['fd_code']}/matches",
                headers=headers, params=params, timeout=30,
            )
            if resp is None:
                print(f"  {code}: request failed, skipping (network error)")
                if strict:
                    raise RuntimeError(f"Could not fetch {code} fixtures")
                continue
            if resp.status_code != 200:
                print(f"  {code}: HTTP {resp.status_code}: {resp.text[:200]}")
                if strict and (resp.status_code == 401 or resp.status_code == 429 or resp.status_code >= 500):
                    raise RuntimeError(f"Could not fetch {code} fixtures: HTTP {resp.status_code}")
                if resp.status_code == 429:
                    print("  Too many requests. Wait a minute and run again.")
                    break
                continue
            successful_competitions += 1
            names = _model_names(conn, code)
            kept = 0
            for m in resp.json().get("matches", []):
                if m["status"] not in ("SCHEDULED", "TIMED"):
                    continue
                kickoff = m["utcDate"]  # e.g. 2026-11-01T16:30:00Z
                home = resolve(m["homeTeam"]["name"], m["homeTeam"].get("shortName"), names, aliases)
                away = resolve(m["awayTeam"]["name"], m["awayTeam"].get("shortName"), names, aliases)
                now = datetime.now(timezone.utc).isoformat()
                for team in (m["homeTeam"], m["awayTeam"]):
                    crest_url = team.get("crest")
                    if crest_url:
                        conn.execute(
                            """INSERT INTO team_crests (league, team_fd, crest_url, updated_at)
                               VALUES (?, ?, ?, ?)
                               ON CONFLICT (league, team_fd) DO UPDATE SET
                                 crest_url = excluded.crest_url, updated_at = excluded.updated_at""",
                            (code, team["name"], crest_url, now),
                        )
                conn.execute(
                    """INSERT INTO fixtures (fd_match_id, league, season, kickoff_utc, status,
                                             home_fd, away_fd, home, away, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                       ON CONFLICT (fd_match_id) DO UPDATE SET
                         kickoff_utc = excluded.kickoff_utc, status = excluded.status,
                         home = excluded.home, away = excluded.away, updated_at = excluded.updated_at""",
                    (m["id"], code, season_label(datetime.fromisoformat(kickoff.replace("Z", "+00:00")).date()),
                     kickoff, m["status"], m["homeTeam"]["name"], m["awayTeam"]["name"], home, away,
                    now),
                )
                conn.execute(
                    """INSERT INTO fixture_metadata (fd_match_id, stage, neutral) VALUES (?, ?, 0)
                       ON CONFLICT (fd_match_id) DO UPDATE SET stage = excluded.stage""",
                    (m["id"], m.get("stage") or (f"Matchday {m['matchday']}" if m.get("matchday") else None)),
                )
                kept += 1
            print(f"  {code}: {kept} upcoming fixtures stored")
            time.sleep(7)  # the free plan allows 10 requests per minute
        if "UNL" in LEAGUES:
            sync_nations_league_fixtures(conn)
    if strict and successful_competitions == 0:
        raise RuntimeError("No football-data.org competitions could be refreshed")


def load_international_results(url: str = "https://raw.githubusercontent.com/martj42/international_results/master/results.csv") -> None:
    """Load national-team results into the dedicated intl_matches table.

    The file is a source of truth for recent international matches and must be kept
    separate from club history in the SQLite database.
    """
    try:
        resp = requests.get(url, timeout=30)
    except requests.RequestException as err:
        raise RuntimeError(f"Could not download international results: {err}") from err
    if resp.status_code != 200:
        raise RuntimeError(f"Could not download international results: HTTP {resp.status_code}")
    from international import clean_results

    raw = pd.read_csv(io.StringIO(resp.text))
    expected_columns = {"date", "home_team", "away_team", "home_score", "away_score", "tournament", "neutral"}
    if not expected_columns.issubset(raw.columns):
        raise RuntimeError("International results CSV has an unexpected schema.")
    results = clean_results(raw)
    rows = [
        (
            row.date.strftime("%Y-%m-%d"), row.home_team, row.away_team,
            int(row.home_score), int(row.away_score), row.tournament, int(row.neutral),
        )
        for row in results.itertuples(index=False)
    ]
    if not rows:
        raise RuntimeError("International results CSV was empty")
    with connect() as conn:
        previous_count = conn.execute("SELECT COUNT(*) FROM intl_matches").fetchone()[0]
        if len(rows) < previous_count:
            raise RuntimeError(
                f"International results source has {len(rows)} completed rows; "
                f"the database already has {previous_count}. Refusing a smaller refresh."
            )
        conn.executemany(
            """INSERT INTO intl_matches (date, home_team, away_team, home_score, away_score, tournament, neutral)
               VALUES (?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT (date, home_team, away_team) DO UPDATE SET
                 home_score = excluded.home_score,
                 away_score = excluded.away_score,
                 tournament = excluded.tournament,
                 neutral = excluded.neutral""",
            rows,
        )
        print(f"  intl_matches: {len(rows)} completed rows loaded; latest {rows[-1][0]}")


def check_access() -> None:
    """Ask football-data.org which competitions your token may read, and compare with LEAGUES."""
    if not FOOTBALL_DATA_TOKEN:
        raise SystemExit("FOOTBALL_DATA_TOKEN is empty. Put it in the .env file (see the guide).")
    resp = _fetch_with_retry(f"{FD_BASE_URL}/competitions", headers={"X-Auth-Token": FOOTBALL_DATA_TOKEN}, timeout=30)
    if resp is None:
        raise SystemExit("Could not reach football-data.org — check your internet connection and retry.")
    print("HTTP status:", resp.status_code)
    if resp.status_code != 200:
        raise SystemExit(f"Unexpected answer: {resp.text[:300]}")
    available = {c["code"]: c["name"] for c in resp.json().get("competitions", [])}
    print(f"Your token can read {len(available)} competitions: {', '.join(sorted(available))}")
    for code, league in LEAGUES.items():
        mark = "OK     " if league["fd_code"] in available else "MISSING"
        print(f"  {mark} {code} ({league['name']})")
