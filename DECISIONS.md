# DECISIONS.md — scratchpad for spec conflicts (branch `noah`)

The agent writes here whenever specs contradict each other, or a spec is unclear, and it had to choose a reading to keep going.
Not binding and not a goal list (rules: `SPECS.md`, goals: `MILESTONES.md`). We read this together after the sprint;
settled points become a spec change on `master`.

## How to add an entry
- Pick the reading that is safest: doubt goes to `needs_review`, never to an approval; never change a decision, article set or number of R01–R10.
- If no reading keeps every active spec satisfied, do not choose: mark the milestone `[!]` and write the entry anyway.
- Leave a code comment `# see DECISIONS.md D-NN` where the choice is implemented.
- One entry per conflict, newest at the bottom, IDs never reused.

```
### D-NN · short title · open
- **Milestone:** M-NN
- **Specs:** S-NNN vs. S-NNN
- **Conflict:** what the specs say and why both cannot hold as written
- **Chosen:** what the code does now
- **Why:** one or two lines
- **Alternatives:** other readings
- **To discuss:** the question for the team
```

Status: `open` (not discussed yet) · `kept` (team agrees, spec change pending or not needed) · `changed` (team chose differently, code to update)

## Entries
### D-01 · Kev reports its model as `kev-latest`, not `kev-4b` · open
- **Milestone:** M-10
- **Specs:** S-031
- **Conflict:** S-031's Verify expects `GET /v1/models` to report `kev-4b`; the running server lists `kev-latest` (and `jev-latest`) with `"run": "jaredpalmer/kev-4b@v1.0"`
- **Chosen:** the check reads the `run` field (`jaredpalmer/kev-4b@v1.0`) plus `dtype = bfloat16`; requests send `"model": "kev-latest"`
- **Why:** `run` is the field that names the weights; the name is only an alias
- **Alternatives:** change the S-031 Verify text on `master`
- **To discuss:** reword S-031's Verify to check `run`?

### D-02 · Which number is "Kev confidence" for a `choice` answer · open
- **Milestone:** M-10
- **Specs:** S-034, S-050
- **Conflict:** a `choice` answer carries both `confidence` (e.g. 0.68) and the chosen option's probability (e.g. 0.79); S-034 says "Kev confidence" without saying which, and the two give different flags at 0.80
- **Chosen:** not yet chosen; proposal: use `confidence` for `choice`, and `max(noul, 1 − noul)` for `noul`
- **Why:** `confidence` is the server's own field for this; it is the stricter of the two
- **Alternatives:** use the chosen option's probability
- **To discuss:** which field, and is 0.80 still the right threshold for it (M-11)?

### D-03 · M-01 ticked before S-043 and S-071 fully pass · open
- **Milestone:** M-01
- **Specs:** S-043, S-071 vs. the M-01 "Done when"
- **Conflict:** M-01 links S-043 and S-071, but their Verify needs real decisions (R02 trace names its Art. 54 category; R01–R10 have `needs_review = false`), which only exist after M-03
- **Chosen:** M-01 ticked on its schema check; until M-03, `decide` returns a placeholder `REJECT` with `needs_review = true` and no numbers; the decision-dependent parts of S-043 and S-071 moved to M-03's specs and TODOs
- **Why:** the placeholder errs towards no data released; a fake approval would break the "doubt never approves" rule
- **Alternatives:** keep M-01 open until M-03 is done
- **To discuss:** fine to split a spec's Verify across milestones like this?

### D-04 · A defined condition that the report line never uses restricts the population · open
- **Milestone:** M-04
- **Specs:** S-006, S-017 vs. S-056
- **Conflict:** R08 defines "Breast cancer = C50" but its report line only says "number of women with a BMI and mean BMI"; the expected numbers (15 in Niederösterreich) are only reached if every count is limited to breast-cancer patients, which the report line does not say
- **Chosen:** a defined condition or medication that no report item uses restricts every count **if the question or purpose names it** ("women with breast cancer"); the plan text and a note say so; if neither names it, the definition counts as unclaimed → `needs_review`, no numbers
- **Why:** matches R08 and keeps the "never guess" rule for definitions nobody refers to
- **Alternatives:** always restrict by unused definitions; or always flag
- **To discuss:** acceptable reading for new jury requests?

