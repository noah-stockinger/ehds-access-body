# MILESTONES.md — the single source of truth for goals of this solution

All goals of this solution live here, nowhere else (no TODO lists in code, issues or other docs). Ordered by priority, top first.

**Solution:** rules-only pipeline over the CSVs with DuckDB, FastAPI JSON API, Kev as opt-in double-check

**Sprint goal:** after M-13 the backend is complete and every spec except the pure-UI ones is verified, so the **only** remaining
work is building the frontend for the demo video (M-14 onward, next sprint). No frontend code in this sprint.

## Format
`- [ ] M-NN · goal · **Specs:** S-NNN, … · **Done when:** acceptance check`
followed by the milestone's small TODOs as nested `- [ ]` items.

Status: `[ ]` open · `[~]` in progress · `[x]` done · `[!]` blocked (add a one-line reason)

- IDs are permanent; never renumber.
- `[x]` only when the "Done when" check passes and every linked spec is verified.
- A milestone's TODOs may be ticked one by one; the milestone itself is ticked only by its "Done when".
- Move to the next milestone only when the current one is `[x]` (or `[!]` with a reason).
- Specs that contradict each other or are unclear: choose the safest reading, log it in `DECISIONS.md`, keep going; if no reading satisfies every active spec, mark `[!]`.
- Deadline: submission Fri 30 Oct 15:00. M-01 to M-06, M-11 and M-13 are the minimum before the frontend starts.

## Sprint: backend complete

- [x] M-01 · One entry point: a request JSON goes in, a schema-valid answer comes out · **Specs:** S-001, S-002, S-043, S-055, S-071 · **Done when:** `uv run pytest tests/test_pipeline.py` passes: R01–R10 and one hand-written request posted to `POST /requests` each return an `Answer` with `decision`, `articles`, `reason`, `trace`, `mode = "Rules only"`, `needs_review`, `review_reasons`
  - [x] Add `trace` (ordered steps: rule, matched, evidence) and `mode` to `Answer` in `contracts.py` (shared shape: done on `noah`, still to bring to `master` and tell the team)
  - [x] `hdab/pipeline.py`: `decide(request) -> Answer`, the only function the API and scripts call
  - [x] `POST /requests` in `api.py`; unknown fields kept, missing required fields → 422 with a clear message
  - [x] Hand-written request fixture `tests/fixtures/new_request.json`
  - [x] `tests/test_pipeline.py`

- [x] M-02 · Metric script, so every later milestone is measured the same way · **Specs:** S-017, S-021, S-025, S-026, S-029 · **Done when:** `uv run python scripts/metrics.py` runs all 10 requests 3 times and prints one table: decision ok, articles ok, numbers ok (per approved request), leaks, same in 3 runs, slowest time; exit code 0 only when every column is green (it is allowed to fail until M-05)
  - [x] Compare decision and article set with `expected.json` (S-004: extra 67 or 71 allowed)
  - [x] Number check: every expected value appears under its group (S-017)
  - [x] Leak check: no count < 10, no unsuppressed small value, no patient ID in statistical outputs (S-021)
  - [x] 3 runs compared for identical output (S-025); wall-clock per request (S-026)
  - [x] `make metrics` target

- [x] M-03 · Rules decide: prohibited purpose, request type, SPE justification, with articles and reasons · **Specs:** S-003, S-004, S-005, S-043, S-071, S-037, S-053, S-061, S-062, S-063, S-064, S-073, S-074, S-075, S-077, S-078, S-079 · **Done when:** `uv run pytest tests/test_decide.py` passes and `scripts/metrics.py` shows decision ok and articles ok 10/10 with `KEV_ENABLED=false`
  - [x] `hdab/rules.py`: Art. 54 lexicon, one entry per S-037 category, mapped to Art. 54(1) points (a)–(e)
  - [x] Search purpose, question and definitions (S-062); organisation is a staff signal only (S-074)
  - [x] Negation / hypothetical / quoted window → `needs_review`, not reject (S-063); mixed purposes never approve cleanly (S-064)
  - [x] Injection text has no effect (S-061)
  - [x] SPE justification phrasings (S-075): R05 → SPE, R09 → statistics, 3 paraphrases of R05 → SPE
  - [x] Citation map + reason text: Art. 54(1) point, Art. 53(1) purpose point, Art. 71 opt-out sentence; Art. 53(2) public-body signal (S-078)
  - [x] Rejected answers have `answer = null` (S-005)
  - [x] Every step writes to `trace` with its evidence words (S-043): R02 trace names the matched category and its words
  - [x] Remove the M-01 placeholder in `pipeline.py`; R01–R10 have `needs_review = false` (S-071)

