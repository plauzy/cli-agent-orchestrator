#!/usr/bin/env bash
#
# Generative-UI showcase: drives POST /agui/v1/emit_ui through every
# allow-listed component (plus one off-list refusal) against a running
# cao-server, so a connected dashboard / AG-UI client renders the full
# component set live.
#
#   0 — all six components accepted AND the off-list component was refused
#   1 — any unexpected status from the server
#
# Usage:
#   ./showcase.sh                       # against http://localhost:9889
#   CAO_URL=http://host:9889 ./showcase.sh
#   CAO_TOKEN=<jwt> ./showcase.sh      # when auth is enabled (cao:write scope)
#
# Requires: cao-server running with CAO_AGUI_ENABLED=true. Watch the frames
# with:  curl -N "$CAO_URL/agui/v1/stream"

set -euo pipefail

CAO_URL="${CAO_URL:-http://localhost:9889}"
AUTH_ARGS=()
if [ -n "${CAO_TOKEN:-}" ]; then
    AUTH_ARGS=(-H "Authorization: Bearer ${CAO_TOKEN}")
fi

emit() {
    local component="$1" props="$2" expected="$3"
    local code
    code=$(curl -s -o /tmp/agui-showcase-resp.json -w '%{http_code}' \
        -X POST "${CAO_URL}/agui/v1/emit_ui" \
        -H 'Content-Type: application/json' \
        "${AUTH_ARGS[@]+"${AUTH_ARGS[@]}"}" \
        -d "{\"component\":\"${component}\",\"props\":${props}}")
    if [ "${code}" != "${expected}" ]; then
        echo "[showcase] ${component}: expected HTTP ${expected}, got ${code}" >&2
        cat /tmp/agui-showcase-resp.json >&2 || true
        exit 1
    fi
    echo "[showcase] ${component} -> ${code} (expected)" >&2
    sleep "${CAO_SHOWCASE_DELAY:-1}"
}

echo "[showcase] emitting all six allow-listed components to ${CAO_URL}" >&2

emit agent_card    '{"name":"showcase","provider":"mock_cli","status":"working"}' 200
emit progress      '{"label":"Analyzing dataset","value":35}' 200
emit metric        '{"label":"Coverage","value":99,"unit":"%"}' 200
emit diff_summary  '{"summary":"auth hardening","files":[{"path":"api/main.py","additions":18,"deletions":2}]}' 200
emit choice_prompt '{"question":"Pick a deploy target","choices":["staging","prod"]}' 200
emit approval_card '{"title":"Approve handoff to prod?","detail":"all gates green","risk":"high"}' 200

# The safety contract: an off-list component must be refused, never rendered.
emit iframe '{"src":"https://evil.example"}' 400

echo "[showcase] done — six components accepted, off-list refused" >&2
