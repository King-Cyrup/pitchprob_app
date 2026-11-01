"""Compare what the model forecast with what actually happened."""
from db import connect

LABEL = {"H": "Home win", "D": "Draw", "A": "Away win"}


def fetch_results(conn, league: str | None = None) -> list[dict]:
    """Every graded match, newest first, with the forecast, the result and whether the forecast 'hit'."""
    sql = """SELECT f.league, f.kickoff_utc, f.home, f.away,
                    p.p_home, p.p_draw, p.p_away, p.p_over25, p.p_btts,
                    g.home_goals, g.away_goals, g.outcome, g.logloss_1x2, g.base_logloss_1x2
             FROM grades g
             JOIN fixtures f ON f.fd_match_id = g.fd_match_id
             JOIN predictions p ON p.fd_match_id = g.fd_match_id"""
    params: list = []
    if league:
        sql += " WHERE f.league = ?"
        params.append(league)
    sql += " ORDER BY f.kickoff_utc DESC"
    rows = []
    for r in conn.execute(sql, params):
        d = dict(r)
        probs = {"H": d["p_home"], "D": d["p_draw"], "A": d["p_away"]}
        d["pick"] = max(probs, key=probs.get)          # the outcome the model rated most likely
        d["pick_prob"] = probs[d["pick"]]
        d["pick_hit"] = d["pick"] == d["outcome"]
        d["over_actual"] = d["home_goals"] + d["away_goals"] > 2
        d["over_hit"] = (d["p_over25"] >= 0.5) == d["over_actual"]    # model said 'over' when p >= 50%
        d["btts_actual"] = d["home_goals"] > 0 and d["away_goals"] > 0
        d["btts_hit"] = (d["p_btts"] >= 0.5) == d["btts_actual"]
        rows.append(d)
    return rows


def summarize(rows: list[dict]) -> dict:
    n = len(rows)
    if n == 0:
        return {"n": 0}
    return {
        "n": n,
        "pick_hits": sum(r["pick_hit"] for r in rows),
        "pick_rate": sum(r["pick_hit"] for r in rows) / n,
        "avg_confidence": sum(r["pick_prob"] for r in rows) / n,
        "over_rate": sum(r["over_hit"] for r in rows) / n,
        "btts_rate": sum(r["btts_hit"] for r in rows) / n,
        "avg_logloss": sum(r["logloss_1x2"] for r in rows) / n,
        "avg_base_logloss": sum(r["base_logloss_1x2"] for r in rows) / n,
    }


def calibration(rows: list[dict], width: float = 0.1) -> list[dict]:
    """Group every forecast percentage (Home, Draw and Away of every match) into bands, then compare
    the band's average forecast with how often that outcome really happened."""
    bands: dict[int, list] = {}
    last = int(round(1 / width)) - 1
    for r in rows:
        for key, p in (("H", r["p_home"]), ("D", r["p_draw"]), ("A", r["p_away"])):
            b = min(int(p / width + 1e-9), last)  # the tiny extra stops 0.3 / 0.1 = 2.9999... landing in the wrong band
            slot = bands.setdefault(b, [0, 0.0, 0])  # count, sum of forecasts, times it happened
            slot[0] += 1
            slot[1] += p
            slot[2] += 1 if r["outcome"] == key else 0
    return [
        {"range": f"{round(b * width * 100)}-{round((b + 1) * width * 100)}%", "n": c,
         "avg_forecast": s / c, "actual": hit / c}
        for b, (c, s, hit) in sorted(bands.items())
    ]


def print_report(league: str | None = None, last: int = 20) -> None:
    with connect() as conn:
        rows = fetch_results(conn, league)
    if not rows:
        print("No graded matches yet. After matches finish, run:  python cli.py load-history  then  python cli.py grade")
        return
    s = summarize(rows)
    scope = league or "all leagues"
    print(f"RESULTS CHECK ({scope}): {s['n']} graded matches\n")
    print(f"  Most-likely outcome was right:  {s['pick_hits']} of {s['n']}  ({s['pick_rate']:.0%})")
    print(f"  Average confidence of those picks: {s['avg_confidence']:.0%}   (compare with the line above)")
    print(f"  Over/under 2.5 call right:      {s['over_rate']:.0%}")
    print(f"  Both-teams-to-score call right: {s['btts_rate']:.0%}")
    print(f"  Average log loss: model {s['avg_logloss']:.3f}  vs  no-model baseline {s['avg_base_logloss']:.3f}  (lower is better)\n")
    print(f"  Last {min(last, len(rows))} matches:")
    print(f"  {'date':10} {'match':34} {'H%':>3} {'D%':>3} {'A%':>3}  {'pick':9} {'result':6} right?")
    for r in rows[:last]:
        match = f"{r['home']} v {r['away']}"[:34]
        print(f"  {r['kickoff_utc'][:10]:10} {match:34} {r['p_home']*100:3.0f} {r['p_draw']*100:3.0f} {r['p_away']*100:3.0f}"
              f"  {LABEL[r['pick']]:9} {r['home_goals']}-{r['away_goals']:<4} {'yes' if r['pick_hit'] else 'no'}")
    print("\n  Calibration: when the model said X%, how often did it happen?")
    print(f"  {'band':8} {'forecasts':>9} {'average forecast':>17} {'happened':>9}")
    for b in calibration(rows):
        print(f"  {b['range']:8} {b['n']:9d} {b['avg_forecast']:17.0%} {b['actual']:9.0%}")
    if s["n"] < 100:
        print(f"\n  NOTE: only {s['n']} graded matches. Fewer than 100 is too few to judge the model: "
              "differences are mostly luck.")