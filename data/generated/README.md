# Generated test data (not challenge data)

**Fake patients made by us, for tests only.** The official challenge data is in `data/track3/` (git submodule) and stays
untouched. Everything here is written by `scripts/make_testdata.py`, deterministically; patient IDs start with `g-`
(the challenge uses `p-`), encounter IDs with `g-e`.

Same 5 CSVs and columns as `data/track3/data/`. The app never reads this folder unless `$TRACK3_DATA` points at
`data/generated`; `tests/test_generated.py` switches to it per test.

| Scenario | Where | What it checks |
|---|---|---|
| A | Burgenland 10, Kärnten 9, Wien 12 (+3 opted out), Tirol 9 + one aged 18 + one aged 17 with type 2 diabetes | small-cell boundary 10 vs. 9, opt-outs, age = 2025 − birth year |
| B | Oberösterreich hypertension aged 49 / 64 / 65 | band edges; ACE inhibitor ending on 31 Dec 2025 (active), on 30 Dec (not), starting 2026 (not), open (active); 13/80 = 16.25 % → 16.3 |
| C | Salzburg 10 women with breast cancer and an old + a new BMI, Steiermark 9 | latest value per patient, mean 26.25 → 26.3, men and patients without BMI left out |
| D | Niederösterreich 10 × I48.0 + 2 × I48.3 | the S-070 note lists flutter codes that occur in the data |
| E | Vorarlberg and Kärnten encounters | inpatient only, start year 2025 (not 31 Dec 2024), opted-out stays excluded, primary diagnosis only in encounters |
| filler | 20 adults per region | every region has patients, so every group appears |

Regenerate: `uv run python scripts/make_testdata.py`.
