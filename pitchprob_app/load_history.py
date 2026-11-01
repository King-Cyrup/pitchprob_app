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
