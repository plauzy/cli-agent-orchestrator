#!/usr/bin/env bash
# ABOUTME: Assembles the interactive AG-UI Dojo from dojo-src/ parts into static/dojo/.
# ABOUTME: Inlines the committed fixture bundle so the page renders on static Pages (no backend).
#
# The page is a concatenation of _base.html, its modules in filename order, the
# inlined fixture bundle (as <script type="application/json"> blobs), and
# _footer.html. Shared CSS/JS is copied once to static/dojo-assets/. The fixtures
# are the SINGLE SOURCE OF TRUTH from examples/ag-ui/ag-ui-dojo/fixtures/ — the
# same bundle the shift-left recorder asserts and capture.py regenerates.
#
# Run from the docusaurus/ directory:  bash dojo-src/build.sh
# The Docusaurus build runs this automatically via the prebuild npm script.
set -euo pipefail

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUT="$SRC/../static"
FIXTURES="$SRC/../../examples/ag-ui/ag-ui-dojo/fixtures"

DEST="$OUT/dojo"
ASSETS="$OUT/dojo-assets"

mkdir -p "$DEST/fixtures" "$ASSETS"

# Shared assets (copied once, referenced as ../dojo-assets/ from static/dojo/).
cp "$SRC/shared/dojo.css" "$SRC/shared/dojo.js" "$ASSETS/"

# Copy the raw fixtures alongside the page too (raw download / live parity).
cp "$FIXTURES"/*.json "$FIXTURES"/*.jsonl "$DEST/fixtures/"

emit_json_blob() {
  # emit_json_blob <id> <type> <file>
  local id="$1" type="$2" file="$3"
  {
    printf '<script id="%s" type="%s">\n' "$id" "$type"
    cat "$file"
    printf '\n</script>\n'
  } >> "$DEST/index.html"
}

echo "Building AG-UI Dojo..."
# 1) shell + modules
cat "$SRC/_base.html" > "$DEST/index.html"
cat "$SRC"/modules/*.html >> "$DEST/index.html"

# 2) inlined fixture bundle (so the page needs no fetch / no backend)
emit_json_blob "dojo-manifest"  "application/json"     "$FIXTURES/manifest.json"
emit_json_blob "dojo-dashboard" "application/json"     "$FIXTURES/dashboard.json"
emit_json_blob "dojo-timeline"  "application/json"     "$FIXTURES/timeline.json"
emit_json_blob "dojo-reel"      "application/x-ndjson"  "$FIXTURES/generative-reel.jsonl"
emit_json_blob "dojo-frames"    "application/x-ndjson"  "$FIXTURES/frames.jsonl"

# 3) footer (closes main, loads ../dojo-assets/dojo.js)
cat "$SRC/_footer.html" >> "$DEST/index.html"

echo "  built dojo/index.html"
echo "Done."
