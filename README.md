# EHDS Health Data Access Body

A prototype of a Health Data Access Body under the European Health Data Space (Reg. (EU) 2025/327, Chapter IV), built for
the AIM Healthcare Hackathon Vienna 2026, Track 3. It takes a data request, proposes `REJECT`, `APPROVE_STATISTICAL` or
`APPROVE_SPE` with the cited articles, computes small-cell-safe statistics or fills a secure processing environment, and
shows decision and reason to the applicant and the staff. Staff confirm or override every proposal.

Challenge: [`data/track3/README.md`](data/track3/README.md). Hard rules: [`SPECS.md`](SPECS.md). Trade-offs taken:
[`DECISIONS.md`](DECISIONS.md). Build log: [`MILESTONES.md`](MILESTONES.md).

> **Demo only, synthetic data only.** There are no logins: anyone who can reach the app can confirm or override decisions,
> read every application and open the secure environment (`DECISIONS.md` D-10, D-11). What a browser shows in RStudio can
> be copied out by hand. It has had no conformity assessment under the EU AI Act and holds no certification. Run it on
> localhost or a private network, and add real authentication before any other use.

## Repo layout
| Path | Contents |
|---|---|
| `data/track3/` | Official challenge: `README.md` (git submodule), 5 CSVs in `data/` (20,000 synthetic patients), 10 requests + `expected.json` in `requests/` |
| `src/hdab/contracts.py` | Pydantic shapes of a request and an answer |
| `src/hdab/data.py` | Data paths (`$TRACK3_DATA`, `$HDAB_VAR`) and loaders |
| `src/hdab/pipeline.py` | The single entry point: `decide` (pure) and `submit` / `confirm` / `override` (register, SPE) |
| `src/hdab/rules.py` | Deterministic decision rules: Art. 54 lexicon, request type, SPE justification, reasons, trace |
| `src/hdab/plan.py`, `vocab.py` | Definitions → query plan; plain-English names → ICD-10 / ATC / LOINC; mismatch notes |
| `src/hdab/stats.py` | Query plan → small-cell-safe statistics or the exact SPE cohort |
| `src/hdab/spe.py` | Secure processing environment: one DuckDB file per permit, data permit, blocked downloads |
| `src/hdab/register.py`, `views.py` | Register and audit log (SQLite); what applicant and staff see |
| `src/hdab/sql.py` | The query plan as SQL for the audit log, checked against the computed numbers |
| `src/hdab/explain.py` | What each rule is, why something was flagged, what staff should check |
| `src/hdab/rstudio.py` | RStudio in the secure environment: a container with no network, data read-only |
| `src/hdab/definitions.py`, `icd10.py`, `sanity.py` | Do codes fit their names (WHO ICD-10), do definitions fit the data |
| `src/hdab/assist.py` | Optional writing help on the applicant form |
| `src/hdab/kev.py` | Optional decision model: hosted Jev or local Kev-4B (off by default) |
| `src/hdab/api.py` | FastAPI app; endpoints in [`docs/API.md`](docs/API.md) |
| `frontend/` | React screens for applicant, staff and secure environment: [`frontend/README.md`](frontend/README.md) |
| `docker/` | Images for RStudio and its proxy (`make spe-image`), and the tailnet demo's web server |
| `scripts/` | `metrics.py`, `redteam.py`, `compare_modes.py`, smoke tests, `kev.sh`, `demo.sh` |
| `tests/` | pytest; `tests/redteam/cases.json` = own red-team and paraphrase requests |

## Setup (Linux/macOS; Windows below)
Needs: `uv`. Optional: Docker (HAPI FHIR), `jq` + `curl` (smoke tests), Ollama.
```bash
git clone --recursive https://github.com/noah-stockinger/ehds-access-body.git  # pulls data/track3 submodule
git submodule update --init      # already cloned without --recursive? run this instead
uv sync                          # venv
cp .env.example .env             # service locations (all optional)
```

