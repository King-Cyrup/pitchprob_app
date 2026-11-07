{
  "project": {
    "name": "PitchProb",
    "one_line": "Probability forecasts for football matches in the top five European leagues, with an honest public record of how the forecasts turned out.",
    "audience": "Football fans who like numbers. Mostly on phones. Three invited testers at first.",
    "platform": "Responsive web (mobile first). Next.js App Router with TypeScript.",
    "tone": "Calm, precise, trustworthy. Forecasts, never tips. No hype words."
  },
  "reference_screenshot": {
    "what_it_is": "The current PitchProb page, desktop width, dark navy theme with neon green accents, showing Champions League fixtures for today (4 Nov), in UTC.",
    "instruction": "If the screenshot is attached, use it to confirm what the page shows. Keep its information and behaviour listed below, and redesign everything visual. Do not copy its colours, spacing or components. The floating 'Manage app' button at the bottom right belongs to the hosting platform, not to the design: ignore it.",
    "keep_from_current_page": [
      "Date selector with Today, Tomorrow and the next dates, plus previous and next arrows",
      "League filter with a match count beside each league (All leagues, Champions League, and the five domestic leagues)",
      "Matches grouped under a league header that shows the number of matches and collapses",
      "Each match shows: kickoff time with the date, a round or square badge with team initials, both team names, each team's win chance as a percentage, the draw chance in the middle",
      "A chevron on each match that expands it for more detail",
      "The label 'Times in UTC'",
      "A one-line description of the product (shorten it and move it out of the way)"
    ],
    "problems_to_fix": [
      "The dark navy with neon green look is generic for a sports data site and feels like a template; the new design must have its own calm identity",
      "ALL CAPS tracked labels (MATCH PROBABILITY INSIGHTS, MATCH DATE, LEAGUES) add noise; use sentence case and quiet headings",
      "The huge title and paragraph push the matches below the fold; fixtures must start immediately under the date strip",
      "The three outcomes are split apart: home bar on the left, draw as small text in the middle, away bar on the right, so the eye cannot compare them at a glance; show them as one three-segment bar",
      "Both teams' bars use the same green, so nothing says which side the model prefers; highlight only the model's pick",
      "'Win chance' is repeated on every row; say it once in a column header or drop it",
      "Date chips are cramped ('Tomorrow' is squeezed) and the left panel uses heavy boxed buttons; use a lighter date strip and chips",
      "Nested panels (league panel, then match panel inside it) make each row heavy; use flat rows separated by a 1px line",
      "Low contrast for the thin bars and grey text on navy; meet 4.5:1 for text and 3:1 for bar segments",
      "Badges are initials in squares that vary in width; use one consistent round badge (initials placeholder until crests exist)"
    ]
  },
  "borrow_from": {
    "livescore_and_flashscore_patterns": [
      "A horizontal date strip at the top (Yesterday, Today, Tomorrow, then dates) that swipes",
      "League chips under it to filter the list",
      "Matches grouped under collapsible league headers",
      "Dense, scannable match rows: kickoff time on the left, teams stacked, key number on the right",
      "Bottom tab bar on phones, left navigation rail on desktop",
      "Tap a row to open a match page with a sticky header and tabs",
      "Clear finished state: the score replaces the kickoff time"
    ],
    "do_better_than_them": [
      "No ads, no banners, no clutter",
      "More whitespace and calmer colour so it feels premium",
      "Probabilities explained in plain words, not just shown"
    ]
  },
  "design_direction": {
    "name": "Quiet scoreboard",
    "personality": [
      "precise",
      "calm",
      "confident",
      "uncluttered"
    ],
    "one_memorable_thing": "The probability bar: three segments for Home, Draw, Away. The outcome the model rates most likely is filled with the accent colour; the other two are muted greys. After the match, a small marker sits on the outcome that really happened, so the bar shows forecast and truth together.",
    "layout_rules": [
      "Left-aligned text. Numbers right-aligned in tabular figures so columns line up.",
      "Separate with space and 1px lines, not heavy shadows.",
      "One accent colour only. Green and red are reserved for right and wrong results.",
      "No gradients, no glass blur, no decorative illustrations, no stock football photos."
    ]
  },
  "tokens": {
    "color": {
      "light": {
        "bg": "#F4F5F7",
        "surface": "#FFFFFF",
        "surface_2": "#ECEEF2",
        "line": "#E2E5EA",
        "ink": "#1C2330",
        "muted": "#5B6577",
        "accent": "#2750E6",
        "accent_soft": "#E6ECFD",
        "hit": "#12804A",
        "miss": "#C93A3A",
        "warn": "#8A5A00"
      },
      "dark": {
        "bg": "#0E1116",
        "surface": "#151A21",
        "surface_2": "#1C222B",
        "line": "#262D38",
        "ink": "#E8ECF2",
        "muted": "#98A2B3",
        "accent": "#7FA2FF",
        "accent_soft": "#1B2540",
        "hit": "#4CC38A",
        "miss": "#FF7B72",
        "warn": "#E3B341"
      },
      "default_theme": "follow the device setting (prefers-color-scheme), with a manual toggle",
      "contrast_checked": "All text pairs listed above are at least 4.5:1 on bg and surface in both themes"
    },
    "type": {
      "family": "Manrope (variable). Install with the npm package @fontsource-variable/manrope. Fallback: system-ui, sans-serif.",
      "numerals": "font-variant-numeric: tabular-nums on every number",
      "scale_px": {
        "caption": 12,
        "body": 15,
        "row_title": 16,
        "section_title": 18,
        "page_title": 24,
        "big_number": 32,
        "hero_number": 44
      },
      "weights": {
        "regular": 450,
        "medium": 550,
        "semibold": 650
      }
    },
    "space_px": [
      4,
      8,
      12,
      16,
      24,
      32,
      48
    ],
    "radius_px": {
      "chip": 999,
      "control": 10,
      "card": 14
    },
    "elevation": "none on lists; 1px line borders; a soft shadow only on the sticky tab bar and open menus",
    "motion": {
      "duration_ms": "150 to 200",
      "easing": "ease-out",
      "allowed": [
        "probability bar widths grow once when first shown",
        "tab content cross-fades",
        "row press feedback"
      ],
      "reduced_motion": "turn all animation off when prefers-reduced-motion is set"
    },
    "icons": "Line icons from lucide-react, 20px, stroke 1.75. Never emoji."
  },
  "layout": {
    "breakpoints_px": {
      "phone": "0-767",
      "tablet": "768-1023",
      "desktop": "1024+"
    },
    "phone": "Single column. Bottom tab bar with 3 tabs: Matches, Results, Insights. Sticky date strip and chips.",
    "tablet": "Single column with wider cards, tab bar at the bottom.",
    "desktop": "Left rail navigation (icons and labels). Two panes: match list (about 440px) on the left, match page on the right. Selecting a row fills the right pane without leaving the list.",
    "max_content_width_px": 1200,
    "touch_target_min_px": 44
  },
  "screens": [
    {
      "id": "matches",
      "route": "/",
      "data": "GET /api/matches?date=YYYY-MM-DD",
      "structure": [
        "Header: PitchProb wordmark (text only), a one-line description shown small under it, theme toggle. Matches start immediately below the date strip; no large hero.",
        "Date strip: Today, Tomorrow, then dated days; previous and next arrows on desktop; swipeable on phones; selected day filled with accent_soft",
        "League chips with counts, for example 'All 9', 'Champions League 9', 'Premier League 4'",
        "Per league: collapsible header with league name and match count",
        "Match row (64px high): kickoff time and date on the left | round badges and the two team names stacked | on the right the three-segment probability bar with Home, Draw and Away percentages under it, the pick in semibold",
        "Tapping a row expands it inline (chevron rotates) to show expected goals, Over 2.5, both teams to score and a 'Full match page' link; on phones the whole row also works as a link to the match page",
        "Finished match row: the score replaces the kickoff time; the right side shows the forecast pick and a tick (hit) or cross (miss) icon with a word",
        "Small neutral chip on the row when match.flags is not empty, e.g. 'Champions League in 2 days'",
        "Rows with no forecast show the note text in muted colour",
        "Footer line: 'Times in UTC' near the list header, and the estimates-not-advice notice at the bottom"
      ]
    },
    {
      "id": "match",
      "route": "/match/[id]",
      "data": "GET /api/matches/{id}",
      "structure": [
        "Sticky header: back arrow, league, kickoff or final score",
        "Teams block: two large placeholder badges, names, and in the centre the kickoff time or the final score",
        "Forecast hero: the three-segment probability bar at full width, three large percentages beneath it, then one sentence in plain words, e.g. 'The model leans Home, 48% against 25% for Away (a 23 point lead).'",
        "Segmented tabs: Overview, Markets, Form and H2H, Corners. The tab is stored in the URL (?tab=)",
        "Overview: expected goals for each team (two big numbers), top 5 likely scorelines as chips, Over 1.5 / 2.5 / 3.5 as thin bars, both teams to score as a thin bar, context flags",
        "Markets: handicap ladder (a table: line, win, push, lose, with a tiny 3-segment bar per row); goal lines",
        "Form and H2H: last 5 results for each team as W / D / L pills, last 5 head-to-head meetings as rows (date, score), season points per game for each team, league goals per match",
        "Corners: expected corners for each team, total corners over lines 7.5 to 11.5, each team over lines 2.5 to 6.5, drawn as thin bars with the percentage",
        "After full time: a 'Forecast vs result' panel with two columns side by side: Forecast (pick and probability) and Result (score and which outcome happened), with a hit or miss badge"
      ]
    },
    {
      "id": "results",
      "route": "/results",
      "data": "GET /api/results/days then GET /api/results?date=YYYY-MM-DD",
      "structure": [
        "Match-day strip: only days that have graded matches, newest first",
        "Day summary card: 'Most likely outcome was right in 7 of 10 matches' with a small progress bar",
        "Per league group, then rows showing forecast and result side by side: forecast bar with the pick highlighted, the real score, and a tick or cross",
        "Tap a row to open its match page"
      ]
    },
    {
      "id": "insights",
      "route": "/insights",
      "data": "GET /api/insights?source=backtest and ?source=live",
      "structure": [
        "Segmented control: Old matches | Live forecasts",
        "Card 1: 'When the model says 60%, how often is it right?' A column chart by confidence band (hit rate) with a marker for the model's average confidence in that band",
        "Card 2: 'Does a bigger lead mean a safer pick?' Table of lead sizes (0-5, 5-10, ... 30+ points) with matches and hit rate. Add a slider or stepper 'Only trust leads of at least N points' that shows how many matches remain and the hit rate",
        "Card 3: 'Are the percentages honest?' calibration chart: forecast on one axis, how often it happened on the other, with the diagonal for perfect",
        "Card 4: 'Which model is best?' comparison table: no model, goals model, goals model plus features, bookmaker odds, with log loss and share of top picks right",
        "Card 5: goals per match by league",
        "Plain-language caption under every chart, and a muted note when there are fewer than 100 matches"
      ]
    }
  ],
  "components": [
    "ProbabilityBar (props: home, draw, away, pick, outcome?, size) with an aria-label that reads the three numbers aloud",
    "MatchRow",
    "LeagueGroup",
    "DateStrip",
    "LeagueChips",
    "SegmentedTabs",
    "StatBar (thin horizontal bar with label and value)",
    "FormPills",
    "HandicapTable",
    "FlagChip",
    "ResultBadge (tick or cross plus text, never colour alone)",
    "ForecastVsResult",
    "BandChart and CalibrationChart (inline SVG, no chart library)",
    "EmptyState",
    "Skeleton",
    "ErrorState"
  ],
  "states": {
    "loading": "Skeleton rows with the same height as real rows",
    "empty": "A calm sentence and one action, e.g. 'No matches on this day. Try tomorrow.'",
    "error": "Plain words, a Retry button, no stack traces",
    "no_forecast": "Show match.note in muted text",
    "stale": "If the page has not refreshed for more than 10 minutes, show 'Updated 12 min ago'"
  },
  "accessibility": [
    "Contrast at least 4.5:1 for text and 3:1 for icons and bar segments",
    "Never use colour alone: results use icon plus word, the favourite segment also has a thicker top edge",
    "Visible 2px focus ring in the accent colour on every interactive element",
    "Full keyboard use; tabs follow the WAI-ARIA tabs pattern",
    "Touch targets at least 44 by 44 px",
    "Respect prefers-reduced-motion and prefers-color-scheme",
    "Charts have a table alternative for screen readers"
  ],
  "content_rules": [
    "Footer on every page: 'Forecasts are statistical estimates, not betting advice. 18+ only.'",
    "Never use the words tip, lock, banker, sure win, guaranteed",
    "No betting links, no odds comparison buttons, no sponsor slots",
    "Times are UTC and say so",
    "Write percentages as whole numbers, e.g. 48%"
  ],
  "data_contract": {
    "base_url_env": "API_BASE_URL (for example http://127.0.0.1:8000)",
    "optional_basic_auth_env": [
      "API_USER",
      "API_PASSWORD"
    ],
    "fetching": "Fetch on the server (React Server Components) with cache: 'no-store' for match data and revalidate: 300 for insights. The browser never calls the API directly.",
    "endpoints": {
      "GET /api/matches?date=YYYY-MM-DD": "{ date, matches: [Match] }",
      "GET /api/matches/{id}": "Match plus extras",
      "GET /api/results/days": "[{ date, n, hits }]",
      "GET /api/results?date=YYYY-MM-DD": "{ date, summary, matches: [ResultRow] }",
      "GET /api/insights?source=backtest|live": "{ source, model, n, confidence, gap, thresholds, calibration, comparison, leagues }"
    },
    "Match": {
      "id": 5001,
      "league": "PL",
      "league_name": "Premier League",
      "kickoff_utc": "2026-11-01T16:30:00Z",
      "home": "Arsenal",
      "away": "Chelsea",
      "forecast": {
        "p_home": 0.48,
        "p_draw": 0.27,
        "p_away": 0.25,
        "p_over25": 0.55,
        "p_btts": 0.52,
        "xg_home": 1.7,
        "xg_away": 1.1,
        "model": "dc",
        "pick": "H",
        "pick_prob": 0.48
      },
      "result": {
        "home_goals": 2,
        "away_goals": 1,
        "outcome": "H"
      },
      "pick_hit": true,
      "flags": [
        {
          "side": "home",
          "type": "cl_ahead",
          "days": 2
        }
      ],
      "note": null
    },
    "Match_extras": {
      "goal_lines": {
        "1.5": 0.8,
        "2.5": 0.55,
        "3.5": 0.3
      },
      "handicap": [
        {
          "line": -1.5,
          "win": 0.2,
          "push": 0.0,
          "lose": 0.8
        }
      ],
      "scorelines": [
        {
          "score": "1-1",
          "p": 0.11
        }
      ],
      "corners": {
        "exp_home": 5.8,
        "exp_away": 4.6,
        "total": {
          "9.5": 0.58
        },
        "home": {
          "4.5": 0.7
        },
        "away": {
          "3.5": 0.72
        }
      },
      "context": {
        "form_home": [
          "W",
          "W",
          "D",
          "L",
          "W"
        ],
        "form_away": [
          "L",
          "D",
          "W",
          "W",
          "D"
        ],
        "h2h": [
          {
            "date": "2026-02-01",
            "home": "Chelsea",
            "away": "Arsenal",
            "score": "0-1"
          }
        ],
        "season_ppg_home": 2.1,
        "season_ppg_away": 1.6,
        "league_gpm": 2.78
      },
      "features": "model inputs, not for display"
    },
    "notes": [
      "forecast is null when there is no forecast; then show note",
      "result is null until the match is graded",
      "extras.corners may be missing; hide the Corners tab when it is",
      "Percent values are fractions between 0 and 1"
    ]
  },
  "tech": {
    "stack": [
      "Next.js (latest stable, App Router)",
      "TypeScript",
      "CSS Modules with the CSS variables above (no Tailwind, no UI kit)",
      "lucide-react",
      "@fontsource-variable/manrope"
    ],
    "rendering": "Server Components by default; client components only for the theme toggle, collapsible league groups and the threshold stepper",
    "state_in_url": [
      "date",
      "league",
      "tab",
      "source"
    ],
    "performance_targets": "Largest Contentful Paint under 2.5 s on a mid-range phone on 4G; first-load JavaScript under 150 KB compressed; no layout shift when data arrives (reserve row heights)"
  },
  "do_not": [
    "No purple-to-blue gradients, no neon green on black, no glassmorphism",
    "No emoji used as icons, no stock football imagery",
    "No cards inside cards inside cards",
    "No ALL CAPS micro-labels above every heading",
    "No invented data: use only the fields in the data contract; for development use a mock server that returns the sample JSON",
    "No chart libraries; draw the few charts with inline SVG",
    "Do not add betting features, accounts, payments or alerts"
  ],
  "acceptance_checklist": [
    "Matches page at 375, 768 and 1280 px wide looks intentional, with no horizontal scrolling except the date strip and chips",
    "A match row can be read in under two seconds: time, teams, favourite",
    "The probability bar reads correctly with only the aria-label (screen reader test)",
    "Light and dark themes both pass the contrast pairs above",
    "A finished match shows forecast and result together, with icon plus word for hit or miss",
    "Results page shows one block per match day with the day summary",
    "Insights page shows the five cards with plain-language captions",
    "Every list has loading, empty and error states",
    "Lighthouse accessibility score of 95 or more"
  ]
}