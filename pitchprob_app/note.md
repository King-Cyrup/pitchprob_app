[ ] python cli.py check-access shows OK for every league you kept
[ ] python cli.py status shows 380 (PL, PD, SA) or 306 (BL1, FL1) matches for each completed season
[ ] python cli.py train trained a model for every league you kept
[ ] python cli.py evaluate shows PASS for every league you kept, and over-2.5 and both-teams-to-score columns beat the constant (or those columns are removed from the page)
[ ] python cli.py check-names prints All team names are matched.
[ ] The page lists upcoming matches with probabilities that add to about 100% across Home, Draw, Away
[ ] The page says forecasts are estimates, not betting advice, and 18+ only
[ ] python -m pytest -q shows 9 passed
[ ] The page is protected (Cloudflare email lock or APP_PASSWORD)
[ ] Locked forecasts (within 60 min of kickoff) show a lock badge and are never overwritten by re-predict
[ ] You ran python cli.py daily successfully at least once from start to end