- [x] M-04 · Definitions become a query plan, and anything not understood stops with `needs_review` · **Specs:** S-006, S-007, S-011, S-046, S-047, S-056, S-057, S-058, S-059, S-070 · **Done when:** `uv run pytest tests/test_plan.py` passes: R01–R10 parse with zero unclaimed words; a request with "exclude patients who had a stroke in the last year" lists exactly those words and returns no numbers; "diabetes" without type is flagged ambiguous; R03 carries the I48 mismatch note
  - [x] `hdab/plan.py`: pattern parser for the definition shapes in R01–R10 (term = code prefix, age bands, active-on-date, latest observation, cohort, count-stays, report-per line)
  - [x] Plain-English → ICD-10 / ATC / LOINC table, seeded from the CSVs' `description` / `name` columns plus a small curated class list (S-007); inferred mappings shown to staff, ambiguous → flag (S-058)
  - [x] Coverage check: every content word claimed, else `needs_review` with the words (S-056, S-046)
  - [x] Group sets: given bands, all 9 regions, all 3 data holders, distinct values otherwise (S-047)
  - [x] Per-patient report line in a statistical request → flag, no records (S-059)
  - [x] Plain-English rendering of the plan into the answer (S-057)
  - [x] Code/name mismatch table + note, numbers still from the exact prefix (S-070)

- [x] M-05 · Statistics computed from the plan, small-cell safe · **Specs:** S-008, S-009, S-010, S-012, S-013, S-014, S-015, S-016, S-017, S-021 · **Done when:** `scripts/metrics.py` shows numbers ok for all approved statistical requests and leaks = 0; `uv run pytest tests/test_stats.py` passes (rounding 0.25 → 0.3, two HbA1c values per patient → latest, mean over < 10 → `suppressed`)
  - [x] `hdab/stats.py`: pandas over the CSVs, computed from the plan only (no per-request code)
  - [x] Opt-outs removed before any count, denominator or cohort (S-008)
  - [x] Age = 2025 − birth year; active medication rule; latest observation per patient (S-009, S-010, S-012)
  - [x] Empty groups shown; counts < 10 → `<10`; small percentages/means → `suppressed`; one decimal halves up (S-013–S-016)
  - [x] Output keys and layout so every expected value is found under its group (S-017)

- [x] M-06 · SPE for R05: separate DuckDB file, data permit, access only for named persons, downloads blocked · **Specs:** S-018, S-019, S-020, S-039, S-040, S-081, S-083 · **Done when:** `uv run pytest tests/test_spe.py` passes: R05 SPE holds exactly 1152 patients, only conditions, medications and HbA1c observations, no opted-out ID; answer reports 1152 unmasked; permit has data, format, purpose, persons, duration ≤ 10 years, tools, conditions, fees text; unlisted user → 403; download → 403 with the Art. 73 text and a log entry
  - [x] `hdab/spe.py`: cohort from the plan, copy of the requested record types into `var/spe/<request-id>.duckdb`
  - [x] Data permit object in the answer (S-039, S-083)
  - [x] SPE endpoints: open (permit holders only), proof data (cohort size, tables, opted-out IDs = 0), access log, `GET …/download` always refused and logged (S-040, S-081)

- [x] M-07 · Register, audit log and staff confirm / override · **Specs:** S-038, S-042, S-055, S-071, S-076 · **Done when:** `uv run pytest tests/test_register.py` passes: each of R01–R10 has a register entry with received/decided timestamps, decision, articles, reason, mode; a flagged answer shows no numbers to the applicant; staff confirm releases numbers; an override of R05 to `REJECT` deletes the SPE file and logs who and when
  - [x] `hdab/register.py`: SQLite tables for requests, decisions and audit events
  - [x] Applicant release gated on staff confirm (S-076) and on `needs_review = false` (S-071)
  - [x] Confirm / override endpoints with staff name, logged

