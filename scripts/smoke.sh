#!/usr/bin/env bash
# "Does each tool run on this machine?" — no product logic.
# Prints PASS / FAIL / SKIP per test.
# Usage: bash scripts/smoke.sh [-v]
# Config comes from ./.env (see .env.example); services default to localhost.
set -uo pipefail
cd "$(dirname "$0")/.."
unset PYTHONPATH  # a PYTHONPATH from the shell profile (e.g. ROS) breaks the 3.11 venvs

VERBOSE=0
for a in "$@"; do case $a in -v) VERBOSE=1 ;; esac; done

ENV_FILE="${ENV_FILE:-.env}"
[ -f "$ENV_FILE" ] && { set -a; source "$ENV_FILE"; set +a; }
export OLLAMA_GENERAL_MODEL="${OLLAMA_GENERAL_MODEL:-gemma4:12b}"
FHIR="${FHIR_BASE:-http://localhost:8080/fhir}"
OLLAMA="${OLLAMA_URL:-http://localhost:11434}"
OUT=smoke-out; mkdir -p "$OUT/logs"
declare -A RESULTS; ORDER=()

run() { # group name cmd...
  local group=$1 name=$2; shift 2
  local log="$OUT/logs/$name.log" status
  "$@" >"$log" 2>&1
  case $? in 0) status=PASS ;; 77) status=SKIP ;; *) status=FAIL ;; esac
  RESULTS["$group|$name"]="$status|$(grep -v '^\s*$' "$log" | tail -n 1 | cut -c1-90)"
  ORDER+=("$group|$name")
  printf '  %-4s %-18s %s\n' "$status" "$name" "$(grep -v '^\s*$' "$log" | tail -n 1 | cut -c1-90)"
  [ $VERBOSE = 1 ] && sed 's/^/        /' "$log"
}
py() { uv run --quiet python "scripts/smoke/$1"; }
hapi() {
  v=$(curl -sf "$FHIR/metadata" | jq -r .fhirVersion) || { echo "SKIP: HAPI not reachable at $FHIR (optional, make fhir-up)"; return 77; }
  echo "fhirVersion=$v"; [ "$v" = 4.0.1 ]
}
ollama_gen() {
  curl -sf "$OLLAMA/api/tags" >/dev/null || { echo "SKIP: Ollama not reachable at $OLLAMA (optional)"; return 77; }
  curl -sf "$OLLAMA/api/generate" -d "{\"model\":\"$OLLAMA_GENERAL_MODEL\",\"prompt\":\"Say hello.\",\"stream\":false,\"think\":false}" \
    | jq -er .response | tr '\n' ' '
}
track3_data() {
  n=$(ls "${TRACK3_DATA:-data/track3}"/requests/R*.json 2>/dev/null | wc -l)
  echo "$n requests, $(($(wc -l < "${TRACK3_DATA:-data/track3}"/data/patients.csv) - 1)) patients"; [ "$n" -eq 10 ]
}
pytest_run() { uv run --quiet pytest -q | tail -n 1; return "${PIPESTATUS[0]}"; }

echo "== core"
run core track3-data     track3_data
run core pytest          pytest_run
echo "== models"
run llm kev              py kev.py
run llm ollama           ollama_gen
echo "== optional"
run opt hapi             hapi

fails=0; for k in "${ORDER[@]}"; do [[ ${RESULTS[$k]} == FAIL* ]] && fails=$((fails+1)); done
echo "== $fails failing (logs in $OUT/logs/)"
exit $((fails > 0))
