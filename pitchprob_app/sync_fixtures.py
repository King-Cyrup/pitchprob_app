"""Fetch upcoming fixtures from football-data.org and match team names to the model's names."""
import time
from datetime import datetime, timedelta, timezone
import requests
from config import FD_BASE_URL, FIXTURE_DAYS_AHEAD, FOOTBALL_DATA_TOKEN, LEAGUES, season_label
from db import connect, ensure_team_crests
from modeling import load_model
from names import load_aliases, resolve


def _fetch_with_retry(url: str, headers: dict[str, str], params: dict | None = None,
                      timeout: int = 30, retries: int = 2) -> requests.Response | None:
    """GET with a short retry loop for transient errors (429, 5xx, connection). Returns None on persistent failure."""
    for attempt in range(retries + 1):
        try:
            resp = requests.get(url, headers=headers, params=params, timeout=timeout)
        except (requests.ConnectionError, requests.Timeout) as err:
            if attempt < retries:
                time.sleep(5 * (attempt + 1))
                continue
            print(f"  Connection failed after {retries + 1} attempts: {err}")
            return None
        if resp.status_code == 429 or 500 <= resp.status_code < 600:
            if attempt < retries:
                wait = 10 * (attempt + 1)
                print(f"  HTTP {resp.status_code}, retrying in {wait}s (attempt {attempt + 1}/{retries})")
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


def sync_fixtures() -> None:
    if not FOOTBALL_DATA_TOKEN:
        raise SystemExit("FOOTBALL_DATA_TOKEN is empty. Put it in the .env file (see the guide).")
    today = datetime.now(timezone.utc).date()
    params = {"dateFrom": today.isoformat(), "dateTo": (today + timedelta(days=FIXTURE_DAYS_AHEAD)).isoformat()}
    aliases = load_aliases()
    with connect() as conn:
        ensure_team_crests(conn)
        for code, league in LEAGUES.items():
            resp = _fetch_with_retry(
                f"{FD_BASE_URL}/competitions/{league['fd_code']}/matches",
                headers={"X-Auth-Token": FOOTBALL_DATA_TOKEN}, params=params, timeout=30,
            )
            if resp is None:
                print(f"  {code}: request failed, skipping (network error)")
                continue
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
                kept += 1
            print(f"  {code}: {kept} upcoming fixtures stored")
            time.sleep(7)  # the free plan allows 10 requests per minute


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
