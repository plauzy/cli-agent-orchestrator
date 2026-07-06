#!/usr/bin/env bash
#
# Drive the LIVE AG-UI generative-UI path against a running cao-server.
#
# Emits all six allow-listed components via POST /agui/v1/emit_ui (each -> a
# GENERATIVE_UI frame on the SSE stream) plus one OFF-LIST component (iframe)
# which the server-side allow-list refuses with HTTP 400 — proving an untrusted
# agent cannot inject arbitrary markup. Meanwhile it tails GET /agui/v1/stream
# so you can see the real frames the dashboard renders.
#
# Requires: ./run.sh already running (or any cao-server with CAO_AGUI_ENABLED).
#
# Usage:
#   ./examples/agui-dashboard/showcase.sh
#   CAO_AGUI_BASE=http://localhost:9889 ./examples/agui-dashboard/showcase.sh

set -euo pipefail

BASE="${CAO_AGUI_BASE:-http://localhost:9889}"
STREAM="${BASE}/agui/v1/stream"
EMIT="${BASE}/agui/v1/emit_ui"

command -v curl >/dev/null 2>&1 || {
    echo "curl is required" >&2
    exit 1
}
if ! curl -fsS "${BASE}/health" >/dev/null 2>&1; then
    echo "cao-server not reachable at ${BASE} — start it first:" >&2
    echo "  ./examples/agui-dashboard/run.sh" >&2
    exit 1
fi

FRAMES="$(mktemp -t agui-frames.XXXXXX)"
EMIT_OUT="$(mktemp -t agui-emit.XXXXXX)"
TAIL_PID=""
cleanup() {
    [ -n "${TAIL_PID}" ] && kill "${TAIL_PID}" >/dev/null 2>&1 || true
    rm -f "${FRAMES}" "${EMIT_OUT}"
}
trap cleanup EXIT INT TERM

# Tail the SSE stream in the background for the duration of the showcase.
curl -N -fsS "${STREAM}" >"${FRAMES}" 2>/dev/null &
TAIL_PID=$!
sleep 1 # let the STATE_SNAPSHOT + subscription establish

ok=0
refused=0

emit() {
    local name="$1" props="$2"
    local code
    code=$(curl -s -o "${EMIT_OUT}" -w '%{http_code}' -X POST "${EMIT}" \
        -H 'content-type: application/json' \
        -d "{\"component\":\"${name}\",\"props\":${props}}")
    printf '  %-14s -> HTTP %s  %s\n' "${name}" "${code}" "$(cat "${EMIT_OUT}")"
    if [ "${code}" = "200" ]; then ok=$((ok + 1)); fi
    if [ "${name}" = "iframe" ] && [ "${code}" = "400" ]; then refused=1; fi
}

echo "[showcase] emitting the six allow-listed components:"
emit approval_card '{"title":"Deploy to prod?","detail":"3 files, 1 migration","risk":"high"}'
emit choice_prompt '{"question":"Pick a branch","choices":[{"label":"main","value":"main"},{"label":"release","value":"release"}]}'
emit diff_summary '{"title":"PR #387 reshape","files":[{"path":"a2a/rpc.py","additions":74,"deletions":3}]}'
emit progress '{"label":"Indexing repo","value":0.42}'
emit metric '{"label":"tokens","value":12840,"unit":"tok"}'
emit agent_card '{"name":"worker-1","provider":"kiro_cli","status":"working"}'

echo "[showcase] emitting an OFF-LIST component (must be refused 400):"
emit iframe '{"src":"https://evil.example"}'

sleep 1
echo
echo "[showcase] AG-UI frames captured from ${STREAM}:"
grep -aE '^event:|GENERATIVE_UI|rejected_component' "${FRAMES}" | head -40 || true

echo
if [ "${ok}" -eq 6 ] && [ "${refused}" -eq 1 ]; then
    echo "[showcase] PASS: 6 components accepted (HTTP 200), iframe refused (HTTP 400)."
else
    echo "[showcase] UNEXPECTED: accepted=${ok}/6, iframe_refused=${refused} (expected 6 and 1)." >&2
    exit 1
fi
