"""Match team names between football-data.org (fixtures) and football-data.co.uk (history)."""
import csv
import difflib
import re
import unicodedata
from config import ALIASES_PATH

# Words that clubs add or drop in different sources. Removed before comparing names.
NOISE = {"fc", "afc", "cf", "sc", "ac", "as", "us", "ud", "rcd", "ssc", "ss", "sv", "vfl", "vfb", "fsv", "tsg", "calcio"}

# with open(ALIASES_PATH, newline="", encoding="utf-8-sig") as f:

def normalize(name: str) -> str:
    text = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii").lower()
    tokens = [t for t in re.split(r"[^a-z0-9]+", text) if t and t not in NOISE]
    return " ".join(tokens)


def load_aliases() -> dict[str, str]:
    """team_aliases.csv has two columns: fd_name,model_name"""
    aliases: dict[str, str] = {}
    if ALIASES_PATH.exists():
        with open(ALIASES_PATH, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                if row.get("fd_name") and row.get("model_name"):
                    aliases[row["fd_name"].strip()] = row["model_name"].strip()
    return aliases


def resolve(fd_name: str, fd_short: str | None, model_names: set[str], aliases: dict[str, str]) -> str | None:
    """Return the model's name for a football-data.org team, or None if we cannot be sure."""
    if fd_name in aliases and aliases[fd_name] in model_names:
        return aliases[fd_name]
    by_norm = {normalize(n): n for n in model_names}
    for candidate in (fd_name, fd_short or ""):
        key = normalize(candidate)
        if key and key in by_norm:
            return by_norm[key]
    # model name's words are all inside the longer fd name, e.g. 'Newcastle' in 'Newcastle United FC'
    fd_tokens = set(normalize(fd_name).split())
    hits = [n for n in model_names if normalize(n) and set(normalize(n).split()) <= fd_tokens]
    return hits[0] if len(hits) == 1 else None


def suggest(fd_name: str, model_names: set[str]) -> list[str]:
    by_norm = {normalize(n): n for n in model_names}
    close = difflib.get_close_matches(normalize(fd_name), list(by_norm), n=3, cutoff=0.4)
    return [by_norm[c] for c in close]
