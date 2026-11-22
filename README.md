# Critter Lab

Backtest playground for the Critter Board (apabones/CBB-Critters). Pick any combination of critters, sizes, pillars,
steadiness, apex traits and flags, and see how it did against the closing spread in 2025-26.

- `index.html`: the Lab page
- `lab_2025-26.json`: every 2025-26 game from Dec 1 to the end of the season with a closing spread, with both teams'
  board ratings rebuilt as of that day from earlier games only
- `build_lab.py` + `fetch_ncaab.py`: rebuild the data with the board's exact rules
  (`python build_lab.py 2026 pillar_run_2025-26.csv`)

2024-25 is deliberately not here. When a scan looks good, use "Copy for 2024-25 test" and have it checked on the
held-out season.
