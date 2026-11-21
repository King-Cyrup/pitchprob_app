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