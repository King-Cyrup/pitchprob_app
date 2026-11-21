"""Corner averages for the current season and previous meetings, kept separate."""


def _average(values: list[float]):
    return round(sum(values) / len(values), 2) if values else None


def season_corner_averages(conn, league: str, season: str, team: str, before_date: str) -> dict:
    rows = conn.execute(
        """SELECT CASE WHEN home = :team THEN home_corners ELSE away_corners END AS corners_for,
                  CASE WHEN home = :team THEN away_corners ELSE home_corners END AS corners_against
           FROM matches
           WHERE league = :league AND season = :season AND (home = :team OR away = :team)
             AND match_date < :before_date AND home_corners IS NOT NULL AND away_corners IS NOT NULL""",
        {"team": team, "league": league, "season": season, "before_date": before_date},
    ).fetchall()
    for_values = [row["corners_for"] for row in rows]
    against_values = [row["corners_against"] for row in rows]
    return {
        "matches": len(rows),
        "corners_for": _average(for_values),
        "corners_against": _average(against_values),
        "total_per_match": _average([a + b for a, b in zip(for_values, against_values)]),
    }


def h2h_corner_averages(conn, league: str, home: str, away: str, before_date: str, limit: int = 5) -> dict:
    rows = conn.execute(
        """SELECT match_date, home, away, home_corners, away_corners FROM matches
           WHERE league = :league AND match_date < :before_date
             AND home_corners IS NOT NULL AND away_corners IS NOT NULL
             AND ((home = :home AND away = :away) OR (home = :away AND away = :home))
           ORDER BY match_date DESC LIMIT :limit""",
        {"league": league, "home": home, "away": away, "before_date": before_date, "limit": limit},
    ).fetchall()
    home_values = [row["home_corners"] if row["home"] == home else row["away_corners"] for row in rows]
    away_values = [row["away_corners"] if row["home"] == home else row["home_corners"] for row in rows]
    return {
        "meetings": len(rows),
        "corners_for_home_team": _average(home_values),
        "corners_for_away_team": _average(away_values),
        "total_per_match": _average([a + b for a, b in zip(home_values, away_values)]),
        "list": [
            {
                "date": row["match_date"],
                "home": row["home"],
                "away": row["away"],
                "corners": f"{row['home_corners']}-{row['away_corners']}",
            }
            for row in rows
        ],
    }
