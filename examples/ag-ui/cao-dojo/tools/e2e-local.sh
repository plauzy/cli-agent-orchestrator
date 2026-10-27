#!/usr/bin/env bash
# Local-only end-to-end check of the CAO Dojo page against a real cao-server
# and a real Claude Code agent: approve, then a fresh agent and reject, then a
# run with nothing pending. Exits 0 only if every assertion passes. Not wired
# into CI; it needs cao, a logged-in `claude`, and Playwright's Chromium.
#
#   examples/ag-ui/cao-dojo/tools/e2e-local.sh
#
# It always starts its own cao-server and refuses a port that is already in
# use, so it never drives a fleet you are working in. For full isolation, also
# point CAO_HOME_DIR and TMUX_TMPDIR at fresh temp dirs.
#
# Environment:
#   CAO_PORT        default 9890 (the server this script starts)
#   PAGE_PORT       default 8790 (the static server for ../index.html)
#   E2E_VIDEO_DIR   opt-in: record each phase's page video into this directory
#   E2E_CAPTION     opt-in: caption drawn on the page in those videos
#   E2E_SHOT_DIR    opt-in: save a screenshot of each step into this directory
#   E2E_HOLD_MS     opt-in: pause on the card and the result so videos are watchable
#
# Playwright and its Chromium must be installed once:
#   (cd examples/ag-ui/cao-dojo/tools && npm install && npx playwright install chromium)
#
# Written for bash 3.2, which is what macOS ships.
set -euo pipefail

# A fleet pane's $TMUX outranks TMUX_TMPDIR; never let the demo reach that server.
unset TMUX TMUX_PANE CAO_TERMINAL_ID

TOOLS_DIR="$(cd "$(dirname "$0")" && pwd)"
PAGE_DIR="$(cd "$TOOLS_DIR/.." && pwd)"
DRIVER="$TOOLS_DIR/e2e-local.mjs"
PROFILE_FILE="$PAGE_DIR/dojo-approver.md"
CAO_PORT="${CAO_PORT:-9890}"
PAGE_PORT="${PAGE_PORT:-8790}"
CAO_URL="http://127.0.0.1:$CAO_PORT"
PAGE_ORIGIN="http://localhost:$PAGE_PORT"
SESSION="dojo-demo" # cao prefixes it, so tmux shows "cao-dojo-demo"
TMP_ROOT="${TMPDIR:-/tmp}"
TMP_ROOT="${TMP_ROOT%/}"
LOG_DIR="$(mktemp -d "$TMP_ROOT/cao-dojo-e2e.XXXXXX")"
PROBE='{"threadId":"e2e-local","runId":"probe","state":{},"messages":[],"tools":[],"context":[],"forwardedProps":{}}'

export CAO_API_HOST=127.0.0.1 CAO_API_PORT="$CAO_PORT"

die() { echo "e2e-local: $*" >&2; exit 1; }

for cmd in cao cao-server claude node python3 curl; do
  command -v "$cmd" >/dev/null 2>&1 || die "'$cmd' is not on PATH"
done
PW_INSTALL="(cd examples/ag-ui/cao-dojo/tools && npm install && npx playwright install chromium)"
(cd "$TOOLS_DIR" && node -e '
  const { chromium } = require("@playwright/test");
  process.exit(require("fs").existsSync(chromium.executablePath()) ? 0 : 1);
') >/dev/null 2>&1 || die "Playwright or its Chromium is not installed: $PW_INSTALL"
[ "$CAO_PORT" != 9889 ] || die "refusing CAO_PORT=9889: that is the default fleet port; pick another"
for port in "$CAO_PORT" "$PAGE_PORT"; do
  if curl -s -o /dev/null -m 2 "http://127.0.0.1:$port/"; then
    die "something is already serving port $port; stop it or pick another port"
  fi
done

SERVER_PID=""
PAGE_PID=""
WORKDIR=""
# shellcheck disable=SC2329 # invoked by the EXIT trap
cleanup() {
  status=$?
  if [ -n "$SERVER_PID" ]; then
    cao shutdown --session "cao-$SESSION" >/dev/null 2>&1 || true
    kill "$SERVER_PID" 2>/dev/null || true
  fi
  if [ -n "$PAGE_PID" ]; then kill "$PAGE_PID" 2>/dev/null || true; fi
  remove_workdir
  if [ "$status" -eq 0 ]; then rm -rf "$LOG_DIR"; else echo "e2e-local: logs kept in $LOG_DIR" >&2; fi
}
remove_workdir() {
  case "$WORKDIR" in
    "$TMP_ROOT"/cao-dojo-work.*) [ -d "$WORKDIR" ] && [ ! -L "$WORKDIR" ] && rm -rf "$WORKDIR" ;;
  esac
  WORKDIR=""
}
trap cleanup EXIT
trap 'exit 130' INT TERM

