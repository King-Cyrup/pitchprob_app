# PitchProb: Implementation Brief for an AI Coding Agent

**Features:** UEFA Nations League model, recency weighting, Over 1.5 and expected goals, correct-score model, corners, and a rebuilt match-details panel.
**Written:** 11 November 2026. **Repository:** the PitchProb repo described in its README (Next.js `web/`, FastAPI `pitchprob_app/`, Streamlit app, SQLite database, GitHub Actions refresh).

You are the agent who will implement this. Read the whole brief before touching code.

---

## 0. How to work

1. **Inspect before editing.** I have only seen the README and one screenshot, not the code. File names below come from the README. Where this brief says "verify", open the file and check. If the repo contradicts the brief, the repo is right: change the plan, and say so in your report.
2. **Do not assume data exists.** Every data source below is marked *verified* (I fetched it and checked) or *unverified* (you must check it with a real request before building on it). If a source fails, build the fallback described, never invent numbers.
3. **Show unavailable as unavailable.** If a number cannot be computed for a match, the API returns `available: false` with a short reason and the UI shows a calm empty state.
4. **Work in small steps.** One task (T1, T2, ...) per commit. Run the tests after each. Keep `python -m pytest -q` green.
5. **Never commit secrets.** Do not read or print `.env`. Do not touch the football-data.org token.
6. **Stay in scope.** Section 2 lists what is out of scope. Do not add betting links, accounts, payments, alerts, lineups or injuries.
7. **Finish with the report in section 9.**

---

## 1. Current state

### 1.1 From the README
- Python 3, FastAPI app in `pitchprob_app/`, SQLite file `data/pitchprob.db` with four tables: `matches`, `fixtures`, `predictions`, `grades`.
- CLI (`cli.py`): `load-history`, `sync-fixtures`, `train`, `predict`, `grade`, `init-db`, `check-access`, `check-names`, `evaluate`, `report`, `status`, `teams`, `daily`.
- Model: one Dixon-Coles model per league through the `penaltyblog` library, forecasts for Home/Draw/Away, Over 2.5 and Both Teams to Score. The Champions League uses a bundled model file `models/CL.pkl`, with no historical-results source.
- Data: results from football-data.co.uk (through penaltyblog), fixtures from the football-data.org free API.
- Front end: Next.js and TypeScript in `web/` reading the FastAPI service. The Next.js server makes all API calls. A legacy Streamlit page renders `templates/index.html`.
- Automation: `.github/workflows/daily-model-refresh.yml` runs daily at 03:23 UTC, refreshes data, retrains, predicts, grades, and **commits the database and model files to the `pitch` branch**.
- The README states that walk-forward backtest forecasts, corner probabilities and scoreline probabilities are **not persisted** today, so those views say "unavailable".

### 1.2 From the screenshot (desktop, dark theme, Thursday 12 Nov 2026 selected)
- Left sidebar: wordmark, collapse button, nav items Matches, Results, Insights with glyph-style icons.
- Top bar: small "PitchProb" title with the line "Statistical forecasts. A clear record.", "Times in UTC", a theme toggle (moon).
- Page: large "Matches" heading, a date strip (arrows, then "Tomorrow Nov 12", Fri Nov 13 ... Wed Nov 18), league chips with crest, name and a count (all showing 0), "Fixtures" section, empty state "No matches on this day. Try tomorrow to see the next fixtures." with a button "Show tomorrow's matches", and a right panel "Match details: Select a fixture to see its match details here."
- Footer: "Times in UTC. Forecasts are statistical estimates, not betting advice. 18+ only."

### 1.3 Problems visible in the screenshot (fix these as part of T10)
1. The empty state tells the user to "try tomorrow" and offers "Show tomorrow's matches" while **tomorrow is already selected**. It should jump to the **next date that has matches**.
2. The date strip has no "Today" and "Tomorrow Nov 12" wraps onto two lines. Chips must never wrap.
3. The first league chip ("All") is truncated to "A..." and its count is hidden.
4. The league chips show the count for the selected day only. Today every league is 0 because domestic leagues are on an international break (the UEFA Nations League window), so the page looks broken. The Nations League chip does not exist yet.
5. Nav icons look like text glyphs. Use real SVG icons.
6. "Matches" is repeated (sidebar and a very large page heading), pushing content down.
7. The right "Match details" panel is empty until a fixture is selected, and nothing says how it behaves on a phone.

