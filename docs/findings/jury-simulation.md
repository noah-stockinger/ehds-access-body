# Finding: jury simulation (30 Oct 2026)

Analysis note, not binding. The jury sends new requests on the same data. `tests/jury/cases.json` (42 cases, written by
`scripts/make_jury_cases.py`) holds three kinds, each with the expected outcome written down **before** the first run:

- **new** (14): well-formed but unlike R01–R10: per hospital, main diagnosis (`primary_icd10`), plain-English names
  without codes, other years, sex groups, an SPE with other wording, three new prohibited purposes
- **wildcard** (11): same meaning, messy form: lower-case codes, `=` without spaces, one text instead of a list, no
  `id` / `submitted`, capitalised request type, `ICD10`, extra fields, typos, German
- **error** (17): requests that make no sense or are broken: contradictory ages, overlapping bands, codes or years the
  data does not have, a statistics request asking for records, a term defined twice, gibberish, a question about BMI
  whose definitions compute HbA1c, an empty SPE cohort, missing fields

Numbers for every approved case come from `scripts/jury_oracle.py`, plain pandas that imports nothing from `hdab`.
Run: `make jury` (rules only).

| | before | after |
|---|---|---|
| new as expected | 13/14 | **14/14** (all numbers match the oracle) |
| wildcard as expected | 5/11 | **11/11** |
| error as expected | 7/17 | **17/17** |
| silent wrong approvals | **10** | 0 |
| wrong numbers | 1 (lower-case `e11` silently counted 0 patients) | 0 |
| leaks | 0 | 0 |

R01–R10 (10/10, 6/6, 0 leaks), red team (30/30) and all older tests unchanged.

## What changed
- `plan.py`: codes are upper-cased (`e11` → E11; before, the clause matched case-insensitively but the code list came
  back empty, so every count was 0 with no flag); `=` without spaces; `ICD10` / `ICD 10`; irregular plurals
  (children, women, men); a term defined twice with different meanings is flagged
- `contracts.py`: `id` and `submitted` get defaults when missing; `requested_as` is case-insensitive; `definitions`
  may be one text (split per line or sentence). Content fields stay required: a request without a purpose is a 422
- `sanity.py` (new), run on every non-rejected request; each finding is a `Sanity:` review reason and withholds the
  numbers: inverted age range, overlapping bands, an age group that falls into none of the bands, a code / LOINC /
  main diagnosis / year the data does not have (only where it selects patients: "without X" stays answerable),
  a population or SPE cohort with nobody in it, a health data request asking for records, a question naming a
  condition, drug or measurement that no definition covers
- Two old tests reused R01's and R08's question with different definitions; the new question check flagged them, so
  each now has a question matching its definitions

## Follow-up: more phrasings (30 Oct, later)
Seven more wildcard cases (W12–W18), expected outcomes first: `ICD-10 code E11` without "starting with", `aged 18+`,
an age without the reference date (assumed and noted), `aged between 18 and 64`, `Exclude patients with chronic kidney
disease`, `Exclude opted-out patients`, and one that must stay in review: `Exclude patients who had a stroke in the
last year` (no time-window template). Before: 6 of the 7 went to review without numbers. After: 49/49 as expected,
numbers match the oracle, 0 silent wrong approvals.

## Still open
- Anything outside the parser's sentence templates goes to **review with no numbers**. That is safe, but on a jury
  request it scores as "no numbers". Typical misses would be new definition shapes; add templates when we see them.
- Jev-led mode was not run here (no `TYPESAFE_API_KEY` in this environment); the sanity checks run in every mode.
- The question check only knows the ~30 names in `vocab.CURATED`.
