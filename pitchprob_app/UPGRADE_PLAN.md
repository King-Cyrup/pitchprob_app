# PitchProb Upgrade Plan — Phase 2

**Date:** 2026-11-01 | **Status:** Spec approved, research done — no code yet

---

## User decisions (from clarifications)

| Question | Answer |
|---|---|
| Build order | Quick wins first (no-dependency features), new data source after |
| API-Football | Research free tier → use if viable, skip corners/lineups if not |
| Champions League | Yes — add back as a properly-configured 6th league |
| Spread calibration definition | Confirmed: "when the top pick is X points ahead of second-best, how often is it correct?" |
| Handicap | Asian handicap |

---

## Research results

### API-Football free tier

**Verdict: VIABLE for prototyping.**

API-Football provides a free tier ($0/mo) that includes **every endpoint** without
paywalls — corners, lineups, injuries, odds, statistics, H2H, etc.  The constraints:

| Constraint | Detail |
|---|---|
| 100 requests / day | Tight for 5+ leagues — need aggressive caching |
| 10 requests / min | Same as football-data.org's free plan |
| `coverage` flags | Must check per-league before calling endpoints — not all leagues track all stats |

**What's available:**

| Data | Endpoint | Notes |
|---|---|---|
| Corners (per fixture) | `/fixtures/statistics` → `corner kicks` | Must check `coverage.fixture_statistics` per league |
| Lineups (Starting XI + bench + formation + coach) | `/fixtures/lineups` | Available 20–40 min before kickoff, some leagues only post-match |
| Injuries & suspensions | `/injuries` | Filterable by league, team, fixture, or date. Types: "Injury", "Suspension". Updates every 4h |
| Pre-match odds | `/odds` | Multiple bookmakers, useful for ensemble / calibration |
| H2H stats | `/fixtures/headtohead` | Direct H2H comparison between two teams |

**Plan:** integrate API-Football as a secondary data source after the quick-win
features are done.  The 100 req/day limit means we must be surgical — fetch only
what's needed for upcoming fixtures, cache aggressively, and batch calls.

### Open-source football prediction repositories