### 1.4 Why the page is empty right now (verified)
The 2026/27 UEFA Nations League league phase has Matchday 5 on 12 to 14 November and Matchday 6 on 15 to 17 November 2026 (UEFA's published fixture list and press coverage). Domestic leagues are paused. The app has no Nations League data, so it shows nothing.

---

## 2. Goals and non-goals

### Goals
| ID | Goal |
|---|---|
| G1 | Add **UEFA Nations League** as a competition: train a model on national-team results and forecast its fixtures |
| G2 | Make predictions rely **mostly on the last two years** (for the Nations League model and the club models) |
| G3 | Add **Over 1.5 goals** and **expected goals** (each team and total) |
| G4 | Add a **correct-score model**: most likely scores and a score table |
| G5 | Add **expected corners** for club leagues |
| G6 | Add **average corners for the current season** (all of a team's matches) and **head-to-head** (previous meetings), shown **separately** |
| G7 | Rebuild the **Match details** component so all of this is organised in tabs |
| G8 | Fix the Matches page problems in section 1.3 |

### Out of scope (held for later: do not build)
Lineups, injuries, xG from a data provider, coach ratings, handicap, cards, accounts, payments, alerts, odds or any betting feature, new paid data sources.

---

## 3. Data sources

| Need | Source | Status | Notes |
|---|---|---|---|
| Club results, shots, corners | football-data.co.uk through `penaltyblog.scrapers.FootballData` | Corner columns **verified by name**: after penaltyblog's snake-case conversion the CSV columns HC, AC, HS, AS, HST, AST become `hc`, `ac`, `hs`, `as`, `hst`, `ast` (checked with penaltyblog's own `to_snake_case`). **Unverified** that the downloaded tables contain them for every season: check | `as` is a Python keyword, so read it with `row["as"]` or `df["as"]`, never `row.as` |
| National-team results | `https://raw.githubusercontent.com/martj42/international_results/master/results.csv` | **Verified** on 11 Nov 2026: 49,940 matches, 1872 to 6 Oct 2026, columns `date, home_team, away_team, home_score, away_score, tournament, city, country, neutral`; Nations League rows use exactly `UEFA Nations League`; CC0 per a third-party article (check the repo's own licence text) | **No upcoming fixtures in this file**: the latest row is 2026-10-06 and no row lacks a score. Do not rely on it for fixtures. Team names include `Czech Republic` and `Turkey` (not Czechia or Türkiye) |
| Nations League upcoming fixtures | Unknown | **Unverified, you must probe** | See T2: try the football-data.org competition list first, then a manual CSV (reader provided in Appendix A) |
| Corners for Nations League or Champions League | None found | **No verified free source** | Show corners as unavailable for those competitions |

**Probe order for Nations League fixtures (T2):**
1. Call `GET https://api.football-data.org/v4/competitions` with the existing token. Print every code and name. If a UEFA Nations League code is listed and its matches endpoint returns fixtures for 12 to 17 Nov 2026, use it exactly like the other competitions. (I found no evidence that the free plan includes it; check.)
2. Otherwise use a manual file `data/nations_league_fixtures.csv` (format and reader in Appendix A). UEFA publishes the full list on uefa.com; a person can copy it into the file. Validate every team name against the model's names and print a clear error for any mismatch.
3. Record which route you used in the report.

---

## 4. Model tasks

### T1. Recency: "mostly the last two years" (G2)
**What the user asked:** predictions should rely mostly on the last two years.

**Do:**
1. Make two settings in `config.py`: `TRAIN_WINDOW_DAYS` and `XI`. New defaults: **1095 days** and **0.0019** (the time-decay rate in `penaltyblog.models.dixon_coles_weights`; a match's weight halves roughly every 365 days). Apply to club models and the Nations League model.
2. Add a function that prints, at train time, **the share of total training weight that comes from the last 730 days** (reference: `recent_weight_share` in Appendix A). Target: at least 70%.
3. Add a command `python cli.py compare-recency` that runs the walk-forward backtest for a small grid (windows 730, 1095, 1460 days; XI 0.001, 0.0019, 0.003) and prints one table per competition with log loss and ranked probability score. **Do not switch defaults automatically.** Print the table and let the user decide.
4. For clubs, if the new default is worse than the old one (1500 days, XI 0.001) by more than 0.01 log loss on your backtest, still apply the user's choice but say so prominently in the report.

**Evidence I measured for the Nations League** (my own walk-forward test on the real file, 288 Nations League matches, Sep 2024 to Oct 2026): see Appendix B. Strict two-year windows are slightly worse on every market than longer windows with decay, but the differences are small relative to the sample size. The default above puts 87% of the weight on the last two years.

### T2. UEFA Nations League model (G1)
1. **Data.** Create a table `intl_matches(date, home_team, away_team, home_score, away_score, tournament, neutral)` with primary key `(date, home_team, away_team)`. Add `load-international` to `cli.py` that downloads the CSV, drops rows without a score, and upserts. Add it to `daily` and to the GitHub Actions workflow. Keep it separate from the club `matches` table (club rows are keyed by league and season; national rows are not).
2. **Competition entry.** Add a competition to `LEAGUES` (or the equivalent) with code `UNL`, name `UEFA Nations League`, and a flag that it is a national-team competition. Do not break the Champions League entry.
3. **Training rows** (reference `training_rows` in Appendix A): matches before the cut-off date that involve **at least one UEFA team** (UEFA teams = every team that appears in a `UEFA Nations League` row), inside `TRAIN_WINDOW_DAYS`. A **neutral-venue** match has no real home side, so enter it twice, once from each side, each at half weight. Friendlies and qualifiers are included (they link the teams together).
4. **Fitting and prediction** (reference `fit_international`, `predict_match`): fit one `DixonColesGoalModel` with the weights above. Predict from the fitted strengths with the helper in Appendix A, not from `model.predict`, because the library raises an error for very lopsided fixtures (for example Spain v San Marino) and the helper handles them. The helper limits each team's expected goals to between 0.15 and 3.5. Without that limit the model produced 12 goals for Spain v San Marino.
5. **Neutral venue at prediction time:** average the two orderings (helper does this).
6. **Unknown teams:** a team with no training matches raises `ValueError`; return "No forecast (not enough data)" and do not guess.
7. **Fixtures:** per section 3. Map team names with the same alias mechanism the club side uses (`check-names` must also list unmatched national-team names).
8. **Grading.** Pair a Nations League forecast with its result by **home team, away team and kickoff date within one day** (not by season). Grade Home/Draw/Away, Over 1.5, Over 2.5, Both Teams To Score and the correct score.
9. **Saved model:** `models/UNL.pkl` plus the training cut-off date.

### T3. Over 1.5 and expected goals (G3)
Compute from the scoreline table (reference `summarize_grid`): `exp_home`, `exp_away`, `exp_total`, and Over for the lines 0.5, 1.5, 2.5, 3.5, 4.5, plus Both Teams To Score. Apply to **all** competitions, not only the Nations League. Persist in the prediction row (JSON column is fine) and return in the API.

### T4. Correct-score model (G4)
1. Persist for every forecast: the **top 10 scores** with probabilities, the **7 by 7 table** (0 to 6 goals per side) and `grid_other` (the probability of every score outside that table). `summarize_grid` already returns these.
2. This is the same Dixon-Coles scoreline table used for the other markets. "Correct score model" here means it is a first-class, validated, displayed market, with its own metrics (T6).
3. Metrics to record in the backtest: the average of `-log(probability given to the score that happened)` against a baseline of overall score frequencies, and how often the exact score was in the top 3.

### T5. Corners (G5, G6)
**Club leagues only.** Football-data.co.uk has no corners for the Champions League or national teams, so for those competitions the API returns `corners: { available: false, reason: "No corner data for this competition" }`.

1. **Store** home and away corners (and, if cheap, shots and shots on target) when loading club history. Add nullable columns `home_corners`, `away_corners` to `matches` with a migration that does not lose data. Print how many loaded rows have corners.
2. **Expected corners and lines.** Train one Poisson model per league on corners with `penaltyblog.models.PoissonGoalsModel`, same time-decay weights, grid up to 30 corners (`model.predict(home, away, max_goals=30).grid`). Persist: expected corners for each team and total; probability of Over for **total lines 7.5, 8.5, 9.5, 10.5, 11.5** and for **each team's lines 2.5, 3.5, 4.5, 5.5, 6.5**.
3. **Averages, kept separate** (reference `corner_stats.py`):
   - **This season**: for each team, all its matches this season (home and away) played before the fixture: matches counted, corners for, corners against, total per match.
   - **Head-to-head**: the last 5 meetings of the two teams (any season, either ground) with corner data: list, each team's corners, total per match.
   - The API returns these as two separate objects and the UI shows them as two separate cards. Never combine them into one number.
4. **Validation** (T6): for corners, compare the model's log loss for "total over 9.5" and "each team over 4.5" with the constant baseline (overall frequency in the training data). If it does not beat the baseline, mark corners `experimental`.

### T6. Persist the backtest and validate each market (supports G3 to G5)
1. Create a table `backtest` that stores, for each past match, the forecast the model would have made **using only data before that match** (walk-forward; refit every 28 days): competition, date, teams, 1X2 probabilities, expected goals, Over lines, BTTS, the top scores, the probability given to the actual score, and for clubs the corner probabilities. Use the three most recent completed seasons for clubs, and Sep 2024 onward for the Nations League.
2. Create `market_validation(competition, market, n, model_loss, baseline_loss, status, computed_at)`. Markets: `1x2`, `over15`, `over25`, `btts`, `correct_score`, `corners_total`. Rule: `status = "validated"` if `n >= 200` and `model_loss < baseline_loss`; `"experimental"` if `n >= 30` and not validated; otherwise `"unavailable"`.
3. The API sends `status` with every market and the UI shows a small badge. **Do not hide a market that failed; label it.**
4. Add `python cli.py backtest` and call it from the daily workflow only when the model has changed (to keep the workflow fast).

**What I measured for the Nations League (Appendix B):** 1X2, Over 2.5, BTTS (slightly) and correct score beat their baselines. **Over 1.5 did not clearly beat the constant baseline** (a tie). Expect the Over 1.5 badge to read "experimental" for the Nations League until more matches exist. For clubs I could not test; your backtest decides.

### T7. Database size and the daily commit (scaling guard)
The workflow commits the SQLite file and model files every day. Binary files do not compress between commits, so history grows by roughly the file size each day.
1. Before and after this work, print `ls -l data/pitchprob.db` and `git count-objects -vH`, and put the numbers in the report.
2. Keep additions compact: JSON text, scoreline table rounded to 5 decimals (49 numbers, a few hundred bytes), backtest limited to the last three seasons.
3. If the database exceeds **25 MB**, or `size-pack` grows by more than **10 MB per week**, stop and report with a recommendation (for example publish the database as a release asset or workflow artifact, or commit it weekly). Do not add Redis, queues or other infrastructure: the app has about three users.

### T8. Data checks and failure behaviour
The daily workflow must fail loudly (as it does now) if the international CSV cannot be downloaded or has fewer rows than yesterday's. If Nations League fixtures cannot be fetched, keep the previous ones and show "Fixtures updated N hours ago" instead of an empty page.

---

## 5. API contract

Percentages are fractions between 0 and 1. All times UTC. Add or extend these endpoints (keep existing ones working).

**`GET /api/dates?from=YYYY-MM-DD&days=14`** returns `[{ "date": "2026-11-12", "total": 8, "by_competition": { "UNL": 8 } }]`. Used by the date strip, the league chip counts and the "next date with matches" logic.

**`GET /api/competitions`** returns `[{ "code": "UNL", "name": "UEFA Nations League", "kind": "national", "emblem_url": null }]`.

**`GET /api/matches?date=...&competition=...`**: existing list, plus `competition: {code, name}` on every row and `forecast.exp_total`, `forecast.over15`.

**`GET /api/matches/{id}`** returns the details object used by the Match details component:

```json
{
  "id": 7001,
  "competition": { "code": "UNL", "name": "UEFA Nations League", "stage": "League phase, Group A3" },
  "kickoff_utc": "2026-11-12T19:45:00Z",
  "home": { "name": "England", "badge_url": null },
  "away": { "name": "Croatia", "badge_url": null },
  "neutral": false,
  "forecast": {
    "p_home": 0.78, "p_draw": 0.14, "p_away": 0.08,
    "pick": "H", "lead_points": 64,
    "model": "dixon_coles", "trained_through": "2026-10-06"
  },
  "goals": {
    "exp_home": 3.11, "exp_away": 1.01, "exp_total": 4.12,
    "over": { "0.5": 0.99, "1.5": 0.93, "2.5": 0.78, "3.5": 0.55, "4.5": 0.32 },
    "btts": 0.62
  },
  "correct_score": {
    "top": [ { "score": "3-1", "p": 0.082 } ],
    "grid": [[0.003, 0.004]],
    "grid_note": "7 by 7 table: row = home goals 0 to 6, column = away goals 0 to 6",
    "grid_other": 0.003
  },
  "corners": { "available": false, "reason": "No corner data for this competition" },
  "validation": {
    "1x2":           { "status": "validated",    "n": 288, "model_loss": 0.885, "baseline_loss": 1.083 },
    "over15":        { "status": "experimental", "n": 288, "model_loss": 0.588, "baseline_loss": 0.587 },
    "over25":        { "status": "validated",    "n": 288, "model_loss": 0.685, "baseline_loss": 0.694 },
    "btts":          { "status": "validated",    "n": 288, "model_loss": 0.688, "baseline_loss": 0.691 },
    "correct_score": { "status": "validated",    "n": 288, "model_loss": 2.77,  "baseline_loss": 3.02 }
  },
  "flags": [],
  "result": null
}
```
(The numbers above are illustrations of the shape; the 78% and 3.11 come from one real forecast I ran, not a promise.)

For a club match the `corners` object is:

```json
"corners": {
  "available": true,
  "expected": { "home": 5.8, "away": 4.6, "total": 10.4 },
  "total_over": { "7.5": 0.82, "8.5": 0.71, "9.5": 0.58, "10.5": 0.44, "11.5": 0.31 },
  "team_over": { "home": { "2.5": 0.95, "3.5": 0.86, "4.5": 0.7, "5.5": 0.52, "6.5": 0.34 },
                 "away": { "2.5": 0.9,  "3.5": 0.78, "4.5": 0.58, "5.5": 0.4,  "6.5": 0.24 } },
  "season_average": {
    "home_team": { "matches": 11, "for": 6.3, "against": 4.1, "total": 10.4 },
    "away_team": { "matches": 11, "for": 4.8, "against": 5.2, "total": 10.0 }
  },
  "h2h": { "meetings": 4, "home_team_for": 6.0, "away_team_for": 4.5, "total": 10.5,
           "list": [ { "date": "2026-02-01", "home": "Chelsea", "away": "Arsenal", "corners": "4-6" } ] },
  "validation": { "status": "experimental", "n": 1100, "model_loss": 0.68, "baseline_loss": 0.69 }
}
```

When `result` is not null (after full time) it holds `{ "home_goals", "away_goals", "outcome", "pick_hit", "score_probability" }` so the UI can show forecast against result.

Add tests that check the **shape** of these responses against a fixture database and that `available: false` is returned (not an error) when corner data is missing.

---

## 6. Tests (T9)

Add tests to `tests/` (the README says the suite uses synthetic data and no live calls; keep that). Adapt the import paths of the reference modules to wherever you place them.

**Required:**
1. Scoreline summary: from a known Poisson table, expected goals, Over lines (monotonic), BTTS, top scores and the 7 by 7 table sum with `grid_other` to 1 (reference test in Appendix A).
2. National training rows: no row on or after the cut-off date; non-UEFA matches excluded; a neutral match entered twice at weight 0.5.
3. `recent_weight_share` is a fraction and grows as XI grows.
4. Prediction: probabilities sum to 1; a neutral fixture is symmetric (`p_home(A,B) == p_away(B,A)`); an unknown team raises `ValueError`; a lopsided fixture (very strong v very weak) does not raise and keeps expected goals at or below 3.5.
5. Corner averages by hand (reference test), including ignoring rows without corners and rows after the fixture date.
6. Manual fixtures reader rejects unknown teams and bad dates with line numbers (reference test).
7. Database migration: open a database created by the **old** schema, run `init-db`, confirm old rows survive and new columns exist.
8. Grading: a Nations League forecast pairs with its result by teams and date (within one day), and grades Over 1.5 and the correct score.
9. API shape tests for `/api/dates`, `/api/matches/{id}` (club and national), including `available: false` for corners.

**Optional real-data tests** (skip automatically when the file is missing): download `results.csv` to `tests/data/international_results_snapshot.csv` and run the two real-data tests in Appendix A. Do not commit the 3.7 MB file unless the user agrees.

**Front end:** `npm run build`, TypeScript type-check and lint must pass. If Playwright or a similar tool is already in the repo, take screenshots at 375, 768 and 1280 px of the Matches page and of the Match details tabs for a club match and a Nations League match.

---

## 7. UI/UX (T10)

**Principles** (distilled from the design guidance used to write this brief):
- Calm, precise, readable. One accent colour. Reserve green and red for right and wrong results, never for decoration.
- Keep the existing visual identity unless it conflicts with the rules here. If a design prompt file exists in the repo, follow it.
- Use the UI approach already in `web/` (check `package.json`). If it already uses Tailwind with shadcn/ui components, use those (Tabs, Accordion, Tooltip, Skeleton, Badge). If not, use semantic HTML with the WAI-ARIA tabs pattern and CSS variables. Do not add a UI library or chart library for this work.
- Accessibility: text contrast at least 4.5:1 and 3:1 for graphics in both themes; visible focus ring; touch targets at least 44 by 44 px; full keyboard use; never colour alone (use an icon and a word); respect `prefers-reduced-motion`; numbers in tabular figures.
- Responsive at 375, 768, 1024 and 1440 px with no horizontal scrolling, except the date strip and league chips.
- Loading skeletons with the same height as the real content, an empty state with one action, an error state in plain words with a Retry button. No emoji as icons: use one SVG icon set consistently.
- Draw the heat map and bars with inline SVG or CSS. No chart library.
- Avoid: ALL CAPS tracked small labels above headings, gradients, glass effects, nested cards inside cards, decorative illustrations.

### 7.1 Matches page fixes (G8)
1. **Default date.** On load, select today if it has matches, otherwise the **next date that has matches** (use `GET /api/dates`). Tell the user why ("Next matches: Thursday 12 November").
2. **Empty state.** If the selected date has no matches, show a single line and a button **"Go to Thursday 12 November"** (the real next date with matches). If there are no matches in the next 14 days, say so.
3. **Date strip.** Include Today. Labels never wrap: two lines by design ("Thu" above "12 Nov"), fixed width, horizontally scrollable, arrows at both ends. Mark days that have matches with a small dot; days without matches are still selectable but muted.
4. **League chips.** Add **UEFA Nations League**. Each chip shows the competition crest or initials badge, the full name (truncate the **name**, never the count) and the count for the **selected date**. "All" is never truncated. A chip with 0 matches is muted, not hidden.
5. **Page heading.** Remove the second, very large "Matches" heading; the sidebar already says where you are. Keep a small page title and "Times in UTC".
6. **Navigation icons:** real SVG icons for Matches, Results and Insights; the collapse button has an accessible label.
7. **National-team rows.** Show the national flag or an initials badge, the team names, kickoff time, and the probability bar. No crest is required.

### 7.2 Match details component (G7)
This is the core of the task. All the new numbers live here, organised and never scattered.

**Placement**
- Desktop (1024 px and up): the right pane, sticky, scrolls inside itself, about 440 to 520 px wide. Selecting a row fills it without leaving the list. Initial state: "Select a fixture to see its match details here." plus the date of the next kickoff.
- Phone and tablet: tapping a row opens the same component full screen on its own route (for example `/match/[id]`) with a back arrow. Deep links work. The selected tab is stored in the URL (`?tab=`).

**Structure (top to bottom)**
```
┌──────────────────────────────────────────────┐
│ ‹  UEFA Nations League · Group A3            │  header (sticky)
│    [badge] England   19:45 UTC   Croatia [badge] │
│    Forecast vs result strip (after full time)│
├──────────────────────────────────────────────┤
│ Overview | Goals | Correct score | Corners   │  tabs (sticky under header)
├──────────────────────────────────────────────┤
│ tab content                                  │
└──────────────────────────────────────────────┘
```

**Header.** Competition and stage, kickoff in UTC, both teams with badges. After full time, show the final score and a **Forecast vs result** strip: the model's pick and probability on the left, the real result and a hit or miss badge on the right (icon plus word).

**Tab: Overview**
- The three-segment **probability bar** (Home, Draw, Away): the model's pick filled with the accent colour, the others muted; after full time a small marker on the outcome that happened. The bar has an `aria-label` that reads the three numbers.
- One plain-language sentence: "The model leans England, 78% against 8% for Croatia (a 70-point lead)." Use `lead_points`.
- Key figures row: **Expected goals** (home, away, total), **Over 1.5**, **Over 2.5**, **Both teams to score**, each with its validation badge (section 7.4).
- Context flags (for example a Champions League match within 3 days) as small neutral chips.

**Tab: Goals**
- Expected goals as two large numbers with the total between them.
- **Over/under ladder**: rows for 0.5, 1.5, 2.5, 3.5, 4.5 goals, each with the Over percentage as a thin bar and the Under percentage as text. Highlight 1.5 and 2.5.
- Both teams to score as a thin bar.
- A one-line caption: "From the model's scoreline probabilities."

**Tab: Correct score**
- **Most likely scores**: top 5 as a ranked list with percentages and thin bars.
- **Score table**: a 7 by 7 grid, rows = home goals, columns = away goals, cell shade from one hue (light to strong by probability), the three most likely cells outlined and labelled with their percentage. Provide an accessible `<table>` alternative with a caption. Under it: "Other scores: 0.3%" from `grid_other`.
- The validation badge for `correct_score`.
- A caption: "No score is likely: even the top one is below 20%." Compute the claim from the data (if the top score is 20% or more, do not show the caption).

**Tab: Corners**
- If `corners.available` is false: one calm empty state with the `reason`. Do not show zeros.
- Otherwise, in this order:
  1. **Expected corners**: home, away, total as three numbers.
  2. **Totals**: chips or rows for Over 7.5, 8.5, 9.5, 10.5, 11.5 with percentages.
  3. **Each team**: Over 2.5 to 6.5 for the home team and for the away team, side by side.
  4. **Two separate cards, clearly titled and visually distinct:**
     - **"This season: all matches"**: for each team: matches counted, corners for, corners against, total per match.
     - **"Head-to-head: last 5 meetings"**: the meetings listed (date, ground, corners), each team's average, total per match. If there are no meetings, say "No earlier meetings with corner data." Never merge this card with the season card.
  5. The corners validation badge.

**Optional tab: Form & H2H.** Add it only if the existing API already provides form and head-to-head goals data. Do not invent anything.

### 7.3 States
Loading: skeleton for header, bar, and a tab body. Error: "Could not load this match" with a Retry button. A tab whose data is missing explains why in one sentence. A match with no forecast shows the note ("Team name not matched yet", "No forecast (not enough data)") and no tabs.

### 7.4 Validation badges
Small, text plus icon, tooltip on hover and focus with the sentence from the API data: "Tested on 288 past matches: model 0.885 against 1.083 for no model (lower is better)."
- `validated`: neutral-positive style, label "Tested".
- `experimental`: amber, label "Not yet proven".
- `unavailable`: muted, label "Not tested".
Never use the words "guaranteed", "sure", "tip" or "lock". Keep the footer line on every page: "Forecasts are statistical estimates, not betting advice. 18+ only."

---

## 8. Acceptance checklist

**Model and data**
- [ ] `python cli.py load-international` loads the CSV; `status` shows the national match count and the latest date.
- [ ] Nations League training prints the training-row count and **the share of weight on the last two years (at least 70%)**.
- [ ] A forecast exists for every Nations League fixture whose two teams are in the training data; the others say why not.
- [ ] Nations League fixtures come from a probed source or the manual CSV, and the report says which.
- [ ] Over 1.5, expected goals, correct score (top scores and table) are stored and returned for **every** competition.
- [ ] Corners are stored, modelled and returned for club leagues; Nations League and Champions League return `available: false` with a reason.
- [ ] Season corner averages and head-to-head corner averages are separate objects.
- [ ] `backtest` fills `backtest` and `market_validation`; statuses follow the rule in T6.
- [ ] `compare-recency` prints the comparison table and changes nothing.
- [ ] Old databases migrate without data loss.
- [ ] Database size and `git count-objects -vH` reported before and after.

**API**
- [ ] `/api/dates`, `/api/competitions`, `/api/matches`, `/api/matches/{id}` match section 5.

**UI**
- [ ] On 11 Nov 2026 the Matches page opens on Thursday 12 Nov with the Nations League fixtures, not an empty page.
- [ ] Date strip includes Today, never wraps. League chips show full names, counts, and a Nations League chip.
- [ ] Match details has Overview, Goals, Correct score and Corners tabs with the content in section 7.2; tab is in the URL.
- [ ] Season and head-to-head corner averages look different and are never merged.
- [ ] Light and dark themes pass contrast; keyboard use works; `prefers-reduced-motion` respected.
- [ ] 375, 768, 1280 px screenshots show no horizontal scroll except the strip and chips.
- [ ] `python -m pytest -q`, `npm run build`, type-check and lint all pass.

**Docs**
- [ ] README updated: new commands, the Nations League data source and licence note, the `APPP_` typo fixed, the corners limitation.

---

## 9. Report back (your final message)

1. What you changed, grouped by T1 to T10, with file names.
2. Which Nations League fixtures route you used and what you found in the probes (print the competition codes you saw).
3. The `compare-recency` table for each competition and the weight-on-last-two-years numbers.
4. The `market_validation` table (competition, market, n, model loss, baseline loss, status).
5. Database size and git size before and after.
6. Anything in this brief that was wrong or unverified, and what you did.
7. Anything you chose not to do and why.
8. Test results.

---

## Appendix A: Reference code (tested)

These modules were run and tested by me against simulated data and, for the national-team parts, against the real results file downloaded on 11 November 2026 (8 tests passing: Python 3.12.3, penaltyblog 1.13.1, pandas 3.1). They have no dependency on the rest of the repo. Place them next to the existing modules and adapt imports.

### `scoreline.py`

```python
"""Everything that can be read from a table of scoreline probabilities (row = home goals, column = away goals)."""
import numpy as np

GOAL_LINES = (0.5, 1.5, 2.5, 3.5, 4.5)
UI_GRID_GOALS = 6          # the correct-score heat map shows 0..6 goals per side


def normalize(grid) -> np.ndarray:
    grid = np.asarray(grid, dtype=float)
    return grid / grid.sum()


def summarize_grid(grid, top_n: int = 10) -> dict:
    """Goal markets, expected goals and correct-score numbers from one scoreline table."""
    g = normalize(grid)
    n = g.shape[0]
    i, j = np.indices(g.shape)
    total = i + j
    k = np.arange(n)
    ui = UI_GRID_GOALS + 1
    order = np.argsort(g, axis=None)[::-1][:top_n]
    return {
        "exp_home": float((g.sum(axis=1) * k).sum()),
        "exp_away": float((g.sum(axis=0) * k).sum()),
        "exp_total": float((g * total).sum()),
        "over": {f"{line:g}": float(g[total > line].sum()) for line in GOAL_LINES},
        "btts": float(g[(i > 0) & (j > 0)].sum()),
        "top_scores": [{"score": f"{a}-{b}", "p": float(g[a, b])} for a, b in (divmod(int(x), n) for x in order)],
        "grid": [[round(float(v), 5) for v in row[:ui]] for row in g[:ui]],       # 0..6 by 0..6
        "grid_other": float(1 - g[:ui, :ui].sum()),                                 # every score outside that table
    }
```

### `international.py`

```python
"""National-team (UEFA Nations League) model: data loading, training rows, fitting and prediction."""
import math
import numpy as np
import pandas as pd
import penaltyblog as pb
from scoreline import summarize_grid

RESULTS_URL = "https://raw.githubusercontent.com/martj42/international_results/master/results.csv"
NL_NAME = "UEFA Nations League"       # exact value of the 'tournament' column (checked in the 11 Nov 2026 file)
WINDOW_DAYS = 1095                    # three years of matches ...
XI = 0.0019                           # ... weighted so a match loses half its weight every ~365 days
MIN_TRAIN_ROWS = 300
MAX_GOALS = 10
LAMBDA_MIN, LAMBDA_MAX = 0.15, 3.5   # allowed range of expected goals per team


def clean_results(df: pd.DataFrame) -> pd.DataFrame:
    """Columns: date, home_team, away_team, home_score, away_score, tournament, city, country, neutral."""
    out = df.copy()
    out["date"] = pd.to_datetime(out["date"])
    out["neutral"] = out["neutral"].astype(str).str.upper().eq("TRUE")
    out = out.dropna(subset=["home_score", "away_score"])          # a row without a score is a fixture, not a result
    out["home_score"], out["away_score"] = out["home_score"].astype(int), out["away_score"].astype(int)
    return out.sort_values("date", kind="stable").reset_index(drop=True)


def load_results(url: str = RESULTS_URL) -> pd.DataFrame:
    return clean_results(pd.read_csv(url))


def uefa_teams(df: pd.DataFrame) -> set[str]:
    nl = df[df["tournament"] == NL_NAME]
    return set(nl["home_team"]) | set(nl["away_team"])


def training_rows(df: pd.DataFrame, as_of, uefa: set[str], window_days: int = WINDOW_DAYS) -> pd.DataFrame:
    """Matches before `as_of` (so no result can leak in) that involve at least one UEFA team.
    A neutral-venue match has no real home side, so it is entered twice, once from each side, at half weight."""
    as_of = pd.Timestamp(as_of)
    w = df[(df["date"] >= as_of - pd.Timedelta(days=window_days)) & (df["date"] < as_of)]
    w = w[w["home_team"].isin(uefa) | w["away_team"].isin(uefa)]
    rows = w[["date", "home_team", "away_team", "home_score", "away_score", "neutral"]].copy()
    rows["weight"] = np.where(rows["neutral"], 0.5, 1.0)
    flipped = rows[rows["neutral"]].rename(columns={"home_team": "away_team", "away_team": "home_team",
                                                    "home_score": "away_score", "away_score": "home_score"})
    return pd.concat([rows, flipped], ignore_index=True)


def fit_international(rows: pd.DataFrame, xi: float = XI):
    if len(rows) < MIN_TRAIN_ROWS:
        raise ValueError(f"Only {len(rows)} training rows (need {MIN_TRAIN_ROWS}).")
    weights = pb.models.dixon_coles_weights(rows["date"], xi=xi) * rows["weight"].to_numpy()
    model = pb.models.DixonColesGoalModel(rows["home_score"].to_numpy(), rows["away_score"].to_numpy(),
                                          rows["home_team"].to_numpy(), rows["away_team"].to_numpy(), weights=weights)
    model.fit()
    return model


def recent_weight_share(rows: pd.DataFrame, as_of, xi: float = XI, years: int = 2) -> float:
    """What share of the total training weight comes from the last `years` years? (The 'mostly the last two years' check.)"""
    weights = pb.models.dixon_coles_weights(rows["date"], xi=xi) * rows["weight"].to_numpy()
    recent = (rows["date"] >= pd.Timestamp(as_of) - pd.Timedelta(days=365 * years)).to_numpy()
    return float(weights[recent].sum() / weights.sum())


def team_rates(model, home: str, away: str) -> tuple[float, float]:
    """Expected goals for the home and away team, read from the fitted strengths (same formula the library uses)."""
    p = model.params
    try:
        lam = math.exp(p["home_advantage"] + p[f"attack_{home}"] + p[f"defence_{away}"])
        mu = math.exp(p[f"attack_{away}"] + p[f"defence_{home}"])
    except KeyError as missing:
        raise ValueError(f"Team not in the training data: {missing}") from None
    return lam, mu


def dc_grid(lam: float, mu: float, rho: float, n: int = MAX_GOALS) -> np.ndarray:
    """Scoreline probabilities: independent Poisson goals plus the Dixon-Coles low-score correction.
    The correction is skipped if it would produce a negative probability (it can for very lopsided fixtures)."""
    pm = lambda k, m: math.exp(-m) * m ** k / math.factorial(k)
    grid = np.array([[pm(i, lam) * pm(j, mu) for j in range(n)] for i in range(n)])
    tau = {(0, 0): 1 - lam * mu * rho, (0, 1): 1 + lam * rho, (1, 0): 1 + mu * rho, (1, 1): 1 - rho}
    if min(tau.values()) > 0:
        for (i, j), t in tau.items():
            grid[i, j] *= t
    return grid / grid.sum()


def predict_match(model, home: str, away: str, neutral: bool = False) -> dict:
    """Raises ValueError for a team the model has not seen. At a neutral venue the two orderings are averaged.
    Expected goals are limited to [LAMBDA_MIN, LAMBDA_MAX]: without that the model produced 12 goals for Spain v San Marino."""
    clip = lambda x: min(max(x, LAMBDA_MIN), LAMBDA_MAX)
    rho = model.params["rho"]
    lam, mu = team_rates(model, home, away)
    grid = dc_grid(clip(lam), clip(mu), rho)
    if neutral:
        lam2, mu2 = team_rates(model, away, home)
        grid = (grid + dc_grid(clip(lam2), clip(mu2), rho).T) / 2
    i, j = np.indices(grid.shape)
    out = {"p_home": float(grid[i > j].sum()), "p_draw": float(grid[i == j].sum()), "p_away": float(grid[i < j].sum())}
    out.update(summarize_grid(grid))
    return out
```

### `corner_stats.py`

```python
"""Corner averages for the match-details page: this season's matches and head-to-head meetings, kept separate."""
import sqlite3


def _avg(values: list[float]):
    return round(sum(values) / len(values), 2) if values else None


def season_corner_averages(conn: sqlite3.Connection, league: str, season: str, team: str, before_date: str) -> dict:
    """All of the team's matches this season (home and away) that have corner data and were played before the match."""
    rows = conn.execute(
        """SELECT CASE WHEN home = :t THEN home_corners ELSE away_corners END AS corners_for,
                  CASE WHEN home = :t THEN away_corners ELSE home_corners END AS corners_against
           FROM matches
           WHERE league = :l AND season = :s AND (home = :t OR away = :t) AND match_date < :d
             AND home_corners IS NOT NULL AND away_corners IS NOT NULL""",
        {"t": team, "l": league, "s": season, "d": before_date}).fetchall()
    cf, ca = [r[0] for r in rows], [r[1] for r in rows]
    return {"matches": len(rows), "corners_for": _avg(cf), "corners_against": _avg(ca),
            "total_per_match": _avg([a + b for a, b in zip(cf, ca)])}


def h2h_corner_averages(conn: sqlite3.Connection, league: str, home: str, away: str, before_date: str, limit: int = 5) -> dict:
    """The last `limit` meetings of the two teams (any season, either ground) that have corner data."""
    rows = conn.execute(
        """SELECT match_date, home, away, home_corners, away_corners FROM matches
           WHERE league = :l AND match_date < :d AND home_corners IS NOT NULL AND away_corners IS NOT NULL
             AND ((home = :h AND away = :a) OR (home = :a AND away = :h))
           ORDER BY match_date DESC LIMIT :n""",
        {"l": league, "h": home, "a": away, "d": before_date, "n": limit}).fetchall()
    for_home = [r["home_corners"] if r["home"] == home else r["away_corners"] for r in rows]
    for_away = [r["away_corners"] if r["home"] == home else r["home_corners"] for r in rows]
    return {"meetings": len(rows), f"corners_for_home_team": _avg(for_home), "corners_for_away_team": _avg(for_away),
            "total_per_match": _avg([a + b for a, b in zip(for_home, for_away)]),
            "list": [{"date": r["match_date"], "home": r["home"], "away": r["away"],
                      "corners": f"{r['home_corners']}-{r['away_corners']}"} for r in rows]}
```

### `manual_fixtures.py`

```python
"""Reads a hand-made fixtures file for competitions that have no free fixtures API (e.g. UEFA Nations League)."""
import csv
from datetime import datetime, timezone

REQUIRED = ("date_utc", "time_utc", "home", "away")


def read_manual_fixtures(path: str, known_teams: set[str], aliases: dict[str, str] | None = None) -> list[dict]:
    """Columns: date_utc (YYYY-MM-DD), time_utc (HH:MM), home, away, optional group and neutral (TRUE/FALSE).
    Team names are mapped through `aliases` (file name -> model name) and must exist in `known_teams`."""
    aliases, out, problems = aliases or {}, [], []
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        missing = [c for c in REQUIRED if c not in (reader.fieldnames or [])]
        if missing:
            raise ValueError(f"Missing columns: {', '.join(missing)}")
        for line, row in enumerate(reader, start=2):
            home = aliases.get(row["home"].strip(), row["home"].strip())
            away = aliases.get(row["away"].strip(), row["away"].strip())
            for name in (home, away):
                if name not in known_teams:
                    problems.append(f"line {line}: unknown team '{name}'")
            try:
                kickoff = datetime.strptime(f"{row['date_utc'].strip()} {row['time_utc'].strip()}", "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)
            except ValueError:
                problems.append(f"line {line}: bad date or time '{row['date_utc']} {row['time_utc']}'")
                continue
            out.append({"kickoff_utc": kickoff.strftime("%Y-%m-%dT%H:%M:%SZ"), "home": home, "away": away,
                        "group": (row.get("group") or "").strip() or None,
                        "neutral": (row.get("neutral") or "").strip().upper() == "TRUE"})
    if problems:
        raise ValueError("Fixture file problems:\n  " + "\n  ".join(problems))
    return out
```

File format for `data/nations_league_fixtures.csv` (the rows are **illustrative**; copy the real list from uefa.com):

```csv
date_utc,time_utc,home,away,group,neutral
2026-11-12,19:45,England,Croatia,A3,FALSE
2026-11-13,19:45,Scotland,North Macedonia,B1,FALSE
```

Team names must match the names in `intl_matches` after aliases (examples that differ between sources: `Czech Republic` and `Turkey` in the results file; other lists write Czechia and Türkiye). Put name fixes in the same alias file the club side uses (`fd_name,model_name`).

### `tests/test_ref.py`

```python
import math
import sqlite3
import sys
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import corner_stats, international as intl, scoreline  # noqa: E402

SNAPSHOT = ROOT / "tests" / "data" / "international_results_snapshot.csv"   # download results.csv here to run the real-data tests


def poisson_grid(lam, mu, n=15):
    pm = lambda k, m: math.exp(-m) * m ** k / math.factorial(k)
    return np.array([[pm(h, lam) * pm(a, mu) for a in range(n)] for h in range(n)])


def test_scoreline_summary_matches_hand_numbers():
    s = scoreline.summarize_grid(poisson_grid(1.6, 1.1))
    assert s["exp_home"] == pytest.approx(1.6, abs=1e-3) and s["exp_away"] == pytest.approx(1.1, abs=1e-3)
    assert s["exp_total"] == pytest.approx(2.7, abs=1e-3)
    assert s["over"]["2.5"] == pytest.approx(0.506, abs=1e-3)          # same worked example as the earlier guide
    assert s["btts"] == pytest.approx(0.532, abs=1e-3)
    over = [s["over"][k] for k in ("0.5", "1.5", "2.5", "3.5", "4.5")]
    assert over == sorted(over, reverse=True)
    assert s["top_scores"][0]["score"] == "1-1" and s["top_scores"][0]["p"] == pytest.approx(0.118, abs=1e-3)
    assert len(s["grid"]) == 7 and len(s["grid"][0]) == 7
    assert sum(sum(r) for r in s["grid"]) + s["grid_other"] == pytest.approx(1.0, abs=1e-4)


def test_clean_results_drops_fixtures_and_reads_neutral():
    raw = pd.DataFrame({"date": ["2026-10-05", "2026-11-12"], "home_team": ["A", "B"], "away_team": ["C", "D"],
                        "home_score": [1, np.nan], "away_score": [0, np.nan], "tournament": ["X", "UEFA Nations League"],
                        "city": ["", ""], "country": ["", ""], "neutral": ["TRUE", "FALSE"]})
    out = intl.clean_results(raw)
    assert len(out) == 1 and out.loc[0, "neutral"] is True or out.loc[0, "neutral"] == True  # noqa: E712
    assert out["home_score"].dtype.kind == "i"


def small_frame():
    rows = [("2026-01-01", "A", "B", 2, 0, False, "UEFA Nations League"), ("2026-02-01", "B", "C", 1, 1, True, "Friendly"),
            ("2026-03-01", "X", "Y", 3, 3, False, "Friendly"),                     # neither team is a UEFA team
            ("2026-04-01", "C", "A", 0, 1, False, "UEFA Nations League"), ("2026-06-01", "A", "C", 5, 0, False, "Friendly")]
    df = pd.DataFrame(rows, columns=["date", "home_team", "away_team", "home_score", "away_score", "neutral", "tournament"])
    df["date"] = pd.to_datetime(df["date"])
    return df


def test_training_rows_never_see_the_future_and_handle_neutral():
    df = small_frame()
    uefa = intl.uefa_teams(df)
    assert uefa == {"A", "B", "C"}
    rows = intl.training_rows(df, "2026-05-01", uefa)
    assert rows["date"].max() < pd.Timestamp("2026-05-01")             # the 1 June match is excluded
    assert not ((rows.home_team == "X") | (rows.away_team == "X")).any()  # non-UEFA match excluded
    neutral = rows[rows["date"] == "2026-02-01"]
    assert len(neutral) == 2 and (neutral["weight"] == 0.5).all()      # entered from both sides at half weight
    assert set(zip(neutral.home_team, neutral.away_team)) == {("B", "C"), ("C", "B")}


def test_recent_weight_share_is_a_fraction_and_grows_with_decay():
    dates = pd.date_range("2023-11-01", "2026-10-01", freq="14D")
    rows = pd.DataFrame({"date": dates, "weight": 1.0})
    low = intl.recent_weight_share(rows, "2026-10-06", xi=0.0)
    high = intl.recent_weight_share(rows, "2026-10-06", xi=0.003)
    assert 0 < low < high < 1
    assert low == pytest.approx((dates >= pd.Timestamp("2026-10-06") - pd.Timedelta(days=730)).mean(), abs=1e-9)


@pytest.mark.skipif(not SNAPSHOT.exists(), reason="needs the downloaded results file")
def test_real_data_model_is_sane_and_neutral_is_symmetric():
    df = intl.clean_results(pd.read_csv(SNAPSHOT))
    uefa = intl.uefa_teams(df)
    assert len(uefa) == 55                                              # the 55 teams seen in the file at the time
    as_of = "2026-10-07"
    rows = intl.training_rows(df, as_of, uefa)
    assert 1000 < len(rows) < 3000
    share = intl.recent_weight_share(rows, as_of)
    assert 0.70 < share < 0.95                                          # 'mostly the last two years'
    model = intl.fit_international(rows)
    p = intl.predict_match(model, "England", "Croatia")
    assert p["p_home"] + p["p_draw"] + p["p_away"] == pytest.approx(1.0, abs=1e-9)
    assert p["over"]["0.5"] > p["over"]["1.5"] > p["over"]["2.5"] > p["over"]["3.5"]
    assert p["exp_total"] == pytest.approx(p["exp_home"] + p["exp_away"], abs=1e-6)
    a = intl.predict_match(model, "England", "Croatia", neutral=True)
    b = intl.predict_match(model, "Croatia", "England", neutral=True)
    assert a["p_home"] == pytest.approx(b["p_away"], abs=1e-9) and a["p_draw"] == pytest.approx(b["p_draw"], abs=1e-9)
    with pytest.raises(ValueError):
        intl.predict_match(model, "England", "Atlantis")
    # a stronger team is favoured, as a smoke test of the whole fit
    strong = intl.predict_match(model, "Spain", "San Marino")            # the library itself raises an error for this fixture
    assert strong["p_home"] > 0.8 and strong["exp_home"] > strong["exp_away"]
    assert strong["exp_home"] <= 3.6 and strong["p_home"] + strong["p_draw"] + strong["p_away"] == pytest.approx(1.0)
    # for a normal fixture my formula equals the library's own table
    lib = model.predict("Germany", "Netherlands", max_goals=intl.MAX_GOALS).grid
    mine = intl.predict_match(model, "Germany", "Netherlands")
    i, j = np.indices(lib.shape)
    assert mine["p_home"] == pytest.approx(float(lib[i > j].sum() / lib.sum()), abs=1e-9)


@pytest.mark.skipif(not SNAPSHOT.exists(), reason="needs the downloaded results file")
def test_real_data_beats_the_no_model_forecast_over_two_nations_league_windows():
    df = intl.clean_results(pd.read_csv(SNAPSHOT))
    uefa = intl.uefa_teams(df)
    test = df[(df.tournament == intl.NL_NAME) & (df.date >= "2025-03-01")]       # March 2025 knockouts + Sep-Oct 2026
    ll_m, ll_b = [], []
    for _, blk in test.groupby(test.date.dt.to_period("M")):
        start = blk.date.min()
        rows = intl.training_rows(df, start, uefa)
        model = intl.fit_international(rows)
        res = np.where(rows.home_score > rows.away_score, 0, np.where(rows.home_score < rows.away_score, 2, 1))
        base = [(res == k).mean() for k in range(3)]
        for r in blk.itertuples():
            try:
                p = intl.predict_match(model, r.home_team, r.away_team, bool(r.neutral))
            except ValueError:
                continue
            o = 0 if r.home_score > r.away_score else 2 if r.home_score < r.away_score else 1
            ll_m.append(-math.log([p["p_home"], p["p_draw"], p["p_away"]][o])); ll_b.append(-math.log(base[o]))
    assert len(ll_m) > 100
    assert np.mean(ll_m) < np.mean(ll_b) - 0.05


def corner_db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE matches (league TEXT, season TEXT, match_date TEXT, home TEXT, away TEXT, home_corners INTEGER, away_corners INTEGER)")
    rows = [("PL", "2026-2027", "2026-08-20", "Arsenal", "Chelsea", 7, 3), ("PL", "2026-2027", "2026-09-10", "Everton", "Arsenal", 2, 8),
            ("PL", "2026-2027", "2026-09-20", "Arsenal", "Fulham", None, None),                      # no corner data: ignored
            ("PL", "2025-2026", "2026-03-01", "Chelsea", "Arsenal", 4, 6), ("PL", "2024-2025", "2025-04-01", "Arsenal", "Chelsea", 9, 5),
            ("PL", "2026-2027", "2026-11-01", "Arsenal", "Leeds", 10, 1)]                           # after the match date: ignored
    conn.executemany("INSERT INTO matches VALUES (?, ?, ?, ?, ?, ?, ?)", rows)
    return conn


def test_corner_averages_by_hand():
    conn = corner_db()
    s = corner_stats.season_corner_averages(conn, "PL", "2026-2027", "Arsenal", "2026-10-15")
    assert s == {"matches": 2, "corners_for": 7.5, "corners_against": 2.5, "total_per_match": 10.0}   # (7+8)/2, (3+2)/2
    h = corner_stats.h2h_corner_averages(conn, "PL", "Arsenal", "Chelsea", "2026-10-15")
    assert h["meetings"] == 3
    assert h["corners_for_home_team"] == pytest.approx((7 + 6 + 9) / 3, abs=0.01)      # Arsenal's corners, either ground
    assert h["corners_for_away_team"] == pytest.approx((3 + 4 + 5) / 3, abs=0.01)
    assert h["list"][0]["date"] == "2026-08-20"                                          # newest first
    assert corner_stats.season_corner_averages(conn, "PL", "2026-2027", "Nobody", "2026-10-15")["corners_for"] is None


def test_manual_fixtures_reader(tmp_path):
    import manual_fixtures as mf
    f = tmp_path / "f.csv"
    f.write_text("date_utc,time_utc,home,away,group\n2026-11-12,19:45,England,Czechia,A3\n2026-11-13,19:45,Scotland,Nobody,A1\n", encoding="utf-8")
    with pytest.raises(ValueError) as err:
        mf.read_manual_fixtures(str(f), {"England", "Czech Republic", "Scotland"}, {"Czechia": "Czech Republic"})
    assert "unknown team 'Nobody'" in str(err.value) and "line 3" in str(err.value) and "Czechia" not in str(err.value)
    f.write_text("date_utc,time_utc,home,away,group\n2026-11-12,19:45,England,Czechia,A3\n", encoding="utf-8")
    rows = mf.read_manual_fixtures(str(f), {"England", "Czech Republic"}, {"Czechia": "Czech Republic"})
    assert rows == [{"kickoff_utc": "2026-11-12T19:45:00Z", "home": "England", "away": "Czech Republic", "group": "A3", "neutral": False}]
    f.write_text("date,home,away\n", encoding="utf-8")
    with pytest.raises(ValueError, match="Missing columns"):
        mf.read_manual_fixtures(str(f), set())
```

---

## Appendix B: Evidence I measured (so you can check your work against it)

**Test:** walk-forward on the real national-team file (snapshot of 11 Nov 2026, matches up to 6 Oct 2026). For each calendar month, train only on matches before that month and forecast that month's UEFA Nations League matches (Sep 2024 to Oct 2026, **288 matches** with both teams known). Neutral venues entered twice at half weight; matches involving at least one UEFA team; expected goals limited to 0.15 to 3.5. "No-model" and "constant" columns use the training data's own frequencies. Lower numbers are better. Produced with the reference code above.

| Window (days) | xi | Weight on last 2 years | 1X2 log loss (model / no-model) | RPS (model / no-model) | Top pick right | Over 1.5 (model / constant) | Over 2.5 | Both teams score | Correct score -log p (model / frequency) | Exact score in top 3 |
|---|---|---|---|---|---|---|---|---|---|---|
| 730 | 0.0019 | 100% | 0.892 / 1.081 | 0.173 / 0.233 | 59% | 0.593 / 0.588 | 0.691 / 0.694 | 0.694 / 0.692 | 2.79 / 3.03 | 36% |
| 1095 | 0.0019 | 87% | 0.885 / 1.083 | 0.170 / 0.233 | 60% | 0.588 / 0.587 | 0.685 / 0.694 | 0.688 / 0.691 | 2.77 / 3.02 | 35% |
| 1095 | 0.003 | 94% | 0.887 / 1.083 | 0.171 / 0.233 | 59% | 0.597 / 0.587 | 0.693 / 0.694 | 0.691 / 0.691 | 2.78 / 3.02 | 35% |
| 1460 | 0.0019 | 83% | 0.881 / 1.083 | 0.169 / 0.233 | 60% | 0.586 / 0.587 | 0.683 / 0.694 | 0.685 / 0.692 | 2.76 / 3.02 | 36% |
| 1460 | 0.001 | 71% | 0.883 / 1.083 | 0.169 / 0.233 | 61% | 0.581 / 0.587 | 0.679 / 0.694 | 0.682 / 0.692 | 2.76 / 3.02 | 38% |
n = 288

**How to read it**
- The model clearly beats the no-model forecast for Home/Draw/Away (about 0.885 against 1.083 log loss; RPS 0.170 against 0.233).
- Correct score beats the score-frequency baseline (about 2.77 against 3.02), and the exact score is in the model's top 3 about 35% of the time.
- Over 2.5 and Both Teams To Score beat the constant only slightly. **Over 1.5 is a tie** in the default setting (0.588 against 0.587), so mark it `experimental`.
- Longer windows with weaker decay (1460 days, XI 0.001, 71% of weight on the last two years) scored best on every market, by small margins on 288 matches. That is why `compare-recency` exists and why the defaults are exposed in `config.py`. The default requested by the user (1095 days, XI 0.0019, 87% on the last two years) is close behind.
- Calibration check on the same 288 matches (default setting): when the model's top pick had 50 to 60% probability it was right 58% of the time (59 matches); 60 to 70%: 74% (34); 70 to 80%: 84% (31); 80% and over: 91% (23). The forecasts were not over-confident in this test.
- Limits: one competition, 288 matches, my own test code. Re-run it with your repo's backtest.

## Appendix C: Things I could not verify

- Whether football-data.org's free plan lists a Nations League competition.
- Whether the club history downloads contain corner columns for every season and league.
- Any corner data source for national teams or the Champions League.
- Club-league backtest numbers for the new recency defaults (the club data sites were not reachable from my environment).
- The licence text of the results repository (a third-party article says CC0).