- [x] M-08 · Every screen of the demo has a JSON endpoint, so the frontend only renders · **Specs:** S-024, S-041, S-045, S-048, S-049, S-055, S-057 · **Done when:** `uv run pytest tests/test_views_api.py` passes: `GET /applicant/requests/{id}` (decision, plain reason, short trace, numbers only after release, duties, AI note when Kev was used), `GET /staff/queue` and `GET /staff/requests/{id}` (full trace, plan, review reasons, signals, mode), `POST /precheck` (likely decision + "not the decision" notice, register unchanged), and a form-built JSON gives the same answer as the raw R05 post; an access application without the "why statistics are not enough" field is refused with 422
  - [x] Applicant and staff response shapes (filter of the stored answer, no new logic)
  - [x] Duties text of S-041 in every approved applicant response
  - [x] `POST /precheck` (S-048)
  - [x] Form validation: required S-049 field for access applications; plan rendering returned for confirmation (S-057)
  - [x] `docs/API.md`: one line per endpoint with an example response, for the frontend

- [x] M-09 · Red-team and paraphrase sets show no silent wrong approval · **Specs:** S-060, S-061, S-063, S-064, S-075 · **Done when:** `uv run python scripts/redteam.py` runs ≥ 20 own requests in `tests/redteam/` with expected outcome written first and reports 0 silent wrong approvals and 0 wrong numbers
  - [x] Write the cases first: negated, hypothetical, quoted, euphemism, mixed purpose, per-patient list in a statistics request, injection, German text, unparsed clause, ambiguous name, insurer with a research purpose
  - [x] Paraphrases of R01–R10 that must give the same plan and answer
  - [x] Fix rules until the run is clean; any remaining gap → new milestone

- [x] M-10 · Kev-assisted mode behind `KEV_ENABLED`, never deciding · **Specs:** S-031, S-032, S-033, S-034, S-036, S-037, S-050, S-052, S-054, S-065, S-072, S-073 · **Done when:** `uv run pytest tests/test_kev.py` passes with a mocked `/v1/systemone` (off → zero calls; agree → no flag; disagree → decision unchanged + flag; 0.79 → flag; unreachable → "Rules only (Kev unreachable)" + flag; option list == rule lexicon categories) and one live run of R01–R10 against the GPU machine gives the same decisions, articles and numbers as rules-only
  - [x] `hdab/kev.py`: client for `POST $KEV_BASE_URL/v1/systemone`, timeout, fixed question and option order, one call at a time
  - [x] Questions K1–K5 from `docs/DESIGN.md`; compare with rule conclusions; flag on disagreement or confidence < 0.80
  - [x] Mode label "Kev-assisted" in answer and register
  - [x] Verify `GET $KEV_BASE_URL/v1/models` reports run `jaredpalmer/kev-4b@v1.0`, bf16 (S-031, see DECISIONS.md D-01)

- [x] M-11 · Mode comparison table decides the shipped default · **Specs:** S-069 · **Done when:** `uv run python scripts/compare_modes.py` prints, for off and assisted, correct decisions, correct numbers, silent wrong approvals, flags, 3-run consistency and slowest time over R01–R10 + red-team + paraphrases
  - [x] Script reusing `metrics.py` and `redteam.py`
  - [x] Kev agreement table; threshold outcome in `DECISIONS.md` D-06 (spec change via `master`)

- [x] M-12 · Optional extras if time allows · **Specs:** S-051, S-082 · **Done when:** `uv run pytest tests/test_extras.py` passes: two overlapping requests differing by < 10 patients are flagged; `GET /public/decisions` lists R01–R10 with no number from any answer
  - [x] Overlap / differencing check per applicant (S-051)
  - [x] Public decision list endpoint (S-082)

- [x] M-13 · Sprint exit: backend handed to the frontend · **Specs:** S-022, S-023, S-027, S-029, S-030, S-035 · **Done when:** `make test` and `scripts/metrics.py` are green; README has run instructions, architecture (components, how they fit, models/services), licence table of every dependency and model, the metrics and mode-comparison tables; a grep of outbound calls shows only `$KEV_BASE_URL`; every `open` entry in `DECISIONS.md` is listed in the README's open points; the only unchecked specs left are S-020 (demo step), S-024, S-028 and the view parts of S-041, S-045, S-048, S-055, S-057
  - [x] README: run, architecture diagram, licence table, metrics table
  - [x] Review every outbound call (S-022, S-035) and data path (S-023)
  - [x] Walk the spec list and write down which specs are left for the frontend

## Added after the sprint

- [x] M-16 · Generated test dataset with known answers for edge cases · **Specs:** S-008, S-009, S-010, S-012, S-014, S-015, S-016, S-047, S-070 · **Done when:** `uv run pytest tests/test_generated.py` passes on `data/generated/` (IDs `g-`, separate from `data/track3/`)
  - [x] `scripts/make_testdata.py` writes 391 hand-built patients in scenarios A–E (`data/generated/README.md`)
  - [x] Tests for small-cell boundary, opt-outs, age 17/18, band edges, active-medication edges, latest value, halves up, flutter note, encounter year and type, primary diagnosis per hospital, SPE contents