### D-05 · `POST /requests` returns numbers before staff confirm · open
- **Milestone:** M-08
- **Specs:** S-001, S-017, S-026 vs. S-071, S-076
- **Conflict:** the jury posts request JSON and expects the numbers back (S-001, S-017, timed by S-026), but S-076 releases numbers to the applicant only after staff confirm
- **Chosen:** `POST /requests` is the access body's intake: it returns the full staff answer (numbers, review reasons, signals). Applicants use `/form/submit` and `GET /applicant/requests/{id}`, which withhold numbers and the permit until staff confirm
- **Why:** keeps the jury path and the metric script working while the applicant path follows S-076
- **Alternatives:** `POST /requests` returns the applicant view, and the jury reads numbers from the staff view
- **To discuss:** is the jury "staff" or "applicant" in the demo?

### D-06 · Kev-assisted flags every request at the 0.80 threshold; Rules only ships as default · open
- **Milestone:** M-11
- **Specs:** S-050, S-069 vs. S-071
- **Conflict:** S-071 says R01–R10 have `needs_review = false`; with Kev on, Kev's confidences (median 0.48 for K1, 0.68–0.75 for K2–K4) are below 0.80 for every request, so all 10 are flagged (6/10 even at 0.50, through disagreements on K2 for R06 and K5 for R09). Decisions, articles and numbers stay identical and there are 0 silent wrong approvals in both modes
- **Chosen:** Rules only stays the shipped default (`KEV_ENABLED=false`, S-052); threshold left at 0.80; K1 counts as agreement when both say "prohibited" even with a different category (R10: Kev says advertising, rules say harmful products); K3 reworded ("a reason why statistics are not enough; merely asking for records is not a reason"), which took K3 agreement from 1/3 to 3/3
- **Why:** S-069 says the default is chosen from the table; Kev adds flags but no correct decision the rules missed
- **Alternatives:** lower the threshold to 0.5 and accept 6/10 flags; drop K1's confidence from the threshold (choice confidences are low by design)
- **To discuss:** is Kev worth showing in the demo as a second reader that flags, or only mentioned?

### D-07 · Our own generated patients next to the challenge data · open
- **Milestone:** M-16
- **Specs:** S-023
- **Conflict:** S-023's Verify says data comes from `data/track3/` only; the generated test set in `data/generated/` is synthetic too, but not from there
- **Chosen:** generated data is used only by `tests/test_generated.py` (and anyone who sets `$TRACK3_DATA` on purpose); the app's default stays `data/track3/`; IDs start with `g-` so the two can never mix
- **Why:** edge cases (10 vs. 9, end date on 31 Dec, age 17/18, 16.25 → 16.3, flutter codes) cannot be tested on the challenge data alone
- **Alternatives:** keep test data inside `tests/` instead of `data/`
- **To discuss:** reword S-023 to "only synthetic data; the app runs on `data/track3/`"?

### D-08 · Jev-led mode: a hosted model reads the purpose and can reject · open
- **Milestone:** M-19
- **Specs:** S-033, S-054 and team decision D2 (model must not decide). The hosted, closed model no longer conflicts: S-084 and S-085 replace S-035 and S-030
- **Conflict:** Noah asked for the strongest base first, data safety and AI Act later. The holdout tests showed keyword rules generalise poorly (unseen set: 8/17, 2 silent wrong approvals) while hosted Jev reads intent well
- **Chosen:** `KEV_MODE=led` with `KEV_PROVIDER=jev` (hosted TypeSafe `jev-latest`, key in `.env`). Jev's purpose answer (K1) can reject a prohibited purpose the keywords missed (confidence ≥ 0.50, not negated) and turn a keyword rejection it reads as harmless (≥ 0.70) into a review, except when the request contains text addressing the system (S-061), where the keyword rejection stands; it never approves on its own; its other answers (K2–K6, K6 new: "could the results identify people?") only flag on disagreement. Keyword rules stay as the floor. Every answer names the mode "Jev-led" and logs the Jev version. Code default stays `off`; `make dev` / `make seed` default to Jev-led for the demo (30 Oct)
- **Why:** unseen holdout 2: 16/17 as expected, 0 silent wrong approvals (rules only 8/17, 2 silent); R01–R10 unchanged (10/10, 6/6, 0 flags)
- **Alternatives:** self-hosted Kev in the same mode (S-086: named, not deployed); rules only
- **Known costs:** request text (incl. applicant names) goes to TypeSafe; the app is an AI system under the AI Act in this mode; results can change with TypeSafe's model version; R06's review flag varies between runs (decision stable); ~1.8 s per request
- **To discuss:** data safety and AI Act review before any use beyond the demo