### Windows: clone and pull with the submodule
`data/track3` is a git submodule (the official challenge repo). Use **Git for Windows** in PowerShell or Git Bash:
```powershell
git clone --recurse-submodules https://github.com/noah-stockinger/ehds-access-body.git
cd ehds-access-body
git config submodule.recurse true          # once per clone: every `git pull` / `git checkout` also updates data/track3
```
Pulling later:
```powershell
git pull                                   # with submodule.recurse=true, this is enough
git submodule update --init --recursive    # without it, or if data/track3 is empty
```
- **Cloned before the submodule switched to HTTPS?** Run `git submodule sync` once, then `git submodule update --init --recursive`.
- **Check it worked:** `git submodule status` shows a commit hash without a leading `-`, and `data/track3/requests/` holds `R01.json`–`R10.json`.
- **Line endings:** keep Git for Windows' default (`core.autocrlf=true`); the CSVs and JSON parse fine either way.
- **Encoding:** read the data as UTF-8 (region names like `Kärnten`). `hdab.data` already does; in your own code pass
  `encoding="utf-8"` to `open()` / `read_text()` / `pd.read_csv()`, or set `PYTHONUTF8=1`.
- `make` and the bash smoke script need Git Bash or WSL; the `uv run ...` commands behind each target work in PowerShell too.

## Run
```bash
make test                    # pytest
make dev KEV_MODE=off        # rules only, no API keys or model needed; API on :8000, docs at /docs, endpoints in docs/API.md
make dev                     # Jev-led demo mode: needs TYPESAFE_API_KEY in .env (D-08)
make metrics                 # R01–R10 against expected.json, 3 runs (S-029)
make redteam                 # own red-team and paraphrase cases (S-060)
make jury                    # jury simulation: new, messy and broken requests (docs/findings/jury-simulation.md)
make compare                 # Kev off vs. Kev-assisted (S-069; needs Kev)
make smoke                   # which tools are ready on this machine
make spe-image               # build the RStudio images (Docker); needed for "Open RStudio"
```
Frontend (Vite, :5173): `make seed` (`make seed KEV_MODE=off` without a key), then `cd frontend && npm install && npm run dev`; screens, demo walkthrough and Mac tunnel in [`frontend/README.md`](frontend/README.md).
Try one request: `curl -s localhost:8000/requests -H 'content-type: application/json' -d @data/track3/requests/R01.json`.
Clean slate for the demo: `curl -X POST localhost:8000/demo/reset` puts R01–R10 back as proposals and deletes everything else: submitted applications, staff decisions, SPEs and the audit log. It takes as long as `make seed` and needs no restart.
Runtime state (register, SPE files) goes to `var/` (gitignored, `$HDAB_VAR`).

## Architecture
Rules decide, Kev (optional) double-checks, staff have the last word. Anything not understood is flagged
`needs_review` and gets no numbers; the app never guesses.
```
request JSON ──▶ POST /requests  or  guided form (/form/precheck → /form/submit)
  │
  ├─ rules.py   1 prohibited purpose? (Art. 54 lexicon over purpose, question, definitions; negation/quotes → review)
  │             2 health data request → statistics (Art. 53, 69)
  │             3 access application that says why statistics are not enough → SPE (Art. 53, 66, 68, 73)
  │             4 other access application → statistics (Art. 53, 66, 69)          ⇒ decision, articles, reason, trace
  ├─ plan.py    definitions → query plan (terms, code prefixes, bands, groups, measures); every word must be claimed,
  │             else needs_review; plain-English rendering for applicant and staff; vocab.py maps names to codes
  ├─ stats.py   pandas over the CSVs: opt-outs out first, <10 / suppressed, one decimal halves up, all groups shown
  ├─ spe.py     APPROVE_SPE: cohort + requested record types → var/spe/<id>.duckdb, data permit, download always 403
  ├─ kev.py     only with KEV_ENABLED=true: typed questions K1–K5 to local Kev-4B; disagreement or low confidence → review
  └─ register   SQLite register + audit log; numbers and SPE released to the applicant only after staff confirm
```
Models and services: the only outbound calls go to the enabled models, hosted Jev or local Kev-4B
(`POST $KEV_BASE_URL/v1/systemone`) and the writing help (hosted Claude, or `$ASSIST_URL` with Ollama), with request text only (S-022, S-084, S-087). Data: the 5 CSVs, read with pandas; SPE copies in DuckDB.