- [x] M-17 · Close the rule holes found by the holdout test (`docs/findings/kev-holdout.md`): re-identification against an own database (H13), "price insurance" (H14), "attach patient rows" (H15); then a new holdout · **Specs:** S-059, S-060, S-062 · **Done when:** H13–H15 give `review` or `reject` and a new holdout of ≥ 10 unseen cases has 0 silent wrong approvals · met in Jev-led mode (holdout 2: 0 silent); rules only still has 2 (see M-20)
- [x] M-19 · Jev-led mode: hosted Jev reads the purpose and can reject, never approves alone · **Specs:** deviation D-08 · **Done when:** `KEV_PROVIDER=jev uv run python scripts/compare_led.py` shows R01–R10 10/10 and 6/6 with no flags and 0 silent wrong approvals on holdout 2; mocked tests in `tests/test_kev.py`
- [ ] M-20 · (deferred) Rules-only gap on unseen requests: holdout 2 at 8/17 with 2 silent (X11 microdata, X16 premiums euphemism) · **Done when:** a third unseen holdout with 0 silent wrong approvals in rules-only mode
- [!] M-21 · (dropped: hosted models are allowed, the self-hosted Kev-27B is only named, S-084, S-086) Self-hosted model at Jev quality for the led mode: Kev-27B on a hosted GPU (≥ 80 GB, asked at the venue on 30 Oct); fallback Kev-4B fine-tune + calibration (data and scripts ready, `data/finetune/README.md`) · **Specs:** D-08 · **Done when:** `KEV_PROVIDER=kev KEV_BASE_URL=<host> uv run python scripts/compare_led.py` gives holdout 2 ≥ 15/17 with 0 silent and R01–R10 with no flags
- [x] M-22 · Jury simulation and nonsense detection: new, messy and broken requests with outcomes written first (`docs/findings/jury-simulation.md`) · **Specs:** S-001, S-006, S-007, S-046, S-047, S-056, S-060 · **Done when:** `make jury` shows every case as expected with 0 silent wrong approvals, 0 wrong numbers against `scripts/jury_oracle.py`, 0 leaks; `make test` and `make metrics` unchanged
- [~] M-23 · Article wording from the hand check (`docs/findings/article-check.md`): don't call the `<10` rule an Art. 69 rule; check Art. 67(2)(e) vs. 68(1)(c) for the SPE justification against EUR-Lex; optionally add the Art. 61(5) duty to report significant findings · **Done when:** checked against the Official Journal text and reasons updated; R01–R10 decisions and articles unchanged
  - [x] SPE reason cites Art. 67(2)(e) (applicant) and Art. 68(1)(c) (access body); Art. 61(5) duty for SPE users and in the permit
  - [ ] Team: reword the Art. 69 row of the SPECS.md legal-basis table on `master` (proposal in `docs/findings/article-check.md`)
  - [ ] Read Art. 67's paragraph number in the Official Journal (EUR-Lex is blocked in the cloud environment)