echo "== serving $PAGE_DIR on $PAGE_ORIGIN"
python3 -m http.server "$PAGE_PORT" --bind 127.0.0.1 --directory "$PAGE_DIR" >"$LOG_DIR/page.log" 2>&1 &
PAGE_PID=$!

echo "== starting cao-server on $CAO_URL (log: $LOG_DIR/server.log)"
CAO_AGUI_ENABLED=1 CAO_CORS_ORIGINS="$PAGE_ORIGIN" \
  cao-server --host 127.0.0.1 --port "$CAO_PORT" >"$LOG_DIR/server.log" 2>&1 &
SERVER_PID=$!
i=0
until curl -fsS -m 2 "$CAO_URL/health" >/dev/null 2>&1; do
  i=$((i + 1))
  [ "$i" -le 60 ] || die "cao-server did not answer $CAO_URL/health within 60s"
  kill -0 "$SERVER_PID" 2>/dev/null || die "cao-server exited; see $LOG_DIR/server.log"
  sleep 1
done
i=0
until curl -fsS -m 2 -o /dev/null "$PAGE_ORIGIN/index.html"; do
  i=$((i + 1))
  [ "$i" -le 20 ] || die "the static server did not serve index.html; see $LOG_DIR/page.log"
  sleep 0.5
done

run_probe() {
  curl -s -m 5 -X POST "$CAO_URL/agui/v1/run" -H 'Content-Type: application/json' \
    -H 'Accept: text/event-stream' -d "$PROBE" || true
}
case "$(run_probe)" in
  *'"type":"RUN_FINISHED"'*) ;;
  *) die "POST $CAO_URL/agui/v1/run did not finish; is this CAO at the run-plane fix (#44) with the [agui] extra?" ;;
esac
cao install "$PROFILE_FILE" >/dev/null

# Launch a fresh agent in a throwaway work dir and wait until CAO reports its
# permission prompt as an open interrupt on the run plane.
fresh_agent() {
  cao shutdown --session "cao-$SESSION" >/dev/null 2>&1 || true
  remove_workdir
  WORKDIR="$(mktemp -d "$TMP_ROOT/cao-dojo-work.XXXXXX")"
  export E2E_WORKDIR="$WORKDIR"
  cao launch --agents dojo-approver --session-name "$SESSION" --working-directory "$WORKDIR" \
    --headless --auto-approve --async "Do your task now." >"$LOG_DIR/launch.log" 2>&1 ||
    { cat "$LOG_DIR/launch.log" >&2; die "cao launch failed"; }
  i=0
  until run_probe | grep -q '"outcome":{"type":"interrupt"'; do
    i=$((i + 1))
    [ "$i" -le 120 ] || die "the agent never raised a permission interrupt within 240s"
    sleep 2
  done
}

result=0
phase() {
  echo "== $1"
  if ! PAGE_URL="$PAGE_ORIGIN/index.html" CAO_URL="$CAO_URL" node "$DRIVER" "$1"; then result=1; fi
}

fresh_agent
phase approve
fresh_agent
phase reject
cao shutdown --session "cao-$SESSION" >/dev/null 2>&1 || true
phase none

if [ "$result" -eq 0 ]; then echo "e2e-local: PASS"; else echo "e2e-local: FAIL"; fi
exit "$result"
