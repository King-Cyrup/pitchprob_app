import glob
import math
import os
import sys
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import decide, elo, live_update, market_check, recalibrate, season_sim  # noqa: E402

CLUB_DIR = ROOT / "tests" / "data" / "club"      # real files from the GitHub mirror (see the guide); tests skip if absent


def toy_matches(n=400, seed=1):
    rng = np.random.default_rng(seed)
    teams = [f"T{i}" for i in range(12)]; strength = rng.normal(0, 0.35, 12); rows = []
    for k in range(n):
        i, j = rng.choice(12, 2, replace=False)
        rows.append(dict(league="L", home=teams[i], away=teams[j], hg=rng.poisson(math.exp(0.3 + strength[i] - strength[j] * 0.5)),
                         ag=rng.poisson(math.exp(0.0 + strength[j] - strength[i] * 0.5))))
    return pd.DataFrame(rows)


def test_elo_update_is_zero_sum_and_rewards_the_winner():
    e = elo.EloRatings()
    e.update("L", "A", "B", 3, 0)
    assert e.r[("L", "A")] > 1500 > e.r[("L", "B")]
    assert e.r[("L", "A")] + e.r[("L", "B")] == pytest.approx(3000)
    assert e.diff("L", "A", "B") > e.diff("L", "B", "A")           # the stronger team is favoured at home and away


def test_pre_match_elo_never_sees_the_future():
    m = toy_matches()
    base = elo.pre_match_diffs(m)
    tampered = m.copy(); tampered.loc[200:, ["hg", "ag"]] = 9      # rewrite match 200 and everything after it
    again = elo.pre_match_diffs(tampered)
    pd.testing.assert_series_equal(base.iloc[:201], again.iloc[:201])   # match 200's own rating difference is unchanged


def test_mapper_and_blend_give_valid_probabilities():
    m = toy_matches(); d = elo.pre_match_diffs(m).to_numpy()
    res = np.where(m.hg > m.ag, 0, np.where(m.hg < m.ag, 2, 1)).astype(int)
    mapper = elo.EloMapper().fit(d, res)
    p = mapper.predict(np.array([-300.0, 0.0, 300.0]))
    assert p.sum(axis=1) == pytest.approx(1.0) and p[0, 2] > p[1, 2] > p[2, 2] and p[2, 0] > p[1, 0] > p[0, 0]
    b = elo.blend(np.array([[0.5, 0.3, 0.2]]), np.array([[0.3, 0.3, 0.4]]), 0.5)
    assert b[0] == pytest.approx([0.4, 0.3, 0.3])


def test_platt_fixes_over_confident_probabilities():
    rng = np.random.default_rng(2)
    true = rng.uniform(0.3, 0.7, 6000); y = rng.random(6000) < true
    raw = np.clip(0.5 + (true - 0.5) * 2.0, 0.02, 0.98)             # a model that is twice as confident as reality
    cal = recalibrate.PlattCalibrator().fit(raw[:3000], y[:3000]).transform(raw[3000:])
    ll = lambda p, t: float(-np.log(np.where(t, p, 1 - p)).mean())
    assert ll(cal, y[3000:]) < ll(raw[3000:], y[3000:]) - 0.01
    order = np.argsort(raw[3000:]); assert np.all(np.diff(cal[order]) >= -1e-12)     # still ordered like the raw numbers


def test_devig_and_market_comparison():
    p = market_check.devig(np.array([2.0, 3.5, 4.0]))
    assert p.sum() == pytest.approx(1.0) and p[0] > p[1] > p[2]
    model = np.array([[0.6, 0.2, 0.2], [0.2, 0.3, 0.5]]); market = np.array([[0.5, 0.3, 0.2], [0.3, 0.3, 0.4]])
    out = market_check.compare_with_market(model, market, np.array([0, 2]))
    assert list(out.index) == ["Model", "Bookmaker closing odds", "50/50 mix"] and out.loc["Model", "log_loss"] == pytest.approx(-(math.log(.6) + math.log(.5)) / 2)


