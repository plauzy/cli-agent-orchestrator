#!/usr/bin/env bash
# ABOUTME: Runs the dog-food capture that regenerates the CAO AG-UI Dojo fixture bundle.
# ABOUTME: Keyless + deterministic; gates on the AG-UI + privacy contract (see capture.py).
#
# Usage:  ./examples/ag-ui/ag-ui-dojo/run.sh
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"

export CAO_AGUI_ENABLED="${CAO_AGUI_ENABLED:-1}"
echo "[dojo-capture] Dog-feeding a real supervisor->developer->reviewer fleet onto the live AG-UI stream..." >&2
uv run python "${REPO_ROOT}/examples/ag-ui/ag-ui-dojo/capture.py"
