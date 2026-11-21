"""Download finished matches from football-data.co.uk (through the penaltyblog library)."""
import time
import pandas as pd
import penaltyblog as pb
from config import LEAGUES, seasons_to_load
from db import connect


def _fetch_with_retry(code: str, season: str, pb_name: str, *, retries: int = 3) -> pd.DataFrame:
    """Download a season's fixtures with exponential backoff on transient failures."""
    last_err: Exception | None = None
    for attempt in range(retries + 1):
        try:
            return pb.scrapers.FootballData(pb_name, season).get_fixtures()
        except Exception as err:
            last_err = err
            if attempt < retries:
                wait = 5 * (2 ** attempt)  # 5s, 10s, 20s
                print(f"  {code} {season}: {type(err).__name__}, retrying in {wait}s "
                      f"(attempt {attempt + 1}/{retries})")
                time.sleep(wait)
    raise last_err  # type: ignore[misc]


def load_history(seasons: list[str] | None = None, *, strict: bool = False) -> None:
    seasons = seasons or seasons_to_load()
    with connect() as conn:
        for code, league in LEAGUES.items():
            if league["pb_name"] is None:
                continue
            for season in seasons:
                try:
                    df = _fetch_with_retry(code, season, league["pb_name"])
                except Exception as err:  # a season file may not exist yet
                    print(f"  {code} {season}: could not download ({type(err).__name__}: {err})")
                    if strict:
                        raise RuntimeError(f"Could not refresh {code} results for {season}") from err
                    continue
                df = df.dropna(subset=["goals_home", "goals_away"])  # keep finished matches only
                home_corners = pd.to_numeric(df["hc"], errors="coerce") if "hc" in df else pd.Series(index=df.index, dtype=float)
                away_corners = pd.to_numeric(df["ac"], errors="coerce") if "ac" in df else pd.Series(index=df.index, dtype=float)
                rows = []
                corner_rows = 0
                for position, (_, row) in enumerate(df.iterrows()):
                    hc = None if pd.isna(home_corners.iloc[position]) else int(home_corners.iloc[position])
                    ac = None if pd.isna(away_corners.iloc[position]) else int(away_corners.iloc[position])
                    corner_rows += int(hc is not None and ac is not None)
                    rows.append((
                        code, season, pd.Timestamp(row["date"]).strftime("%Y-%m-%d"),
                        row["team_home"], row["team_away"], int(row["goals_home"]),
                        int(row["goals_away"]), hc, ac,
                    ))
                conn.executemany(
                    """INSERT INTO matches (league, season, match_date, home, away, home_goals, away_goals,
                                            home_corners, away_corners)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                       ON CONFLICT (league, season, home, away) DO UPDATE SET
                         match_date = excluded.match_date,
                         home_goals = excluded.home_goals, away_goals = excluded.away_goals,
                         home_corners = excluded.home_corners, away_corners = excluded.away_corners""",
                    rows,
                )
                print(f"  {code} {season}: {len(rows)} finished matches stored, {corner_rows} with corners")
                time.sleep(1)  # pace DNS lookups between requests