def test_decision_rule():
    rng = np.random.default_rng(3)
    old = rng.normal(1.0, 0.5, 4000); better = old - rng.normal(0.005, 0.05, 4000)
    r = decide.paired_gain(old, better)
    assert r["n"] == 4000 and decide.decide(r) == "adopt" and r["low"] > 0
    same = decide.paired_gain(old, old + rng.normal(0, 0.05, 4000))
    assert decide.decide(same) in ("reject", "shadow") and decide.decide(same) != "adopt"
    small = decide.paired_gain(old[:300], better[:300])
    assert decide.decide(small) != "adopt"                           # too few matches to adopt, whatever the gain
    assert decide.decide({"n": 5000, "gain": -0.01, "low": -0.02, "high": 0.0}) == "reject"


def test_season_simulation_is_a_proper_distribution():
    one_nil = np.zeros((4, 4)); one_nil[1, 0] = 1.0
    t = {"A": {"points": 10, "gd": 2, "gf": 5}, "B": {"points": 10, "gd": 0, "gf": 4}}
    out = season_sim.simulate(t, [{"home": "B", "away": "A", "grid": one_nil}], n_sims=200)
    assert out["B"] == pytest.approx([1.0, 0.0]) and out["A"] == pytest.approx([0.0, 1.0])      # B wins 1-0 and overtakes A
    g = np.outer([.4, .3, .2, .1], [.5, .3, .1, .1])
    teams = {c: {"points": 20 + i, "gd": i, "gf": 20 + i} for i, c in enumerate("ABCD")}
    fx = [{"home": a, "away": b, "grid": g} for a in "ABCD" for b in "ABCD" if a != b]
    res = season_sim.simulate(teams, fx, n_sims=3000)
    M = np.vstack([res[c] for c in "ABCD"])
    assert M.sum(axis=1) == pytest.approx(1.0) and M.sum(axis=0) == pytest.approx(1.0)


def test_in_play_update_limits():
    lam, mu = 1.6, 1.1
    pre = live_update.inplay_1x2(lam, mu, 0, 0, 0)
    assert pre["p_home"] == pytest.approx(0.490, abs=2e-3) and pre["p_draw"] == pytest.approx(0.249, abs=2e-3)   # the guide's worked example
    assert live_update.inplay_1x2(lam, mu, 90, 1, 0)["p_home"] == pytest.approx(1.0)
    assert live_update.inplay_1x2(lam, mu, 90, 1, 1)["p_draw"] == pytest.approx(1.0)
    a, b = live_update.inplay_1x2(lam, mu, 30, 1, 0)["p_home"], live_update.inplay_1x2(lam, mu, 70, 1, 0)["p_home"]
    assert 0.49 < a < b < 1.0                                       # leading team's chance grows as time runs out


@pytest.mark.skipif(not glob.glob(str(CLUB_DIR / "*.csv")), reason="needs the downloaded club files")
def test_real_data_elo_beats_no_model_out_of_sample():
    frames = []
    for path in sorted(glob.glob(str(CLUB_DIR / "*.csv"))):
        name = os.path.basename(path)[:-4]; lg, season = name.rsplit("-", 1)
        d = pd.read_csv(path); d["league"] = lg; d["season"] = season; frames.append(d)
    df = pd.concat(frames).dropna(subset=["FTHG", "FTAG"])
    df["date"] = pd.to_datetime(df["Date"]); df = df.sort_values(["date", "league"], kind="stable").reset_index(drop=True)
    df = df.rename(columns={"HomeTeam": "home", "AwayTeam": "away", "FTHG": "hg", "FTAG": "ag"})
    df["hg"], df["ag"] = df.hg.astype(int), df.ag.astype(int)
    d = elo.pre_match_diffs(df).to_numpy(); res = np.where(df.hg > df.ag, 0, np.where(df.hg < df.ag, 2, 1)).astype(int)
    train = (df.date < "2023-08-01").to_numpy(); test = ~train & (df.date >= "2024-08-01").to_numpy()
    p = elo.EloMapper().fit(d[train], res[train]).predict(d[test])
    ll = market_check.log_loss_1x2(p, res[test])
    base = np.tile([(res[train] == k).mean() for k in range(3)], (test.sum(), 1))
    assert test.sum() > 3000 and ll < market_check.log_loss_1x2(base, res[test]) - 0.05 and ll < 1.02
