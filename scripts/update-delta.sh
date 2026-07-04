#!/usr/bin/env bash
# Usage: ./scripts/update-delta.sh
# Temporarily adds the awslabs upstream remote, prints the commit delta for
# docs/awslabs-delta.md, then removes the remote — no persistent remote state.
set -euo pipefail

UPSTREAM_URL="https://github.com/awslabs/cli-agent-orchestrator"
REMOTE_NAME="upstream"

git remote remove "$REMOTE_NAME" 2>/dev/null || true
git remote add "$REMOTE_NAME" "$UPSTREAM_URL"

git fetch "$REMOTE_NAME" --quiet

echo "=== Pat's commits not in awslabs upstream ==="
git log --oneline "$REMOTE_NAME/main..HEAD"

echo ""
echo "=== awslabs commits not in this repo ==="
git log --oneline "HEAD..$REMOTE_NAME/main"

git remote remove "$REMOTE_NAME"
