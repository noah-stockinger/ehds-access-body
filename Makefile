SHELL := /bin/bash
unexport PYTHONPATH  # a PYTHONPATH from the shell profile (e.g. ROS) breaks the 3.11 venvs
ENV_FILE ?= .env
# Set HOST=0.0.0.0 (e.g. in Makefile.local) to serve the app to other machines.
HOST ?= 127.0.0.1
OLLAMA_URL ?= http://localhost:11434
export OLLAMA_URL
# Personal overrides (gitignored).
-include Makefile.local

LOAD_ENV = set -a; [ -f $(ENV_FILE) ] && source $(ENV_FILE); set +a

.PHONY: dev test lint seed metrics redteam jury compare smoke fhir-up fhir-down spe-image

# Demo default: Jev-led (DECISIONS.md D-08); override with `make dev KEV_MODE=off` for rules only.
# Tests and metric scripts keep the code default (off).
dev seed: export KEV_MODE ?= led
dev seed: export KEV_PROVIDER ?= jev
dev: export ASSIST_ENABLED ?= true

dev:            ## FastAPI backend on :8000 (Jev-led by default, see above)
	uv run uvicorn hdab.api:app --reload --host $(HOST) --port 8000

test:
	uv run pytest -q

redteam:        ## own red-team and paraphrase cases (S-060)
	uv run python scripts/redteam.py

jury:           ## jury simulation: new, messy and broken requests (tests/jury/)
	uv run python scripts/jury.py

compare:        ## Kev off vs. Kev-assisted (S-069; needs Kev for the second column)
	KEV_ENABLED=true uv run python scripts/compare_modes.py

seed:           ## R01–R10 into the register for the frontend (proposals, Jev-led by default)
	uv run python scripts/seed_demo.py

metrics:        ## R01–R10 against expected.json, 3 runs (S-029)
	uv run python scripts/metrics.py

lint:
	uv run ruff check src tests scripts

smoke:          ## does every tool run on this machine?
	bash scripts/smoke.sh

spe-image:      ## RStudio and proxy images for the secure processing environment (M-29)
	docker build -t hdab-rstudio:latest docker/rstudio
	docker build -t hdab-rstudio-proxy:latest docker/rstudio-proxy

fhir-up:        ## optional: empty HAPI FHIR R4 server on :8080 (only if a solution converts to FHIR)
	docker compose up -d hapi

fhir-down:
	docker compose down
