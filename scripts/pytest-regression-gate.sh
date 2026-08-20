#!/usr/bin/env sh
# Pre-push pytest gate that blocks on REGRESSIONS, not on absolute green.
#
# Why: the pre-push hook previously required a fully green suite. As of
# 2026-08-19 `main` itself fails 71 tests (57 of them AG-UI), so the gate was
# unpassable from a clean checkout -- every contributor had to `--no-verify`,
# which disables the gate entirely and lets real regressions through unnoticed.
#
# A gate nobody can pass is worse than no gate: it trains people to bypass it.
#
# This compares the current failure set against a recorded baseline and fails
# ONLY on test IDs that are newly broken. Tests that start passing are reported
# as a hint to refresh the baseline, but never block.
#
# Refresh the baseline (run on a clean checkout of the target branch):
#   ./scripts/pytest-regression-gate.sh --update-baseline
set -u

ROOT=$(cd "$(dirname "$0")/.." && pwd)
BASELINE="$ROOT/test/known-failures.txt"
CURRENT=$(mktemp)
trap 'rm -f "$CURRENT"' EXIT

run_suite() {
  if command -v uv >/dev/null 2>&1; then
    (cd "$ROOT" && uv run pytest test -m "not e2e" -q --disable-warnings -p no:cacheprovider 2>&1)
  elif command -v python3 >/dev/null 2>&1 && python3 -c "import pytest" >/dev/null 2>&1; then
    (cd "$ROOT" && python3 -m pytest test -m "not e2e" -q --disable-warnings -p no:cacheprovider 2>&1)
  else
    echo "__NO_RUNNER__"
  fi
}

OUT=$(run_suite)
if [ "$OUT" = "__NO_RUNNER__" ]; then
  echo "[gate] skipping python tests: no uv/pytest runner on PATH"
  exit 0
fi

# Normalise: strip the FAILED/ERROR prefix and any trailing " - <message>".
printf '%s\n' "$OUT" | grep -E '^(FAILED|ERROR)' \
  | sed -E 's/^(FAILED|ERROR) //; s/ - .*$//' | sort -u > "$CURRENT"

if [ "${1:-}" = "--update-baseline" ]; then
  mkdir -p "$(dirname "$BASELINE")"
  cp "$CURRENT" "$BASELINE"
  echo "[gate] baseline updated: $(wc -l < "$BASELINE" | tr -d ' ') known failures recorded"
  exit 0
fi

[ -f "$BASELINE" ] || : > "$BASELINE"

NEW=$(comm -13 "$BASELINE" "$CURRENT")
FIXED=$(comm -23 "$BASELINE" "$CURRENT")

if [ -n "$FIXED" ]; then
  echo "[gate] these baseline failures now PASS -- refresh with --update-baseline:"
  printf '%s\n' "$FIXED" | sed 's/^/    /'
fi

if [ -n "$NEW" ]; then
  echo ""
  echo "[gate] REGRESSION: tests failing that are not in the baseline:"
  printf '%s\n' "$NEW" | sed 's/^/    /'
  echo ""
  echo "[gate] baseline: $BASELINE ($(wc -l < "$BASELINE" | tr -d ' ') known failures)"
  exit 1
fi

echo "[gate] no regressions ($(wc -l < "$CURRENT" | tr -d ' ') failures, all known)"
exit 0
