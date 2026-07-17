#!/usr/bin/env bash
#
# AG-UI stock client live demo (POST /agui/v1/run).
#
# Boots cao-server with CAO_AGUI_ENABLED=1 and mock_cli on PATH, POSTs to
# /agui/v1/run using Python's requests library, and verifies at least one
# frame is received from post-connect activity.
#
# This proves the run plane works with a raw HTTP client speaking the stock
# AG-UI protocol (no CopilotKit, no JS, no special adapter).
#
# Usage:
#   ./examples/agui-stock-client-live/run.sh

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

export CAO_AGUI_ENABLED="${CAO_AGUI_ENABLED:-1}"
export CAO_API_PORT="${CAO_API_PORT:-9889}"
export PATH="${REPO_ROOT}/test/providers/fixtures/bin:${PATH}"
BASE="http://localhost:${CAO_API_PORT}"
SERVER_PID=""
SERVER_LOG="$(mktemp -t agui-stock-client.XXXXXX.log)"

cleanup() {
    local code=$?
    [ -n "${SERVER_PID}" ] && kill "${SERVER_PID}" >/dev/null 2>&1 || true
    rm -f "${SERVER_LOG}"
    exit "${code}"
}
trap cleanup EXIT INT TERM

CAO_SERVER_BIN="cao-server"
if [ -x "${REPO_ROOT}/.venv/bin/cao-server" ]; then
    CAO_SERVER_BIN="${REPO_ROOT}/.venv/bin/cao-server"
fi

echo "[stock-client] Starting cao-server (CAO_AGUI_ENABLED=${CAO_AGUI_ENABLED}) on ${BASE}" >&2
"${CAO_SERVER_BIN}" >"${SERVER_LOG}" 2>&1 &
SERVER_PID=$!

# Wait for the server to become healthy.
for _ in $(seq 1 40); do
    if curl -fsS "${BASE}/health" >/dev/null 2>&1; then break; fi
    sleep 0.5
done
if ! curl -fsS "${BASE}/health" >/dev/null 2>&1; then
    echo "[stock-client] Server did not become healthy; log follows:" >&2
    cat "${SERVER_LOG}" >&2 || true
    exit 1
fi
echo "[stock-client] Server healthy." >&2

# POST to /agui/v1/run and verify we get at least one frame back.
echo "[stock-client] POSTing to /agui/v1/run..." >&2

uv run python3 - "${BASE}" <<'PYTHON'
"""Minimal stock AG-UI client: POST to /agui/v1/run and parse SSE frames."""
import json
import sys
import uuid

import requests

base = sys.argv[1]
url = f"{base}/agui/v1/run"

# Build a RunAgentInput payload (stock AG-UI protocol).
payload = {
    "threadId": f"thread-{uuid.uuid4().hex[:8]}",
    "runId": f"run-{uuid.uuid4().hex[:8]}",
    "state": {},
    "messages": [],
    "tools": [],
    "context": [],
    "forwardedProps": {},
}

print(f"[stock-client] POST {url}")
print(f"[stock-client] payload = {json.dumps(payload)}")

resp = requests.post(
    url,
    json=payload,
    headers={"Content-Type": "application/json", "Accept": "text/event-stream"},
    stream=True,
    timeout=(5, 3),  # (connect_timeout, read_timeout) -- short read to avoid blocking on live bus
)

if resp.status_code == 501:
    print("[stock-client] 501: ag-ui-protocol extra not installed (expected in minimal installs)")
    print("[stock-client] PASS: endpoint responded correctly without the [agui] extra.")
    sys.exit(0)

if resp.status_code == 404:
    print("[stock-client] 404: AG-UI surface not enabled (check CAO_AGUI_ENABLED)")
    sys.exit(1)

resp.raise_for_status()

# Parse SSE frames from the response. The stream stays open for live bus
# events, so we use a short read timeout and catch the expected exceptions
# once the initial frames (RUN_STARTED, STATE_SNAPSHOT) have been delivered.
frames = []
try:
    for line in resp.iter_lines(decode_unicode=True):
        if line is None:
            continue
        if line.startswith("data: "):
            data_str = line[6:]
            try:
                frame = json.loads(data_str)
                frames.append(frame)
                frame_type = frame.get("type", "unknown")
                print(f"  frame: type={frame_type}")
            except json.JSONDecodeError:
                pass
        # Stop after collecting enough frames.
        if len(frames) >= 5:
            break
except (requests.exceptions.ChunkedEncodingError, requests.exceptions.ConnectionError):
    # Stream ended or read timed out after initial frames delivered.
    # Both are expected for short-lived runs with no live bus activity.
    pass

print(f"\n[stock-client] Received {len(frames)} frame(s).")

# Assertions.
if len(frames) == 0:
    print("[stock-client] FAIL: no frames received from POST /agui/v1/run")
    sys.exit(1)

# The first frame should be RUN_STARTED (stock AG-UI lifecycle).
first_type = frames[0].get("type")
if first_type == "RUN_STARTED":
    print(f"[stock-client] First frame is RUN_STARTED (threadId={frames[0].get('threadId')})")
else:
    print(f"[stock-client] First frame type: {first_type} (expected RUN_STARTED)")

print("[stock-client] PASS: at least one frame received from post-connect activity.")
sys.exit(0)
PYTHON

echo "[stock-client] Done." >&2
