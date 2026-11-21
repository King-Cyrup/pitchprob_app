"""Downloads the public club-match files used by the real-data tests into tests/data/club/ (about 2 MB)."""
import sys
import urllib.request
from pathlib import Path

BASE = "https://raw.githubusercontent.com/datasets/football-datasets/main/datasets"
LEAGUES = ["premier-league", "la-liga", "serie-a", "bundesliga", "ligue-1"]
SEASONS = ["1920", "2021", "2122", "2223", "2324", "2425", "2526"]      # 2019-20 to 2025-26


def main(target: str = "tests/data/club") -> None:
    out = Path(target)
    out.mkdir(parents=True, exist_ok=True)
    for league in LEAGUES:
        for season in SEASONS:
            name = f"{league}-{season}.csv"
            try:
                data = urllib.request.urlopen(f"{BASE}/{league}/season-{season}.csv", timeout=60).read()
            except Exception as err:
                print(f"skipped {name}: {err}")
                continue
            (out / name).write_bytes(data)
    print(f"{len(list(out.glob('*.csv')))} files in {out}")


if __name__ == "__main__":
    main(*sys.argv[1:])