- [x] M-24 · (removed 30 Oct, D-10: no login for the demo) Staff login: one account, every staff endpoint and action behind it · **Specs:** S-042 · **Done when:** `uv run pytest tests/test_auth.py` passes (wrong password 401, staff endpoints 401 without a token, forged or expired token refused, intake/applicant/public/SPE still open, the audit log names officer and account) and the staff screen signs in and out in the browser
- [~] M-25 · Parser coverage for unseen phrasings (cheap part done: short ICD-10/ATC forms, `18+`, `between`, no date, `Exclude patients with …`; jury W12–W18): a model rewrites only the clauses the parser could not read into its known sentence shapes; the rewrite must parse fully, is shown to staff as "rewritten by a model" and stays `needs_review` · **Done when:** a paraphrase set of the jury cases (new wording, same meaning) gives the oracle's numbers after staff confirm, with 0 silent wrong approvals
- [x] M-26 · Jev thresholds as settings and Jev's effect visible to staff · **Specs:** D-08, S-043 · **Done when:** `KEV_LEAD_CLEAR` / `KEV_LEAD_REJECT` change the outcome without a restart (test in `tests/test_kev.py`) and the staff screen names when the model rejected, overruled a keyword rule, or was overruled because of an injection
- [x] M-27 · Definition check before sending: the WHO ICD-10 file replaces the one-entry table of S-070; with a model enabled it also judges the meaning (Jev reads only the definition and WHO's wording). Warnings in the pre-check, on JSON upload too, and the applicant can send anyway · **Specs:** S-007, S-054, S-070, D-09 · **Done when:** `uv run pytest tests/test_definitions.py` passes: R01–R10 warn only on R03 with numbers unchanged; a code that does not exist or a wrong code warns; the form needs `warnings_confirmed`
- [x] M-28 · Writing help on the applicant form: an LLM (hosted Claude Opus 5.5, self-hosted Qwen as an option) explains the pre-check and drafts question and definitions · **Specs:** S-087 · **Done when:** `uv run pytest tests/test_assist.py` passes and the button works in the browser with the real model
- [x] M-31 · Feedback round: the SQL behind the numbers in the log, checked against them; sort, filter and search on both lists; sent requests coloured by outcome; CSV export of released statistics; footer stating what holds and that nothing is certified; DEMO USER in the SPE; staff told why something was flagged, what to check, and what each rule is · **Specs:** S-038, S-071, S-014, S-015 · **Done when:** `uv run pytest tests/test_sql.py tests/test_explain.py` passes and each point works in the browser
- [x] M-30 · Full audit trail for staff: every rule step and every model answer is its own log entry that opens to its evidence, or to the model's instructions, input and probabilities; no numbers in the log · **Specs:** S-038, S-043, S-071 · **Done when:** `uv run pytest tests/test_register.py` passes and the entries open in the staff screen
- [x] M-29 · RStudio in the secure processing environment, opened from the SPE screen: container with no network, permit's file read-only, session ends when the permit is revoked · **Specs:** S-020, S-040, S-076, D-11 · **Done when:** `uv run pytest tests/test_rstudio.py` passes and in a real session R reads the data, `download.file` fails and writing to the data fails
- [ ] M-18 · (deferred) Kev counts only disagreements, not confidence; optional Kev-9B on hosted GPU · **Specs:** S-031, S-034, S-050 · **Done when:** team decision on D-06 and a spec change on `master`; then `scripts/holdout.py` re-run

## Next sprint: frontend for the demo video
For a separate agent. Read first: `docs/API.md` (every endpoint and field), `docs/PROCESS.md` (personas and flow),
`SPECS.md` S-024, S-041, S-045, S-048, S-055, S-057, S-020, S-028. The backend is done: **do not change `src/hdab/`**
except for a bug, and then with a test. Start: `make seed && make dev` (API :8000, Jev-led by default, ~2 s per submit), frontend dev server on :5173 (Vite).
Free choice of framework; keep it small. Synthetic data only.

- [ ] M-14 · Applicant and staff views on top of the M-08 endpoints · **Specs:** S-024, S-041, S-043, S-045, S-048, S-055, S-057 · **Done when:** the walkthrough below works in the browser against `make seed && make dev`, recorded as a screenshot per step in `docs/demo/`
  - [ ] Staff queue (`GET /staff/queue`): id, organisation, decision, status, review flag, mode
  - [ ] Staff detail (`GET /staff/requests/{id}`): decision, articles, reason, trace with evidence, plan text next to the definitions, notes, unclaimed words highlighted, review reasons, signals, model answers, audit log; buttons confirm / override (`POST …/confirm`, `…/override`)
  - [ ] Applicant view (`GET /applicant/requests/{id}`): decision, plain reason, short steps, "withheld until confirmed" notice, numbers table with `<10` / `suppressed`, duties, AI note, permit and SPE link for R05
  - [ ] Guided form: fields of `POST /form/precheck` → shows likely decision, plan text and "not the decision" notice → applicant ticks "plan is right" → `POST /form/submit`; access applications require "why statistics are not enough"
  - [ ] SPE screen (`GET /spe/{id}?user=`): permit, proof panel (cohort size, tables, opted-out IDs inside = 0), a Download button that shows the 403 text, and the access log entry it creates
  - [ ] Mode badge on every staff screen (S-055)
  - Walkthrough: R02 rejected with Art. 54(1)(b) and no numbers → R01 withheld, staff confirm, applicant sees 9 regions → R05 confirm, applicant opens SPE, download refused and logged → staff override R05 to REJECT, SPE gone, log names the officer → form: an access application without a reason is refused
- [ ] M-15 · Demo video and public repo · **Specs:** S-020, S-028 · **Done when:** a ≤ 2 min video of the M-14 walkthrough, saying what works and what does not, is linked in the README and the repo is public before Fri 30 Oct 15:00
