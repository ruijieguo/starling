#!/usr/bin/env bash
# integration-test.sh — end-to-end check of the Starling OpenClaw memory plugin.
#
# Topology: Starling dashboard runs on the HOST (native _core.so), OpenClaw runs
# in a container and reaches the host via host.docker.internal. See README.md.
#
# Prerequisites (the script checks them and tells you what to do):
#   1. Host Starling dashboard running and bound to 0.0.0.0:
#        STARLING_DASH_HOST=0.0.0.0 .venv/bin/python scripts/run_dashboard.py
#   2. STARLING_TOKEN exported (from ~/.starling/starling.json).
#
# Usage:
#   STARLING_TOKEN=<token> [STARLING_PORT=8787] ./docker/integration-test.sh
#
# The token is read from the environment and passed through to the container at
# runtime; it is never written to the image or to git.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMPOSE=(docker compose -f "${HERE}/docker-compose.yml")
PORT="${STARLING_PORT:-8787}"
HOST_URL="http://127.0.0.1:${PORT}"      # how the HOST reaches its own dashboard
MARKER="docker-e2e-$(date +%s)"

red()   { printf '\033[31m%s\033[0m\n' "$*"; }
green() { printf '\033[32m%s\033[0m\n' "$*"; }
info()  { printf '\033[36m[it]\033[0m %s\n' "$*"; }

if [[ -z "${STARLING_TOKEN:-}" ]]; then
  red "STARLING_TOKEN is not set."
  echo "  export STARLING_TOKEN=\$(python3 -c \"import json,os;print(json.load(open(os.path.expanduser('~/.starling/starling.json')))['token'])\")"
  exit 2
fi
export STARLING_TOKEN STARLING_PORT="${PORT}"

auth=(-H "Authorization: Bearer ${STARLING_TOKEN}")

# Count statements via the host dashboard /api/overview (authoritative; the
# inspection /api/statements returns its rows under the "rows" key).
stmt_count() {
  curl -fsS "${auth[@]}" "${HOST_URL}/api/overview" \
    | python3 -c "import sys,json; print(json.load(sys.stdin).get('counts',{}).get('statements','ERR'))" 2>/dev/null \
    || echo "ERR"
}

# ---------------------------------------------------------------------------
info "0. Precondition: host dashboard reachable at ${HOST_URL}"
if ! curl -fsS "${auth[@]}" "${HOST_URL}/api/overview" >/dev/null 2>&1; then
  red "Host dashboard not reachable / token rejected at ${HOST_URL}/api/overview"
  echo "  Start it bound to 0.0.0.0 so the container can reach it too:"
  echo "    STARLING_DASH_HOST=0.0.0.0 STARLING_DASH_PORT=${PORT} .venv/bin/python scripts/run_dashboard.py"
  exit 2
fi
green "  host dashboard OK"

before="$(stmt_count)"
info "  statements before: ${before}"

# ---------------------------------------------------------------------------
info "1. Build (if needed) + start the OpenClaw container"
# Build only when the image is missing or BUILD=1 is set. The `FROM node:22-slim`
# metadata re-resolution intermittently fails with a Docker Hub EOF; retry a few
# times. Once built, plain `up -d` reuses the local image (no registry round-trip).
if [[ "${BUILD:-0}" == "1" ]] || ! docker image inspect starling-openclaw-integration:latest >/dev/null 2>&1; then
  info "  building image (set BUILD=1 to force a rebuild)"
  for a in 1 2 3 4 5; do
    if "${COMPOSE[@]}" build; then break; fi
    red "  build attempt ${a} failed (transient Docker Hub EOF?); retrying…"; sleep 8
  done
fi
"${COMPOSE[@]}" up -d
trap '"${COMPOSE[@]}" logs --no-color | tail -40; "${COMPOSE[@]}" down -v >/dev/null 2>&1 || true' EXIT

info "  entrypoint config (token redacted):"
"${COMPOSE[@]}" logs --no-color openclaw 2>/dev/null | grep -E "\[entrypoint\]" || true

# ---------------------------------------------------------------------------
info "2. Verify the plugin loads with no error (plugins.slots.memory=starling)"
# `plugins inspect` reads discovery/manifest/config without a live gateway.
if "${COMPOSE[@]}" exec -T openclaw openclaw plugins inspect starling 2>&1 | tee /tmp/oc-inspect.txt | grep -qiE "starling"; then
  green "  plugin 'starling' discovered"
  grep -iE "memory|slot|enabled|error|invalid|missing" /tmp/oc-inspect.txt | head -20 || true
else
  red "  plugin 'starling' NOT discovered — see output above"
  "${COMPOSE[@]}" exec -T openclaw openclaw plugins list 2>&1 | head -40 || true
fi

# ---------------------------------------------------------------------------
info "3. Round-trip: container plugin -> host dashboard (remember/recall via host.docker.internal)"
"${COMPOSE[@]}" exec -T -e RT_MARKER="${MARKER}" openclaw node /opt/starling-plugin/roundtrip.mjs

after="$(stmt_count)"
info "  statements after: ${after} (before ${before})"
if [[ "${before}" != "ERR" && "${after}" != "ERR" && "${after}" -gt "${before}" ]]; then
  green "  WRITE VERIFIED: statement count increased (${before} -> ${after})"
else
  red "  WRITE NOT confirmed via count (before=${before} after=${after}); checking marker directly"
  curl -fsS "${auth[@]}" "${HOST_URL}/api/statements?limit=1000" | grep -c "${MARKER}" && green "  marker present in statements" || red "  marker NOT found"
fi

# ---------------------------------------------------------------------------
info "4. Downgrade test: dashboard unreachable -> reads degrade, writes queue, then flush"
"${COMPOSE[@]}" exec -T openclaw env \
  STARLING_DASHBOARD_URL="http://host.docker.internal:1" \
  STARLING_REAL_URL="http://host.docker.internal:${PORT}" \
  node /opt/starling-plugin/downgrade.mjs || true

green "ALL DONE. Marker=${MARKER}"
echo "Inspect the captured memory in the dashboard UI: ${HOST_URL}/#token=<your token>"
