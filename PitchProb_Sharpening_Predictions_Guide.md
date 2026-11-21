# PitchProb: Step-by-Step Guide to Sharper Predictions

**Written:** 14 November 2026. **For:** you (the owner) and the AI coding agent that does the work. Every step says what to build, why this way, how to know it worked, how to undo it, and what **you** must do by hand.

**The most important result first:** I tested these ideas on real match data before recommending any of them. Football is noisy, so the gains are small. The biggest practical win is not accuracy at all: it is **not showing a number that is no better than a constant guess**. For example, the Both Teams To Score probability from the goals model alone was *worse* than a constant guess in my test, until it was recalibrated (Step 3).

---

## 1. What I tested, and the verdict for each idea

**How I tested:** walk-forward on real match files, meaning the model always predicts a month of matches using only matches played before that month. Club data: 12,459 matches from the Premier League, La Liga, Serie A, Bundesliga and Ligue 1 (2019-20 to 2025-26), from a public GitHub mirror of football-data.co.uk files. Test matches: 5,186 (2023-24 to 2025-26) for model comparisons and 3,458 (2024-25 and 2025-26) for stacking and calibration. National teams: the 288 UEFA Nations League matches used in the previous brief. Lower log loss is better. A gain counts only if its 95% interval (bootstrap) stays above zero.

| Idea you listed | Verdict | Evidence (real data) | Action |
|---|---|---|---|
| Market check against bookmaker closing odds | **Do first** (it changes nothing, it only measures) | Not testable here: the mirror has no odds columns. Your football-data.co.uk downloads may have them (Step 1 checks) | Step 1 |
| Blend the goals model with **Elo ratings** | **Do (clubs only)** | +0.005 log loss, 95% interval +0.0013 to +0.0094. For national teams: **no gain** (-0.006, interval -0.019 to +0.007) | Step 2 |
| **Recalibrate** Over/Under and Both Teams To Score | **Do** | +0.0042 (Over 1.5), +0.0047 (Over 2.5), +0.0065 (BTTS), all intervals above zero. Raw BTTS was worse than a constant guess | Step 3 |
| Recency (last two years) | **Keep your setting** | 1095 days with decay 0.0019 loses only 0.0007 log loss against the best setting tested. A strict 730-day window loses 0.004 | Step 4 |
| Better **corner** model | **Do (negative binomial)** | Per-team corner lines beat a constant (home over 4.5: 0.653 vs 0.684). **Total corners are almost a coin flip** (over 9.5: 0.686 vs 0.688) | Step 5 |
| **Season simulations** | **Do** (cheap, useful, built from the existing forecasts) | Logic tested; calibration can only be checked over several seasons | Step 6 |
| Stacked **feature model** (form, rest, head-to-head, shots) | **Defer: run in shadow** | +0.0034, interval -0.0016 to +0.0085: not proven | Step 7 |
| **Lineups and injuries** | **Trial for 2 months** (paid API) | Not testable here: needs historical lineup data | Step 8 |
| **xG** from a provider | **Optional trial** after Step 8 | Not testable here. The free shot-based proxy is already inside Step 7 | Step 9 |
| **In-play** updating | **Defer** until you have your own live data | No minute-by-minute data to validate with | Step 10 |
| Bivariate Poisson, negative binomial or zero-inflated **goals** models | **Reject** | All within 0.001 log loss of the current Dixon-Coles model | none |
| **Referee** tendencies for cards | **Reject** | Predicting yellow cards: with referee 1.661 average error, without 1.657, constant 1.712 | none |
| Manager change, motivation, travel | **Skip** | No reliable free data; cannot be tested | none |

The full tables are in Appendix B.

---

## 2. The rules that keep every change honest

These apply to every step. Nothing ships unless it passes them.