### D-09 · The definition check uses the WHO file and, when enabled, a hosted model · open
- **Milestone:** M-27
- **Specs:** S-070 ("a curated table"), S-052, S-054 (S-084 and S-085 allow the hosted model)
- **Conflict:** S-070 names a curated table with an advisory note only. A table cannot cover every code, and a word match cannot judge meaning: on 66 test pairs the firm rules flagged 8/30 wrong codes
- **Chosen:** rules against the WHO ICD-10 file always run; with a model enabled it answers `match`, `broader` or `different` from WHO's wording (Jev: 29/30 wrong codes and 6/6 too-broad warned, 2/30 correct definitions warned, 66 hand-labelled pairs, not held out). A `wrong` or `unsure` warning is also a review reason, so a wrong code the rules cannot name still reaches an officer (cost: correct synonyms such as "Heart attack = I21" go to review in rules-only mode); the numbers still use the exact code (S-007) and the applicant can send anyway
- **Alternatives:** rules only (most wrong codes get just a soft note); Kev-4B (missed R03: 2/6 too-broad)
- **Known costs:** definitions and WHO wording go to TypeSafe in Jev modes; WHO holds the ICD-10 copyright and redistribution needs its permission, so the file is not in this repo and was removed from the branch history (README, "WHO ICD-10 file"); without it the app says ICD-10 codes were not checked
- **To discuss:** update S-070's wording on `master`; ask licensing@who.int whether the file may ship with the repo

### D-10 · No staff login in the demo · open
- **Milestone:** M-24 (removed)
- **Specs:** S-042
- **Conflict:** S-042 wants the register to record who did what; without accounts the officer name is self-declared
- **Chosen:** Noah's call: no login, every staff endpoint is open, the audit log records the typed officer name or `staff`
- **Why:** the demo is on synthetic data and the login added work without showing anything
- **Alternatives:** keep the one demo account (M-24, removed code is in git history)
- **Known costs:** anyone who can reach the backend can confirm or override decisions and read every application
- **To discuss:** accounts, and binding the backend to localhost, before any use beyond the demo

### D-11 · RStudio in the secure processing environment · open
- **Milestone:** M-29
- **Specs:** S-020, S-040, S-081, S-076, S-030, D-10
- **Conflict:** S-020 and S-081 block every download of records, but a live R session shows the records on screen, and the person is only the name in `?user=` (D-10)
- **Chosen:** Noah's call: one container per session (`rocker/rstudio`, AGPL-3; DuckDB driver, MIT) with `--network none`, the permit's file mounted read-only, no RStudio login (Noah's call, for a smooth demo), reached over a Unix socket through an nginx proxy bound to 127.0.0.1 that refuses RStudio's download routes. Opening and refusals are logged; an override to `REJECT` ends the session
- **Why:** researchers can work on the data directly, and the demo shows a real download from R failing. An internal Docker network was rejected because a session could still reach SSH on the host
- **Alternatives:** describe it as a next step only; a locked-down remote desktop
- **Known costs:** the browser must receive what it shows, so the screen, the clipboard and the browser's own traffic stay open and a determined user can still copy rows out; RStudio's `allow-file-downloads=0` does not close its `/files` and `/export` routes, the proxy does, and the Export menu entry stays visible but fails; what happens inside a session is not logged; one session at a time on one port; with no login, anyone who can reach the port (on the tailnet demo, every device on the tailnet) gets the session without the check or the log entry of S-040; the SPE file now uses the older storage format `v1.4.0` so the R driver can read it, and the image's driver version must keep up with it (test in `tests/test_rstudio.py`)
- **To discuss:** real logins and session auditing before any use beyond the demo

### D-12 · Applicants are not told what the data holds · open
- **Milestone:** none, found in the demo
- **Specs:** S-070, S-071, S-048
- **Conflict:** the pre-check told applicants which codes and years occur in the data and whether a population is empty, so drafts could be used to probe the data without a decision
- **Chosen:** findings that depend on the data are review reasons starting with `Data:`, for staff only, and do not change the pre-check's `needs_review`; the mismatch note keeps its data sentence in the answer and staff view (S-070) but not in the applicant's pre-check or view; a code is judged against WHO alone; names resolve from the hand-built table only, not from the data's columns
- **Alternatives:** publish a data catalogue so applicants may know this openly
- **Known costs:** an applicant whose code is absent from the data learns this only from staff; a name outside the hand-built table ("metformin") needs a code, otherwise it is unread and goes to review with no numbers
- **To discuss:** `POST /requests` returns the full answer unfiltered, including numbers before staff confirm
