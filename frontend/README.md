# Frontend — HDAB demo

React + TypeScript + Vite. Four screens for the M-14 walkthrough, built from the design canvas "HDAB Bildschirme".
The frontend only renders: every screen reads one endpoint of [`docs/API.md`](../docs/API.md), all decisions come from the backend.

## Run

```bash
# repo root: backend on :8000
make seed          # R01–R10 into the register, as proposals
make dev

# second terminal: frontend on :5173
cd frontend
npm install        # once
npm run dev
```

Open <http://localhost:5173>. The backend URL defaults to `http://127.0.0.1:8000`; set `VITE_API` to change it.
CORS on the backend allows `localhost:5173` and `127.0.0.1:5173` (other origins: `CORS_ORIGINS`).

### From another machine (e.g. a Mac)

Tunnel the ports over Tailscale (add `-L 8009:127.0.0.1:8009` if you also need Kev), then open <http://localhost:5173> on the Mac:

```bash
ssh -N -L 5173:127.0.0.1:5173 -L 8000:127.0.0.1:8000 -L 8787:127.0.0.1:8787 <gpu-user>@<gpu-host>
```

No code change needed: the browser calls `127.0.0.1:8000`, which the tunnel forwards.

### The demo for colleagues on the tailnet

`scripts/demo.sh start` serves one address, printed at the end, from its own worktree (`../<repo>-demo`) pinned to one commit, with its own register, so edits here do not touch it. It listens only on the Tailscale address (RStudio too), the backend only on localhost. `scripts/demo.sh seed` puts R01–R10 back to "proposed". To deploy a newer commit: `scripts/demo.sh stop`, `git worktree remove --force ../<repo>-demo`, `scripts/demo.sh start <commit>`; that also resets the register.

## Screens

The dark bar at the top switches between applicant and staff during the demo.

| Route | Role | Endpoints |
|---|---|---|
| `/apply` | Applicant: guided form, pre-check, submit or upload JSON; sent requests, coloured by outcome, to sort, filter and search | `POST /form/precheck`, `POST /form/assist`, `POST /form/submit`, `POST /requests` |
| `/applicant/:id` | Applicant: decision, reason, withheld notice, numbers, permit, duties, the application as submitted, CSV export of released statistics | `GET /applicant/requests/{id}` |
| `/staff`, `/staff/:id` | Staff: inbox and detail with trace, plan, review reasons, signals, model answers, audit log where every rule step and model answer opens; confirm / override | `GET /staff/queue`, `GET /staff/requests/{id}`, `POST …/confirm`, `POST …/override` |
| `/spe/:id?user=` | Permit holder, opened from the permit on `/applicant/:id`: permit, proof panel, RStudio, blocked download, activity log | `GET /spe/{id}`, `POST /spe/{id}/rstudio`, `GET /spe/{id}/download`, `GET /register/{id}/log` |

## Demo walkthrough (M-14)

1. `/staff/R02` → proposal REJECT, Art. 54(1)(b). `/applicant/R02`: no numbers, no duties.
2. `/applicant/R01` → numbers withheld. `/staff/R01`: optionally type an officer name in the header, **Confirm and release statistics**. `/applicant/R01`: 9 regions.
3. `/staff/R05` → **Confirm and issue data permit**. `/applicant/R05` → **Open the secure environment** → **Try to download the records** → refused (Art. 73), shown in the activity log. **Open RStudio** (once: `make spe-image`) → `DBI::dbGetQuery(con, "SELECT count(*) FROM conditions")` works, `download.file(...)` fails.
4. `/staff/R05` → **Override decision** → Reject, Art. 54, a reason → SPE deleted, RStudio session ended, the log names the officer.
5. `/apply` → choose **Pseudonymised records**, leave "why statistics are not enough" empty → **Check my draft** → refused.

### Clean state before recording

`curl -X POST localhost:8000/demo/reset` puts R01–R10 back as proposals and deletes everything else, the audit log too.
The backend keeps running. Plain `make seed` only resets R01–R10; the audit log keeps growing.

## Rules the UI keeps

- Small cells come as `"<10"` and `"suppressed"` and are shown as such, never as 0. Shares and means are shown with one decimal.
- Applicants never see `review_reasons`, `signals` or model answers; numbers and permit only after staff confirm (the backend enforces this, the UI only shows what it gets).
- `mode` is shown on every staff screen (S-055); `ai_note` to the applicant when a model helped.
- The officer name lives in `localStorage` (`officer`); every confirm and override is logged with it.

## Code

```
src/api.ts               fetch client and response types (mirror src/hdab/contracts.py, views.py)
src/ui.tsx               shared pieces: header, role bar, decision pill, numbers table, definitions, icons
src/pages/*.tsx          one file per screen
src/index.css            design tokens (:root) and all styles
```

`npm run build` type-checks and builds to `dist/`; `npm run lint` runs ESLint.

## Known limits

- The applicant portal lists every application in the register as "Sent Requests" (no per-applicant endpoint, no accounts).
- No accounts (D-10): the staff screen is open and the officer name is self-declared. The SPE user is a `?user=` parameter checked against the permit by the backend.
- No export review in the SPE (out of scope in the backend).
