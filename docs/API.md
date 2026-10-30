# API — for the frontend

Backend: `make seed` (R01–R10 into the register) then `make dev` → <http://127.0.0.1:8000>, interactive docs at `/docs`.
CORS allows `http://localhost:5173` (Vite); other origins via `CORS_ORIGINS`. All bodies are JSON. Every screen of the demo
reads one of these endpoints; the frontend only renders. Shapes: `src/hdab/contracts.py` (`Request`, `Answer`) and `src/hdab/views.py`.

| Endpoint | Screen | Returns |
|---|---|---|
| `POST /requests` | jury / access-body intake (raw `R*.json`) | full `Answer` incl. numbers, trace, review reasons, signals (see `DECISIONS.md` D-05) |
| `POST /precheck` | form: "check my draft" | `notice`, `likely_decision`, `articles`, `reason`, `needs_review`, `review_reasons`, `plan_text`, `notes`, `definition_warnings`, `unclaimed_words`; no register entry, no numbers (S-048) |
| `POST /form/precheck` | same, from the form body | as above |
| `GET /form/assist` | is the writing help on? | `{enabled}` |
| `POST /form/assist` | AI help for an unfinished draft (S-087); stores nothing, 503 if off or down | `{model, message, suggestion: {question, definitions} or null, left_out, check}`; `check` is the pre-check of the suggestion |
| `POST /form/submit` | form: submit | applicant view (below); 422 if an access application lacks `why_statistics_not_enough` (S-049), `plan_confirmed` is false (S-057), or the definitions have `wrong` or `check` warnings and `warnings_confirmed` is false (S-070) |
| `GET /applicant/requests/{id}` | applicant: my application and decision | `status`, `status_text`, `request` (the application as submitted), `decision`, `articles`, `reason`, `steps` (short trace), `plan_text`, `notes`, `mode`, `ai_note`, `duties`; `answer` and `permit` are `null` until staff confirm, with a `withheld` text |
| `GET /applicant/requests/{id}/results.csv` | applicant: export | the released statistics as CSV, `<10` and `suppressed` unchanged; 404 before staff confirm, for a rejection and for an SPE |
| `GET /applicant/requests` | applicant: list (demo, no applicant accounts) | `[{id, received, organisation, requested_as, status, decision}]`; `decision` is `null` while proposed, so a proposal stays hidden |
| `GET /staff/queue` | staff: queue | `[{id, received, organisation, decision, needs_review, status, mode}]` |
| `GET /staff/requests/{id}` | staff: one request | `request`, `answer` (full: `trace`, `review_reasons`, `signals`, `plan_text`, `notes`, `unclaimed_words`, `permit`), `proposal` (the app's original), `status`, `staff`, `received`, `decided`, `log` |
| `POST /staff/requests/{id}/confirm` `{staff?}` | staff: confirm | the confirmed `Answer`; releases numbers and SPE access |
| `POST /staff/requests/{id}/override` `{staff, decision, reason, articles}` | staff: override | the new `Answer`; leaving `APPROVE_SPE` deletes the SPE (logged); moving to `APPROVE_SPE` creates one |
| `POST /demo/reset` | none (demo clean slate) | `{requests: [ids]}`; only R01–R10 remain, as proposals; deletes other applications, staff decisions, SPEs and the audit log |
| `GET /register/{id}/log` | staff: audit log | `[{ts, actor, action, detail}]`: one entry per rule step (`rule_checked`), model answer with its instructions and input (`model_answered`), `definitions_read`, `definition_warning`, `review_reason`, `signal`, `numbers_computed`, the SQL behind the numbers with whether it reproduces them (`query_run`), `decided`, and every staff and SPE action. Never numbers (S-071) |
| `GET /spe/{id}?user=` | SPE screen + proof panel | `{permit, proof: {cohort_size, tables, opted_out_ids_inside}}`; 403 before confirm or for a user not in the permit (logged) |
| `POST /spe/{id}/rstudio?user=` | the "Open RStudio" button | `{url}`, no login (D-11); same checks as the SPE screen (logged); 503 if Docker or the image is missing (`make spe-image`) |
| `GET /spe/{id}/download?user=` | the "Download" button | always 403 with the Art. 73 text (logged) |

**No login** (demo, D-10): every endpoint is open. The SPE still checks the permit name in `?user=`.
The officer name in `{staff}` is optional and self-declared; the audit log records it, or `staff` without one.

Form body (`POST /form/submit`): `{id?, applicant: {name, organisation, country}, requested_as, requested_format?, purpose,
question, definitions: [..], why_statistics_not_enough?, plan_confirmed, warnings_confirmed?}`. Flow: `/form/precheck` → show `plan_text` →
applicant ticks "plan is right" → `/form/submit` with `plan_confirmed: true`.

Demo walk (all with R01–R10 from `data/track3/requests/`):
1. R02 → `POST /requests` → `REJECT`, reason names Art. 54(1)(b); applicant view has no numbers and no duties.
2. R01 → applicant view withholds numbers → staff confirm → applicant view shows the 9 regions.
3. R05 → staff confirm → `GET /spe/R05?user=<applicant name>` shows the proof panel → download → 403 → log shows the attempt.
4. Staff override R05 to `REJECT` → SPE gone, log names the officer.

## Fields worth showing
- `mode`: `"Rules only"` (default), `"Jev-led"` / `"Kev-led"` (a model read the purpose, D-08), `"Kev-assisted"`, or
  `"Rules only (Jev unreachable)"`. Show it on every staff screen and register entry (S-055).
- `ai_note` (applicant view): a sentence to show when a model helped; `null` in rules-only mode.
- `trace`: ordered steps `{rule, matched, evidence}`: the "why" panel for staff; `steps` is the short applicant version.
  A step whose rule starts with `"1b decision model"` means the model changed the outcome: `matched: true` = it rejected
  what the keywords missed; `matched: false` = it overruled a keyword rejection (decision is an approval) or was itself
  overruled because of an injection (decision stays `REJECT`). The staff screen shows it as a callout.
- `review_reasons`: why staff must look (flag shown in the queue as `needs_review`); not in the applicant view. `POST /precheck` returns them without the `Data:` ones and counts only the rest for its `needs_review`, so a draft cannot be used to probe what the data holds; for the same reason its notes and warnings leave out whether codes occur in the data.
- `signals`: staff-only hints (e.g. "Organisation looks like: insurer"); change nothing.
- `definition_warnings`: `[{severity, definition, message}]`, a name and code that do not seem to agree (S-070, `src/hdab/definitions.py`): `wrong` (also a review reason), `check`, or `unsure` (also a review reason, needs no confirmation). The numbers still use the exact code. `POST /requests` is not gated; its answer carries them.
- `plan_text`: the query plan in plain English (show next to the original `definitions`); `notes`: inferred codes and
  definition mismatches (R03's I48 note); `unclaimed_words`: words the parser did not understand (highlight them).
- `kev`: staff only, empty in rules-only mode; one entry per model question:
  `{question, answer, model, confidence, rules, agrees}`
  - `question`: `"K1_category"` … `"K6_identifies_people"`
  - `answer`: the model's raw answer object, `{type: "choice", choice, confidence, probabilities}` (K1) or `{type: "noul", noul}` (yes probability)
  - `model`: model version, e.g. `"jev-1.14.0"`; `confidence`: 0.5–1 (choice: its confidence; yes/no: distance from 0.5)
  - `rules`: what the rules concluded: a list of categories (K1), a bool, or `null` when the question does not apply
  - `agrees`: bool, or `null` when there is nothing to compare
- `permit`: the data permit of an SPE (persons, duration, data, conditions, fees).
- Small cells come as the strings `"<10"` and `"suppressed"`; render them as such, never as 0.

## Modes for the demo
`make dev` and `make seed` run **Jev-led by default** (needs `TYPESAFE_API_KEY` in `.env`; without it every answer says
"Rules only (Jev unreachable)" and is flagged). Rules only: `make dev KEV_MODE=off`. Tests and scripts stay rules only.
The API shape is the same in every mode; a Jev-led request takes ~2 s, so show a loading state.