## Results
`make metrics` (Rules only, the default):

| | R01 | R02 | R03 | R04 | R05 | R06 | R07 | R08 | R09 | R10 |
|---|---|---|---|---|---|---|---|---|---|---|
| decision + articles | ok | ok | ok | ok | ok | ok | ok | ok | ok | ok |
| numbers | ok | – | ok | – | ok | – | ok | ok | ok | – |

Decisions 10/10 · numbers 6/6 · leaks 0 · same in 3 runs 10/10 · slowest 0.06 s. `make redteam`: 30/30 as expected,
0 silent wrong approvals, 0 wrong numbers.
`make jury` (49 unseen jury-style cases, expected outcomes written first, numbers from an independent oracle): new 14/14,
messy 18/18, broken or nonsensical 17/17, 0 silent wrong approvals, 0 wrong numbers, 0 leaks
([`docs/findings/jury-simulation.md`](docs/findings/jury-simulation.md)).

`make compare` (S-069):

| metric | Rules only | Kev-assisted |
|---|---|---|
| decisions (10) | 10 | 10 |
| numbers (6) | 6 | 6 |
| R01–R10 flagged for review | 0 | 10 |
| red team as expected | 30/30 | 22/30 |
| silent wrong approvals | 0 | 0 |
| same in 3 runs | 10 | 10 |
| slowest | 0.06 s | 0.43 s |

Kev agrees with the rules on whether a purpose is prohibited 10/10, but its confidences are low (median 0.48 for the
category question), so at the 0.80 threshold every request is flagged. **Rules only ships as the default** (`DECISIONS.md` D-06).

### Jev-led mode (`DECISIONS.md` D-08)
`KEV_MODE=led KEV_PROVIDER=jev` (key `TYPESAFE_API_KEY` in `.env`): hosted Jev reads the purpose and can reject what the
keywords miss; it never approves alone, and keyword rules stay as the floor. `scripts/compare_led.py`:

| | Rules only | Jev-led |
|---|---|---|
| R01–R10 decisions / numbers / flagged | 10/10 · 6/6 · none | 10/10 · 6/6 · none |
| red team (30, tuned on) | 30/30, 0 silent | 28/30, 0 silent |
| holdout 1 (17, rules tuned after) | 15/17, 0 silent | 15/17, 0 silent |
| **holdout 2 (17, unseen)** | **8/17, 2 silent** | **16/17, 0 silent** |
| slowest request | 0.06 s | 1.8 s |

"Silent" = a wrong approval without a review flag. Not as expected in Jev-led: harmless studies that contain a
prohibited word (tobacco cessation, research on premiums, on marketing of sugary drinks) go to review instead of
approval, by design; one R09 paraphrase is flagged by the new "could identify people" question. In this mode request
text goes to TypeSafe and the app is an AI system under the AI Act; both are parked until the base is strong.

## WHO ICD-10 file (not in this repo)
The definition check (M-27, `src/hdab/definitions.py`) compares ICD-10 codes with WHO's wording. WHO holds the copyright
and redistribution needs its permission, so `data/icd10/` is gitignored and the file must never be committed.

1. Get the English ICD-10 2019 ClaML file (`icd102019en.xml`) from WHO via <https://icd.who.int/browse10>; WHO's terms apply to your copy.
2. Put it at `data/icd10/icd102019en.xml`, or set `ICD10_XML` to its path.

