"""Validated reader for Nations League fixtures when the API provider has no competition."""

import csv
from datetime import datetime, timezone

REQUIRED = ("date_utc", "time_utc", "home", "away")


def read_manual_fixtures(path, known_teams: set[str], aliases: dict[str, str] | None = None) -> list[dict]:
    aliases = aliases or {}
    fixtures, problems = [], []
    with open(path, newline="", encoding="utf-8-sig") as file:
        reader = csv.DictReader(file)
        missing = [column for column in REQUIRED if column not in (reader.fieldnames or [])]
        if missing:
            raise ValueError(f"Missing columns: {', '.join(missing)}")
        for line, row in enumerate(reader, start=2):
            source_home = (row.get("home") or "").strip()
            source_away = (row.get("away") or "").strip()
            home = aliases.get(source_home, source_home)
            away = aliases.get(source_away, source_away)
            for team in (home, away):
                if team not in known_teams:
                    problems.append(f"line {line}: unknown team '{team}'")
            try:
                kickoff = datetime.strptime(
                    f"{(row.get('date_utc') or '').strip()} {(row.get('time_utc') or '').strip()}",
                    "%Y-%m-%d %H:%M",
                ).replace(tzinfo=timezone.utc)
            except ValueError:
                problems.append(f"line {line}: bad date or time '{row.get('date_utc')} {row.get('time_utc')}'")
                continue
            fixtures.append({
                "kickoff_utc": kickoff.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "home": home,
                "away": away,
                "group": (row.get("group") or "").strip() or None,
                "neutral": (row.get("neutral") or "").strip().upper() in {"TRUE", "1", "YES"},
            })
    if problems:
        raise ValueError("Fixture file problems:\n  " + "\n  ".join(problems))
    return fixtures