**V1. One test harness.** Every change is judged by the same walk-forward backtest: refit every 28 days, predict the next 28 days using only earlier matches. The backtest forecasts are stored in the database (the earlier brief's `backtest` table), one row per match per model version.

**V2. No leakage.** A feature or rating for a match may use only matches played before it. Each step has a test that rewrites the future and proves the number does not change.

**V3. One decision rule** (`decide.py`, Appendix A). A change is **adopted** only if: at least 2,000 matches, the average log-loss gain is at least 0.002, and the whole 95% interval is above zero. If the gain is positive but not proven it runs in **shadow** (computed and stored, never shown). Otherwise it is **rejected**.

**V4. Tune on the past, confirm on the newest season.** Choose any weight or setting using all test seasons except the latest, then report the result on the latest season alone. If the latest season disagrees, say so.

**V5. Label what is not proven.** Each market on the site carries a status from the validation table: validated, experimental, or unavailable. A market that fails is labelled, not hidden.

**V6. Versioned and reversible.** Every forecast row stores `model_version`. Each step is switched on by a setting in `config.py`, so turning it off restores the previous behaviour. Rolling back never changes old, already-graded rows.

**V7. Small sample warning.** Under 100 graded live matches, the site says it is too early to judge. Tests on historical data count as evidence; live results count as monitoring.

---

## 3. Manual work and settings checklist (for you)

Do these once, before the steps that need them. The steps repeat the relevant item.

| # | When | What you do | Why |
|---|---|---|---|
| M1 | Before Step 0 | Install **scikit-learn 1.9.1** next to the existing libraries: add `scikit-learn==1.9.1` to the root `requirements.txt` **and** to the dependency file beside the Streamlit entry point (the README says that file exists), then run `pip install -r requirements.txt` | Steps 2, 3 and 7 use it. Without it the Streamlit and GitHub Actions builds will fail |
| M2 | Before Step 1 | Check that your football-data.co.uk downloads contain closing-odds columns (command in Step 1). Tell the agent the result | Decides whether the market check is possible |
| M3 | Step 0 | Decide where tests may download real data: the club test files come from `https://raw.githubusercontent.com/datasets/football-datasets/main/datasets/<league>/season-<yyzz>.csv` (for example `premier-league/season-2526.csv`). Put them in `tests/data/club/`. Do not commit them if you want a small repository | The real-data tests skip when the files are absent |
| M4 | Every step | Read the agent's report. When it says **shadow**, **you** decide whether to keep waiting or drop the idea | The rule never overrides you |
| M5 | Step 8 only | Create an API-Football account at api-football.com, choose the **Pro plan ($19 per month, 7,500 requests per day, as published on their page)**, copy the API key, and add it as a GitHub Actions secret named `API_FOOTBALL_KEY` (Settings, Secrets and variables, Actions). Put the same key in your local `.env` as `API_FOOTBALL_KEY=...`. Never paste it into code | The only step that costs money. It fits your $20 monthly limit with $1 to spare |
| M6 | Step 8 only | Decide what time to publish the final forecast. API-Football's documentation says lineups appear **20 to 40 minutes before kickoff**, so a "lock one hour before kickoff" rule cannot use them. Choose: keep the early forecast (no lineups), or publish a final forecast about 30 minutes before kickoff | A product decision only you can make |
| M7 | Step 9 only | Read the terms of use of any xG source before scraping it, and decide whether you accept the risk | I could not check the terms |
| M8 | Steps 2, 3, 5, 6 | After each deployment look at database size: `ls -l data/pitchprob.db` and `git count-objects -vH` | The daily workflow commits the database; history grows with its size |
| M9 | Any time | When a step says "confirm on your own backtest", run `python cli.py backtest` and send the printed table to the agent | My numbers come from public mirrors; yours come from your pipeline |
| M10 | Giving work to an AI agent | Give it **one step at a time**, with the text of this guide for that step and Appendix A. Ask it to run `python -m pytest -q` and to paste the backtest table | Smaller tasks are less likely to go wrong, especially with cheaper models |

---

## 4. The steps

**Order of work:** Step 0 first. Then Steps 1, 2, 3 and 4 in any order. Step 5 and Step 6 after Step 3. Steps 7 to 10 are optional and come last.

### Step 0. Foundation: harness, versions, decision rule
**Goal:** every later step can be measured the same way and switched off.
**Why this way:** one shared harness stops each step from using its own favourable test.

**Do:**
1. Persist walk-forward forecasts in a `backtest` table (the earlier brief's T6 describes it). One row per match and model version with the probabilities, the outcome, and a JSON column of any inputs used.
2. Add a `model_version` column to `predictions` and `backtest`.
3. Add the module `decide.py` (Appendix A) and a command `python cli.py compare --old <version> --new <version>` that loads both versions' backtest rows for the same matches, calls `paired_gain` on the per-match log loss, prints the gain, the interval and the decision.
4. Add one setting per later step in `config.py`, for example `USE_ELO_BLEND = False`, `USE_PLATT = False`, `USE_NB_CORNERS = False`. All start off.
5. Add `scikit-learn` (M1).

**Done when:** `python cli.py compare --old dc --new dc` prints gain 0.000, and the tests for `decide.py` pass.
**Rollback:** nothing changes behaviour yet.

### Step 1. Market check against bookmaker closing odds
**Goal:** know whether the model is any good compared with the market.
**Why this way:** the closing line is the best public estimate of match probabilities. It is a measuring stick, not a model input, so it cannot break anything.

**Do:**
1. Check which odds columns your downloads contain (M2):
   ```
   python -c "import penaltyblog as pb; df = pb.scrapers.FootballData('ENG Premier League','2025-2026').get_fixtures(); print([c for c in df.columns if c.startswith(('avg','psc','psch','b365','max'))])"
   ```
   Names depend on penaltyblog's snake-case conversion. Closing average odds are expected as `avg_ch`, `avg_cd`, `avg_ca`, Pinnacle closing as `psch`, `pscd`, `psca`, Bet365 closing as `b365_ch`, `b365_cd`, `b365_ca`. Use the first complete set found; store it as `mk_h`, `mk_d`, `mk_a` after `devig` (Appendix A).
2. Add `market_check.py` (Appendix A) and a command `python cli.py market-check` that prints log loss for: the model, the bookmaker, and the 50/50 mix, on the matches that have odds.
3. Read the result as follows: if the model is **within 0.01** of the bookmaker, it is strong. If the **50/50 mix beats both**, the model adds information the market lacks, so keep going. If the bookmaker is far better (more than 0.02), the model is missing something real: do Steps 2 and 8 before anything else.

**Done when:** the command prints the three numbers for each league.
**If the columns are missing:** skip this step and say so on the site's Insights page. Do not substitute guesses.

### Step 2. Blend with Elo ratings (club leagues only)
**Goal:** a small, proven accuracy gain for Home/Draw/Away.
**Why this way (chosen over a stacked feature model):** Elo is a rating that reacts to recent results in a different way from Dixon-Coles. Averaging two different, similarly good models reduces errors. It needs no training beyond one tiny mapping, it is explainable, and the gain was **statistically supported** (+0.005, interval above zero). The feature model was not.

**Evidence:** club test, 3,458 matches: Dixon-Coles 0.9944, Elo alone 0.9937, 50/50 blend 0.9893. For national teams the blend did **not** help (Appendix B), so do not apply it to the Nations League.

**Do:**
1. Add `elo.py` (Appendix A). Settings tested: K 20, home advantage 60 Elo points, rating 1500 for new teams, a margin-of-victory multiplier. Do not change them without a new test.
2. In the backtest, compute `pre_match_diffs` over **all** stored matches in date order (the earlier seasons warm the ratings up). For each 28-day block, fit `EloMapper` on matches before the block and predict the block. Store `p_*_elo`.
3. Store the blend as model version `dc_elo50`: `blend(dc_probs, elo_probs, weight)`.
4. Choose the weight by V4: try 0.35 and 0.5 on all but the latest season, confirm on the latest. I found both significant on the combined test.
5. Run `compare --old dc --new dc_elo50`. If the decision is `adopt`, set `USE_ELO_BLEND = True`.
6. Live forecasting: each night rebuild Elo from all stored matches (about 12,000 rows, a second or two), fit the mapper on all matches, and for each upcoming fixture compute `elo.diff(league, home, away)`. Promoted teams start at 1500: flag this on the match page ("new to the league").

**Done when:** the backtest decision is printed and the no-leakage test passes (Appendix A, `test_pre_match_elo_never_sees_the_future`).
**Rollback:** set `USE_ELO_BLEND = False`.

### Step 3. Recalibrate Over/Under and Both Teams To Score
**Goal:** make the goal-total probabilities honest.
**Why this way (chosen over isotonic):** Platt scaling learns just two numbers, so it is stable. Isotonic regression gave smaller gains (Over 2.5: Platt 0.6806, isotonic 0.6834, raw 0.6853, constant 0.6909).

**Evidence:** gains +0.0042 (Over 1.5), +0.0047 (Over 2.5), +0.0065 (BTTS); all intervals above zero. Raw BTTS (0.6920) was worse than a constant guess (0.6887); recalibrated it is 0.6855.

**Do:**
1. Add `recalibrate.py` (Appendix A).
2. In the backtest, for each 28-day block fit one `PlattCalibrator` per market (Over 1.5, Over 2.5, Over 3.5, BTTS) on the **earlier** backtest forecasts and what happened, then transform the block. Store as model version `dc_platt`.
3. Run `compare` per market. Adopt each market separately.
4. Live: refit calibrators monthly on all backtest and graded live forecasts; apply to new forecasts.
5. Also apply to the Nations League totals once it has at least 500 backtest matches. Until then keep its totals labelled experimental.

**Done when:** each market has a decision and the monotonic-order test passes (calibration must not reorder forecasts).
**Rollback:** `USE_PLATT = False`.

### Step 4. Confirm the recency setting
**Goal:** keep your "mostly the last two years" rule without hurting accuracy.
**Evidence:** 1095 days with decay 0.0019 (87% of the weight on the last two years for the national-team model; compute the share for clubs with the earlier brief's function) scored 0.9895; the best setting tested (1500 days, 0.001) scored 0.9888. A strict 730 days scored 0.9930. The difference between your setting and the best is negligible.

**Do:** run `python cli.py compare-recency` from the earlier brief on your own data and keep your setting unless it loses more than 0.005 to the best. Print the weight share in the report.
**Done when:** the table is in the report. **Rollback:** edit two numbers in `config.py`.

### Step 5. Corners with a negative binomial model
**Goal:** useful per-team corner lines, and honest total lines.
**Why this way:** corner counts vary more than a Poisson model allows (variance 1.2 times the mean in my data), and the negative binomial handles that. It was better than Poisson in every corner market tested.

**Evidence (5,202 matches):**

| Market | Constant | Poisson | Negative binomial |
|---|---|---|---|
| Total over 8.5 | 0.6634 | 0.6627 | 0.6608 |
| Total over 9.5 | 0.6880 | 0.6882 | 0.6855 |
| Total over 10.5 | 0.6624 | 0.6645 | 0.6609 |
| Home team over 4.5 | 0.6842 | 0.6612 | 0.6531 |
| Away team over 3.5 | 0.6820 | 0.6709 | 0.6634 |

Total corners hardly beat a constant guess. Team lines do. So the site should lead with the team lines and label totals "experimental".

**Do:**
1. Replace the Poisson corner model of the earlier brief with `penaltyblog.models.NegativeBinomialGoalModel` on the corner counts (same weights, `predict(home, away, max_goals=30).grid`).
2. Record corner forecasts in the backtest and compute `market_validation` rows for `corners_home_4.5`, `corners_away_3.5` and `corners_total_9.5`.
3. `compare` Poisson against negative binomial per market, then adopt.
4. Keep the season and head-to-head average cards separate, as in the earlier brief.

**Done when:** corner rows exist in `market_validation`. **Rollback:** `USE_NB_CORNERS = False`.

### Step 6. Season simulations
**Goal:** "chance of winning the title / finishing top four / being relegated" for each club.
**Why this way:** it reuses the scoreline tables you already store. A Monte Carlo of 10,000 seasons takes seconds and needs no new data.

**Do:**
1. Add `season_sim.py` (Appendix A). Inputs: today's table (points, goal difference, goals for) built from the `matches` table, and the remaining fixtures each with its stored scoreline table.
2. The remaining fixtures for a whole season are not all in the API (only the next 7 days are fetched). Get the full fixture list for each league once per season from football-data.org (`/competitions/{code}/matches?season=...`, one call per league) or from the football-data.co.uk results plus a fixture list file. Verify the source before coding; I did not.
3. For fixtures beyond the 7-day horizon, compute forecasts on the fly from the saved model.
4. Add `GET /api/simulation?competition=PL` returning each team's probability of each position and the summary probabilities. Show it on the Insights or a new Table page.
5. Validate over time: store each week's title, top-four and relegation probabilities; at season end compare with what happened (log loss per team). One season is a small sample: label it "not yet validated".

**Done when:** each team's position probabilities sum to 1 and each position's probabilities across teams sum to 1 (tests in Appendix A).
**Rollback:** remove the page.

### Step 7. Stacked feature model (run in shadow)
**Goal:** learn whether form, rest days, head-to-head and shots add anything.
**Why shadow:** the gain was +0.0034 with an interval from -0.0016 to +0.0085. That is a hint, not proof.

**Do:** build the features (last-5 form, season points per game, venue form, shots on target balance, rest days, head-to-head, league goals per game), all from earlier matches only. Fit a logistic regression on the goals model's probabilities plus the features (settings: standardise, regularisation C=0.3, median imputation). Store as `dc_stack` and **do not show it**. Re-run `compare` each month. Promote it when the rule says `adopt` or when the combination "Elo blend + features" (+0.0046) is proven.
**Rollback:** nothing to roll back; it is not shown.

### Step 8. Lineups and injuries (two-month paid trial)
**Goal:** find out whether knowing who plays improves forecasts.
**Why a trial:** this is the information bookmakers use and your model lacks. But it costs money and needs history to test.

**Verified from API-Football's documentation:** the API has endpoints for fixtures, lineups, injuries, players, coaches, predictions and odds; the key is sent in the `x-apisports-key` header; lineups are available **20 to 40 minutes before kickoff** for covered competitions (coverage is listed per league in the `/leagues` endpoint). Pro plan: $19 per month, 7,500 requests per day. I could not test the data quality.

**Do:**
1. M5 and M6 first (key, secret, forecast timing decision).
2. Check coverage: call `/leagues` and print, for your five leagues, the coverage flags for lineups, injuries and players. If any flag is false, stop for that league.
3. Backfill: for the last two seasons, fetch lineups for each fixture (about 1,750 fixtures per season across the five leagues, one call each). At 7,500 calls per day this takes under a day per season. Store compact rows: fixture, team, starting eleven player ids, formation.
4. Build one feature: **share of the team's usual minutes missing**: from the previous 10 matches compute each player's share of team minutes; sum the share for players not in today's starting eleven. Derive it for both teams.
5. Add it to the stacked model of Step 7 and to the Elo-blend model as a shift in expected goals; compare with `compare`.
6. Run live for the second month: fetch lineups about 35 minutes before kickoff and store the forecast before and after the lineup.
7. Cancel the subscription if after two months the gain is not proven. Keep the stored data.

**Done when:** the decision is printed for "with lineups" against "without lineups".
**Rollback:** cancel the plan; the code path is skipped when `API_FOOTBALL_KEY` is empty.

### Step 9. xG data (optional, after Step 8)
**Goal:** replace shots-based strength with real expected goals.
**Why last:** the shot-based proxy is already in Step 7. `penaltyblog` includes an Understat scraper in its source, so xG for the big five leagues may be reachable for free, but I could not reach it or read its terms (M7).
**Do:** if you accept the risk, scrape each match's xG for past seasons into a separate table, compute a rating from xG as for goals, and compare in shadow. Drop it if the gain is below 0.002.

### Step 10. In-play updating (defer)
**Why defer:** I have a first formula (`live_update.py`, Appendix A) that assumes goals arrive evenly over 90 minutes. Real goal rates change through a match and after red cards, and I have no minute-by-minute data to test it. Do not show it to users yet.
**Do now:** record, for every match, the live score at five-minute marks and any red cards (API-Football `fixtures?live=all` covers this per its documentation; check your plan's limits first). After one season, test the formula against what actually happened.

---

## 5. Cost, time and risk summary

| Step | Money | Effort (my estimate) | Expected gain | Risk |
|---|---|---|---|---|
| 0 Foundation | $0 | 1 to 2 days | none directly | low |
| 1 Market check | $0 | 0.5 day | knowledge | none |
| 2 Elo blend | $0 | 1 day | +0.005 log loss | low |
| 3 Recalibration | $0 | 1 day | +0.004 to +0.0065 | low |
| 4 Recency | $0 | 0.5 day | none (protects) | none |
| 5 Corners NB | $0 | 1 day | small; honest labels | low |
| 6 Simulations | $0 | 2 days | product value | low |
| 7 Features | $0 | 2 days | maybe +0.003 | overfitting |
| 8 Lineups | $19 per month for 2 months | 4 to 6 days | unknown | data quality, timing |
| 9 xG | $0 or paid | 2 to 3 days | unknown | terms of use |
| 10 In-play | later | later | unknown | high |

A realistic ceiling: the combined tested gains are around 0.01 log loss. That is real but modest; it does not turn forecasts into winning bets. Bookmakers' margins and the legal questions in the first research report still apply to anything involving betting.


---

## Appendix A: Reference code (tested)

Run by me: 9 tests passing (Python 3.12.3, scikit-learn 1.9.1, penaltyblog 1.13.1, pandas 3.1). One test uses real club files and skips when they are absent. The modules depend on nothing else in your repo; adapt the import paths.

To fetch the real club files for the real-data test (about 2 MB; I checked that all 35 downloads work), save the script below and run `python fetch_test_data.py`.

### `fetch_test_data.py`

```python
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
```

### `decide.py` (the rule from section 2)

```python
"""The rule that decides whether a change ships. Used for every step in the guide."""
import numpy as np

MIN_MATCHES = 2000        # smaller samples cannot separate a real gain of 0.003 from luck
MIN_GAIN = 0.002          # smallest average log-loss gain worth the extra complexity


def paired_gain(loss_old, loss_new, n_boot: int = 2000, seed: int = 0) -> dict:
    """Per-match loss difference (old minus new; positive = the new version is better) and its 95% bootstrap interval."""
    d = np.asarray(loss_old, dtype=float) - np.asarray(loss_new, dtype=float)
    rng = np.random.default_rng(seed)
    means = [rng.choice(d, len(d)).mean() for _ in range(n_boot)]
    return {"n": len(d), "gain": float(d.mean()), "low": float(np.percentile(means, 2.5)), "high": float(np.percentile(means, 97.5))}


def decide(result: dict, min_matches: int = MIN_MATCHES, min_gain: float = MIN_GAIN) -> str:
    """'adopt' only if the whole interval is above zero, the gain is big enough and the sample is large enough."""
    if result["n"] >= min_matches and result["low"] > 0 and result["gain"] >= min_gain:
        return "adopt"
    if result["gain"] > 0:
        return "shadow"        # run it quietly next to the live model and collect more matches
    return "reject"
```

### `elo.py` (Step 2)

```python
"""Elo ratings and the blend with the goals model (tested: +0.005 log loss on 3,458 real club matches)."""
import math
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

K, HOME_ADV, START = 20.0, 60.0, 1500.0     # settings used in the test; change only with a new test


class EloRatings:
    def __init__(self, k=K, home_adv=HOME_ADV, start=START):
        self.k, self.home_adv, self.start, self.r = k, home_adv, start, {}

    def diff(self, league: str, home: str, away: str) -> float:
        """Home rating plus home advantage minus away rating, BEFORE the match is played."""
        return self.r.get((league, home), self.start) + self.home_adv - self.r.get((league, away), self.start)

    def update(self, league: str, home: str, away: str, hg: int, ag: int) -> None:
        a, b = self.r.get((league, home), self.start), self.r.get((league, away), self.start)
        expected = 1 / (1 + 10 ** (-(a + self.home_adv - b) / 400))
        score = 1.0 if hg > ag else 0.0 if hg < ag else 0.5
        margin = math.log(abs(hg - ag) + 1) + 1 if hg != ag else 1.0       # bigger wins move ratings more
        delta = self.k * margin * (score - expected)
        self.r[(league, home)], self.r[(league, away)] = a + delta, b - delta


def pre_match_diffs(matches: pd.DataFrame) -> pd.Series:
    """matches: columns league, home, away, hg, ag, sorted by date. Returns each match's Elo difference before kickoff."""
    elo, out = EloRatings(), []
    for r in matches.itertuples():
        out.append(elo.diff(r.league, r.home, r.away))
        elo.update(r.league, r.home, r.away, r.hg, r.ag)
    return pd.Series(out, index=matches.index)


class EloMapper:
    """Turns an Elo difference into probabilities [home, draw, away]. Refit on earlier matches before every use."""
    def fit(self, diffs, results):                       # results: 0 = home win, 1 = draw, 2 = away win
        self.model = make_pipeline(StandardScaler(), LogisticRegression(C=0.3, max_iter=2000))
        self.model.fit(np.asarray(diffs, dtype=float).reshape(-1, 1), np.asarray(results))
        return self

    def predict(self, diffs) -> np.ndarray:
        return self.model.predict_proba(np.asarray(diffs, dtype=float).reshape(-1, 1))


def blend(goals_model_probs, elo_probs, weight: float = 0.5) -> np.ndarray:
    """Weighted average of two probability tables (rows = matches, columns = H, D, A). 0.5 was the best tested weight."""
    out = (1 - weight) * np.asarray(goals_model_probs) + weight * np.asarray(elo_probs)
    return out / out.sum(axis=1, keepdims=True)
```

### `recalibrate.py` (Step 3)

```python
"""Platt recalibration for Over/Under and Both-Teams-To-Score (tested: +0.004 to +0.0065 log loss on real club matches)."""
import numpy as np
from sklearn.linear_model import LogisticRegression


def _logit(p):
    p = np.clip(np.asarray(p, dtype=float), 1e-4, 1 - 1e-4)
    return np.log(p / (1 - p))


class PlattCalibrator:
    """Learns a stretch and a shift of the model's probability, from EARLIER forecasts and what happened."""
    def fit(self, raw_probs, happened):
        self.model = LogisticRegression(C=1e3, max_iter=1000)       # nearly unpenalised: only two numbers are learned
        self.model.fit(_logit(raw_probs).reshape(-1, 1), np.asarray(happened).astype(int))
        return self

    def transform(self, raw_probs) -> np.ndarray:
        return self.model.predict_proba(_logit(raw_probs).reshape(-1, 1))[:, 1]
```

### `market_check.py` (Step 1)

```python
"""Compare the model with bookmaker closing odds. The market is the hardest benchmark there is."""
import numpy as np
import pandas as pd


def devig(odds: np.ndarray) -> np.ndarray:
    """Decimal odds [home, draw, away] -> probabilities without the bookmaker's margin (proportional method)."""
    inverse = 1 / np.asarray(odds, dtype=float)
    return inverse / inverse.sum(axis=-1, keepdims=True)


def log_loss_1x2(probs: np.ndarray, results: np.ndarray) -> float:
    return float(-np.log(np.clip(probs[np.arange(len(results)), results], 1e-12, 1)).mean())


def compare_with_market(model_probs: np.ndarray, market_probs: np.ndarray, results: np.ndarray) -> pd.DataFrame:
    """All three inputs refer to the same matches. Also reports the 50/50 mix, which shows whether the model adds anything the market lacks."""
    mix = (model_probs + market_probs) / 2
    rows = [("Model", model_probs), ("Bookmaker closing odds", market_probs), ("50/50 mix", mix)]
    return pd.DataFrame({"log_loss": [log_loss_1x2(p, results) for _, p in rows]}, index=[n for n, _ in rows])
```

### `season_sim.py` (Step 6)

```python
"""Monte Carlo season simulation: how likely is each final position?"""
import numpy as np


def simulate(table: dict, fixtures: list[dict], n_sims: int = 10000, seed: int = 0) -> dict:
    """table: {team: {"points": int, "gd": int, "gf": int}} today.
    fixtures: remaining matches [{"home", "away", "grid": 2-D array of scoreline probabilities (row = home goals)}].
    Returns {team: array of length n_teams with P(final position = 1..n)}. Ties: points, goal difference, goals for."""
    rng = np.random.default_rng(seed)
    teams = list(table)
    idx = {t: i for i, t in enumerate(teams)}
    pts = np.array([table[t]["points"] for t in teams], dtype=float)[None, :].repeat(n_sims, 0)
    gd = np.array([table[t]["gd"] for t in teams], dtype=float)[None, :].repeat(n_sims, 0)
    gf = np.array([table[t]["gf"] for t in teams], dtype=float)[None, :].repeat(n_sims, 0)
    for fx in fixtures:
        grid = np.asarray(fx["grid"], dtype=float)
        flat = rng.choice(grid.size, size=n_sims, p=(grid / grid.sum()).ravel())
        hg, ag = np.divmod(flat, grid.shape[1])
        h, a = idx[fx["home"]], idx[fx["away"]]
        pts[:, h] += np.where(hg > ag, 3, np.where(hg == ag, 1, 0)); pts[:, a] += np.where(ag > hg, 3, np.where(hg == ag, 1, 0))
        gd[:, h] += hg - ag; gd[:, a] += ag - hg; gf[:, h] += hg; gf[:, a] += ag
    score = pts * 1e6 + gd * 1e3 + gf                       # larger = better; fine for realistic totals
    order = np.argsort(-score, axis=1, kind="stable")        # team indices from first place to last
    position = np.empty_like(order)
    np.put_along_axis(position, order, np.arange(order.shape[1])[None, :].repeat(n_sims, 0), axis=1)
    return {t: np.bincount(position[:, idx[t]], minlength=len(teams)) / n_sims for t in teams}
```

### `live_update.py` (Step 10: not validated, do not show to users)

```python
"""In-play probabilities from the pre-match goal rates. NOT VALIDATED: do not show to users until it has been tested on your own live data."""
import math
import numpy as np


def inplay_1x2(lam: float, mu: float, minute: int, home_goals: int, away_goals: int, max_goals: int = 12) -> dict:
    """Assumes goals arrive at a constant rate over 90 minutes (real rates rise late in matches, so this is only a first approximation)."""
    left = max(90 - minute, 0) / 90
    pm = lambda k, m: math.exp(-m) * m ** k / math.factorial(k)
    ph = np.array([pm(k, lam * left) for k in range(max_goals)]); pa = np.array([pm(k, mu * left) for k in range(max_goals)])
    grid = np.outer(ph, pa); grid /= grid.sum()
    i, j = np.indices(grid.shape)
    final = (i + home_goals) - (j + away_goals)
    return {"p_home": float(grid[final > 0].sum()), "p_draw": float(grid[final == 0].sum()), "p_away": float(grid[final < 0].sum())}
```

### `tests/test_sharpen.py`

```python
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
```

---

## Appendix B: Evidence tables

All numbers are log loss (lower is better) unless stated. "No-model" and "constant" use frequencies from earlier matches only.

### B1. Goals models and recency (5,186 matches, walk-forward, 5 leagues)

Model names: `dc` = Dixon-Coles, `bp` = bivariate Poisson, `nb` = negative binomial, `zip` = zero-inflated Poisson. The numbers after the name are the window in days and the decay (`_19` = 0.0019, `_10` = 0.001). Columns: Home/Draw/Away log loss, ranked probability score, Over 1.5, Over 2.5, Both Teams To Score, correct-score -log(probability of the real score), and the average error in total goals per match.

```text
ALL 3 SEASONS (2023-24 to 2025-26): n=5186
                   1X2 logloss     RPS    O1.5    O2.5    BTTS  score -logp  goals bias
model                                                                                  
no-model baseline       1.0754  0.2302  0.5291  0.6869  0.6889          NaN         NaN
bp_1095_19              0.9909  0.2005  0.5272  0.6801  0.6882       2.9297     -0.0391
dc_1095_10              0.9899  0.2006  0.5259  0.6796  0.6889       2.9288     -0.0464
dc_1095_19              0.9895  0.2004  0.5260  0.6802  0.6893       2.9287     -0.0410
dc_1500_10              0.9888  0.2002  0.5254  0.6787  0.6882       2.9263     -0.0493
dc_730_19               0.9930  0.2012  0.5276  0.6834  0.6918       2.9378     -0.0370
nb_1095_19              0.9899  0.2004  0.5262  0.6802  0.6897       2.9278     -0.0411
poisson_1095_19         0.9904  0.2004  0.5262  0.6803  0.6900       2.9297     -0.0411
zip_1095_19             0.9904  0.2004  0.5262  0.6803  0.6900       2.9297     -0.0411

LAST SEASON ONLY (2025-26): n=1729
                   1X2 logloss     RPS    O1.5    O2.5    BTTS  score -logp  goals bias
model                                                                                  
no-model baseline       1.0724  0.2290  0.5437  0.6871  0.6899          NaN         NaN
bp_1095_19              0.9994  0.2033  0.5431  0.6923  0.6911       2.9166      0.0018
dc_1095_10              0.9978  0.2031  0.5421  0.6920  0.6916       2.9170      0.0011
dc_1095_19              0.9987  0.2032  0.5424  0.6926  0.6919       2.9174     -0.0010
dc_1500_10              0.9954  0.2023  0.5415  0.6907  0.6920       2.9128     -0.0065
dc_730_19               1.0037  0.2046  0.5444  0.6963  0.6944       2.9274      0.0013
nb_1095_19              0.9985  0.2033  0.5427  0.6926  0.6924       2.9149     -0.0013
poisson_1095_19         0.9997  0.2033  0.5427  0.6927  0.6930       2.9184     -0.0013
zip_1095_19             0.9997  0.2033  0.5427  0.6927  0.6930       2.9184     -0.0013

Home/Draw/Away log loss by league (all 3 seasons):
dc_1095_19  dc_1500_10  dc_730_19  bp_1095_19
PL      0.9831      0.9876     0.9841      0.9832
PD  0.9732  0.972  0.9748  0.9772
SA  0.9863  0.9848  0.9906  0.9862
BL1  1.003  1.002  1.0067  1.0072
FL1  1.0083  1.003  1.0158  1.0068
```

**Reading it:**
- Every goals model beats the no-model forecast clearly for Home/Draw/Away (about 0.990 against 1.075).
- Bivariate Poisson, negative binomial and zero-inflated Poisson are within 0.001 of Dixon-Coles: no reason to switch.
- Recency: 1095 days with decay 0.0019 (0.9895) is within 0.0007 of the best setting (1500 days, 0.001: 0.9888). A strict 730 days is worse (0.9930).
- In the **latest season alone** (2025-26) the raw Over 2.5 (0.6926) and BTTS (0.6919) forecasts were worse than the constant (0.6871 and 0.6899). That is why Step 3 exists.
- Differences between leagues are small; Ligue 1 and the Bundesliga are the hardest to forecast.

### B2. Stacking, Elo blend and recalibration (3,458 matches, 2024-25 and 2025-26)

`platt` on the 1X2 line means a recalibration of the Home/Draw/Away probabilities themselves (no gain). `stack_*` use logistic regression with the listed inputs. `blendNN` is the Dixon-Coles probabilities mixed with Elo probabilities at weight NN%.

```text
n = 3458 (2024-25 and 2025-26)
no-model (overall freq)      logloss 1.0750  RPS 0.2311
dc                           logloss 0.9944  RPS 0.2027  top-pick right 51.9%
platt                        logloss 0.9956  RPS 0.2029  top-pick right 52.1%
elo_only                     logloss 0.9937  RPS 0.2027  top-pick right 52.1%
stack_feats                  logloss 0.9910  RPS 0.2014  top-pick right 52.7%
stack_elo                    logloss 0.9916  RPS 0.2019  top-pick right 52.0%
blend20                      logloss 0.9907  RPS 0.2020  top-pick right 52.1%
blend35                      logloss 0.9896  RPS 0.2017  top-pick right 51.9%
blend50                      logloss 0.9893  RPS 0.2016  top-pick right 52.2%
stack_feats_elo              logloss 0.9899  RPS 0.2009  top-pick right 52.5%
gain over DC for elo_only        : +0.0008 log loss (95% CI -0.0056 to +0.0076)  [positive = better]
gain over DC for blend35         : +0.0048 log loss (95% CI +0.0018 to +0.0081)  [positive = better]
gain over DC for blend50         : +0.0051 log loss (95% CI +0.0013 to +0.0094)  [positive = better]
gain over DC for stack_feats     : +0.0034 log loss (95% CI -0.0016 to +0.0085)  [positive = better]
gain over DC for stack_feats_elo : +0.0046 log loss (95% CI -0.0009 to +0.0106)  [positive = better]
o15   gain of Platt over raw: +0.0042 (95% CI +0.0012 to +0.0071)
o15   constant 0.5360 | raw 0.5334 | platt 0.5293 | platt_ctx 0.5292 | isotonic 0.5307
o25   gain of Platt over raw: +0.0047 (95% CI +0.0018 to +0.0076)
o25   constant 0.6909 | raw 0.6853 | platt 0.6806 | platt_ctx 0.6801 | isotonic 0.6834
btts  gain of Platt over raw: +0.0065 (95% CI +0.0026 to +0.0104)
btts  constant 0.6887 | raw 0.6920 | platt 0.6855 | platt_ctx 0.6857 | isotonic 0.6884
```

**Reading it:** the Elo blend at 35% or 50% is the only change to Home/Draw/Away with an interval entirely above zero. Platt recalibration helps all three goal-total markets, with intervals above zero. The feature model is a hint, not proof.

### B3. National teams: does the Elo blend help? (288 UEFA Nations League matches)

I built Elo ratings from all international matches since 1990 (home advantage 0 for neutral venues, K 20 for friendlies and 30 otherwise) and blended with the Dixon-Coles national-team model.

```text
Dixon-Coles 0.8851 | Elo only 0.9105 | blend 50% 0.8908 | blend 30% 0.8870 | no model 1.0886
Gain of the 50% blend over Dixon-Coles: -0.0057 (95% interval -0.0191 to +0.0069)
```

Verdict: do not use the Elo blend for the Nations League (run it in shadow only).

### B4. Corners and cards

Corner results are in Step 5 (5,202 matches). Total corners per match averaged 9.68; the Poisson model predicted 9.65. For cards (Premier League, 2,660 matches with referee names; 1,137 forecasts tested): average error in total yellow cards was 1.657 using the two teams' recent card counts, 1.661 adding the referee's average, and 1.712 for a constant. The referee added nothing.

---

## Appendix C: What is verified and what is not

**Verified by running code on real data:** every number in section 1 and Appendix B (from public mirrors: club files at `github.com/datasets/football-datasets`, national results at `github.com/martj42/international_results`); the reference code and its tests; that the `fetch_test_data.py` downloads work.

**Verified from documentation:** API-Football's endpoints (fixtures, lineups, injuries, players, coaches, predictions, odds), the `x-apisports-key` header, lineups appearing 20 to 40 minutes before kickoff, and the Pro price and daily request limit (their published page).

**Not verified:**
- Whether your football-data.co.uk downloads contain closing-odds columns (Step 1 tells you).
- The quality of API-Football lineup and injury data and its historical coverage (Step 8 checks coverage flags).
- Understat access and terms (Step 9).
- Whether the football-data.org free plan can return a full-season fixture list for Step 6.
- Any in-play behaviour (Step 10).
- My club-data tests exclude the Champions League and use files without odds, so the market comparison could not be run.