| Repo | What it contributes | Relevance |
|---|---|---|
| **[Reymes/fottball-match-prediction](https://github.com/Reymes/football-match-prediction)** | Dixon-Coles + LightGBM ensemble, Elo ratings, xG features, form, Asian handicap, de-vigged market odds, 22 leagues, 2025 data | **HIGH** — builds on the same Dixon-Coles foundation PitchProb uses |
| **[jdgoated1/football-predictor](https://github.com/jdgoated1/football-predictor)** | 5-model ensemble (Dixon-Coles + Elo + Pi-rating + XGBoost + CatBoost), rolling xG, form, streaks, H2H, rest days, WC 2026 priors | **HIGH** — multi-model approach worth studying for ensemble ideas |
| **[danielsaed/futbol_corners_forecast](https://github.com/danielsaed/futbol_corners_forecast)** | Dedicated corners model — XGBoost, 269 features, MAE 1.93 on 21k matches | **MEDIUM** — relevant when we build the corners feature |
| **[yafetful/tikml](https://github.com/yafetful/tikml)** | 84 features across 12 categories, corner-specific model module, rolling xG + tactical features | **MEDIUM** — feature engineering patterns worth borrowing |
| **[LForcher/ai_match_analysis](https://github.com/LForcher/ai_match_analysis)** | RF/XGBoost regressors → Double Poisson simulation, xG/EPV features | **LOW** — different architecture but ideas for xG integration |

**Key takeaway:** Both Reymes and jdgoated1 use the **exact same** Dixon-Coles model
PitchProb already trains (via `penaltyblog`), then layer **ensemble models** (LightGBM,
XGBoost) with **form, xG, and market-odds features** on top.  This is the natural
evolution path for PitchProb's model.

---

## Implementation plan — ordered by phase

### Phase 2a: Quick wins (no new data, no new deps)

These all use the existing `matches` / `fixtures` / `predictions` / `grades` tables.

| # | Feature | What changes | Files touched |
|---|---|---|---|
| **Q1** | **xG display** | Show `xg_home` / `xg_away` on upcoming fixtures and track record. Add tooltip: "expected goals". Model already computes + stores this. | `templates/index.html`, `app.py` (pass xG fields to template context — already done) |
| **Q2** | **Form strip per team** | Last 5 match results as W/D/L badges (🟢⚪🔴) next to team name in fixture table. Computed from `matches`. | `app.py` (new `_team_form()`), `templates/index.html` |
| **Q3** | **H2H — last 5 meetings** | Click/tap a fixture → expand row showing last 5 H2H results between those two teams. | `app.py` (new `/api/h2h?home=X&away=Y`), `templates/index.html` |
| **Q4** | **League home-advantage stat** | Extract the Dixon-Coles home-advantage parameter per league, display on the page (e.g., goal advantage). | `modeling.py` (expose param from fitted model), `app.py`, template |
| **Q5** | **Per-league accuracy stats** | Expand the track-record stats from overall → per-league. Show pick-rate and log-loss per league in a compact grid. | `app.py` (`_ledger` enhancement), template |
| **Q6** | **Matchday summary view** | After each matchday: "Matchday 12: 7/10 correct (70%)". Show last 3 matchdays as stat cards. | `app.py`, template |
| **Q7** | **Spread calibration analysis** | New analysis: group all graded predictions by the percentage-point gap between the top pick and the second-highest probability. For each gap band, show how often the top pick was correct. | `report.py` (new `calibration_by_spread()`), `app.py`, template |

### Phase 2b: Model enhancement (no new data, uses current sources)

| # | Feature | Approach | Files touched |
|---|---|---|---|
| **M1** | **Form-weighted Dixon-Coles** | The model already uses time-decay (`xi=0.001`). Add a form-feature vector as an ensemble input: train a LightGBM on top of Dixon-Coles output + form/H2H/season features. Study **Reymes/football-match-prediction** for the stacking pattern. | New `ensemble.py`, `modeling.py`, `predict.py` |
| **M2** | **Asian handicap probabilities** | Dixon-Coles output (goal matrix) can compute handicap-adjusted probabilities: P(home -1.5 goals), P(away +0.5), etc. This is a pure computation from the existing goal matrix. | `modeling.py` (new `forecast_handicap()` function), template |
| **M3** | **Big-match-impact flag** | If Champions League is added (Phase 2d), flag fixtures where one team has a CL match within 4 days — potential rotation/rest impact. | `app.py`, template |

### Phase 2c: Post-match comparison & auto-retraining

| # | Feature | Approach | Files touched |
|---|---|---|---|
| **P1** | **Side-by-side prediction vs actual** | The page already shows recent graded matches. Enhance with a visual hit/miss indicator and the spread between prediction and reality. | `templates/index.html` |
| **P2** | **Auto-detected "fresh results"** | When `grade_predictions` runs and finds new results, flag them as "new" in the DB. The page highlights fresh results. | `predict.py`, `db.py` (add `is_new` column or use `graded_at`), template |
| **P3** | **Matchday completeness indicator** | Detect when all fixtures in a matchday have been graded → show a "Matchday complete" badge. | `app.py`, template |

### Phase 2d: Champions League

| # | Feature | Approach | Files touched |
|---|---|---|---|
| **CL1** | Add CL to `LEAGUES` | `fd_code: "CL"`, `pb_name`: research the exact penaltyblog name (likely `"UEFA Champions League"` or test via `load_history`). Run `check-access` to confirm free-plan access. | `config.py` |
| **CL2** | CL load + train | `load-history` + `train` for the new league. May need fewer seasons (CL format changed recently). | None (pipeline handles any league) |
| **CL3** | CL display tweaks | CL matches in the "Upcoming" section may need a visual differentiator (CL badge/icon). | `templates/index.html` |

### Phase 2e: API-Football integration (corners + lineups + injuries)

*This phase runs only if API-Football's free tier is confirmed viable in real use.*

| # | Feature | Approach | Files touched |
|---|---|---|
| **AF1** | API client module | New `apifootball.py` — wraps `/fixtures/statistics`, `/fixtures/lineups`, `/injuries`, `/fixtures/headtohead`. Handles rate limits (10/min), caching, and `coverage` flag checks. | New `apifootball.py` |
| **AF2** | Corner probabilities | Train a corner model (study **danielsaed/futbol_corners_forecast** for feature engineering). Add corner over/under and per-team corner predictions. | New `corners.py`, `modeling.py` (or ensemble) |
| **AF3** | Lineup impact | When lineups are available, adjust team strength: if a key attacker is missing, reduce attack strength by a calibration factor. Simple v1: flag "key player missing" without adjusting the model. | `app.py`, template |
| **AF4** | Injury feed on page | Show injury/suspension summaries for each upcoming fixture as an expandable section. | `app.py`, template |
| **AF5** | Coach data | Display head coach name per team (from lineups endpoint). V1: display only, no model impact. | `apifootball.py`, template |

---

## Feature delivery schedule

```
Week 1   ████████  Phase 2a: Q1–Q4  (xG, form, H2H, home advantage)
Week 2   ████████  Phase 2a: Q5–Q7  (per-league accuracy, matchday view, spread calibration)
Week 3   ████████  Phase 2b: M1–M2  (ensemble model, Asian handicap)
Week 4   ████████  Phase 2c: P1–P3  (post-match comparison, auto-detect, matchday badge)
Week 5   ████████  Phase 2d: CL1–3  (Champions League)
Week 6+  ████████  Phase 2e: AF1–5 (API-Football — corners, lineups, injuries)
```

Each phase is self-contained: the app remains functional and deployable after every
phase.  Phases 2a–2d require no new data sources or paid APIs.

---

## Sources

- API-Football free tier & coverage: https://www.api-football.com
- Reymes/football-match-prediction: https://github.com/Reymes/football-match-prediction
- jdgoated1/football-predictor: https://github.com/jdgoated1/football-predictor
- danielsaed/futbol_corners_forecast: https://github.com/danielsaed/futbol_corners_forecast
- yafetful/tikml: https://github.com/yafetful/tikml
- football-data.org v4: https://docs.football-data.org
- penaltyblog Dixon-Coles: https://penaltyblog.readthedocs.io

---

> **Status:** Spec complete.  Ready to start Phase 2a (quick wins) on your signal.
> Each feature will be built one at a time with code, tests, and a page refresh to
> confirm it renders.