Without it the app still runs and gives the same decisions and numbers, but it says ICD-10 codes were not checked: no
warning on R03, no wrong-code warnings, and the model is not asked. The tests that need the file are skipped.

## Licences (S-085)
| Component | Licence |
|---|---|
| duckdb | MIT |
| fastapi, pydantic, rich, pytest, ruff | MIT |
| pandas, numpy, httpx, uvicorn, starlette, python-dotenv | BSD-3-Clause (numpy also 0BSD, MIT, Zlib parts) |
| Kev server code (`jaredpalmer/kev`, optional) | Apache-2.0 |
| Kev-4B weights `jaredpalmer/kev-4b@v1.0` (optional) | Apache-2.0 (S-031) |
| Qwen3.5-4B-Base, Kev's base model (optional) | ⏳ not verified yet |
| NVIDIA CUDA runtime libraries used by Kev (optional) | ⏳ proprietary; open question against S-085 |
| TypeSafe Jev (hosted, optional) | closed model, exempt under S-085 (S-084) |
| Claude Opus 5.5 (hosted, writing help, optional) | closed model, exempt under S-085 (S-084) |
| anthropic Python SDK | MIT |
| Ollama (writing help, self-hosted option) | MIT |
| `qwen3.8:27b` weights (writing help, self-hosted option) | Apache-2.0 |
| WHO ICD-10 2019 (`data/icd10/`, optional, not in this repo) | © WHO; redistribution needs WHO's permission |
| RStudio Server (optional, Docker image) | AGPL-3.0 |
| nginx (optional, Docker image) | BSD-2-Clause |

## Models
What we run ourselves is open source (S-085). Hosted models are allowed and receive request text only, never
patient-level data (S-084). To run without a hosted model, a self-hosted Kev-27B on one RTX PRO 6000 is the way; that
setup was not deployed or measured here (S-086).
- **Writing help (S-087):** "Help me write this" on the applicant form uses hosted Claude Opus 5.5 (self-hosted Qwen3.8 27B is an option) and
  explains the pre-check and drafts the question and definitions. The rules re-check every draft and it decides nothing; off
  unless `ASSIST_ENABLED=true`. Setup: [`docs/SETUP-assist.md`](docs/SETUP-assist.md).
- **Rules only is the code default:** with `KEV_MODE=off` the app uses only hand-written rules, with no machine-learned
  component (S-052, S-053). `make dev` and `make seed` turn on Jev-led mode for the demo (D-08), where a hosted model reads the purpose and the app is an AI system under the AI Act.
- **Kev-4B** (Apache-2.0) is the optional typed decision model (S-031). It runs as its own process on the GPU machine
  (RTX 4060 Ti, 16 GB), from <https://github.com/jaredpalmer/kev>:
  ```bash
  git clone https://github.com/jaredpalmer/kev && cd kev
  uv sync --extra serve
  uv run --extra serve python -m kev.serve --run jaredpalmer/kev-4b@v1.0 --port 8009
  ```
  The app calls `POST $KEV_BASE_URL/v1/systemone` (default `http://127.0.0.1:8009`). From another machine use
  `ssh -L 8009:127.0.0.1:8009 <gpu-host>`.
  On the GPU machine `scripts/kev.sh start|stop` runs it on demand. Don't `pip install kev`: that is an unrelated PyPI package.
- **Ollama (optional):** only models with Apache-2.0 or MIT weights, and only if they fit beside Kev.

## Ports
| Port | Service |
|---|---|
| 8000 | App backend (FastAPI) |
| 5173 | Frontend dev server (Vite, [`frontend/`](frontend/README.md)) |
| 8009 | Kev decision model (`/v1/systemone`), on the GPU machine |
| 8080 | HAPI FHIR server (`/fhir`, optional) |
| 11434 | Ollama (optional) |

