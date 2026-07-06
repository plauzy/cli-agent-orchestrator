#!/usr/bin/env bash
#
# AG-UI dashboard demo: launches a small mock_cli fleet against a running
# cao-server (started with CAO_AGUI_ENABLED=true), drives the generative-UI
# showcase, and leaves the stream up for a dashboard to render.
#
#   0 — fleet launched and showcase completed
#   1 — precondition failed (server down, AG-UI disabled, tmux missing)
#
# Usage:
#   CAO_AGUI_ENABLED=true uv run cao-server        # terminal 1
#   ./run.sh                                        # terminal 2
#   curl -N http://localhost:9889/agui/v1/stream    # terminal 3 (or open cao_pwa)
#
# The mock_cli binary is a test fixture (deterministic echo REPL, no
# credentials); this script puts it on PATH for the demo only — production
# installs never ship it on PATH.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
CAO_URL="${CAO_URL:-http://localhost:9889}"
SESSION_NAME="agui-demo-$$"
PREFIXED="cao-${SESSION_NAME}"

export PATH="${REPO_ROOT}/test/providers/fixtures/bin:${PATH}"

command -v tmux >/dev/null || { echo "[demo] tmux is required" >&2; exit 1; }
command -v mock_cli >/dev/null || { echo "[demo] mock_cli fixture not found" >&2; exit 1; }

# Preconditions: server up, AG-UI surface enabled (404 = flag not set).
curl -sf "${CAO_URL}/health" >/dev/null || {
    echo "[demo] cao-server not reachable at ${CAO_URL} — start it first" >&2; exit 1; }
STREAM_CODE=$(curl -s -o /dev/null -w '%{http_code}' -m 3 "${CAO_URL}/agui/v1/stream?since=2999-01-01T00:00:00Z" || true)
if [ "${STREAM_CODE}" = "404" ]; then
    echo "[demo] AG-UI surface is disabled — restart the server with CAO_AGUI_ENABLED=true" >&2
    exit 1
fi

cleanup() {
    local code=$?
    cao shutdown --session "${PREFIXED}" >/dev/null 2>&1 || true
    exit "${code}"
}
trap cleanup EXIT INT TERM

echo "[demo] installing the fleet_worker profile" >&2
cao install "${SCRIPT_DIR}/fleet_worker.md" >/dev/null

echo "[demo] launching a 2-worker mock fleet in session ${PREFIXED}" >&2
cao launch --agents fleet_worker,fleet_worker \
    --async --yolo \
    --session-name "${SESSION_NAME}" \
    "Demo fleet for the AG-UI dashboard."

echo "[demo] fleet is up — driving the generative-UI showcase" >&2
CAO_URL="${CAO_URL}" "${SCRIPT_DIR}/showcase.sh"

echo "[demo] open the dashboard now (cao_pwa: npm run dev) or watch raw frames:" >&2
echo "[demo]   curl -N ${CAO_URL}/agui/v1/stream" >&2
echo "[demo] press Enter to shut the fleet down" >&2
read -r || true
