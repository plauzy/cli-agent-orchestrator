#!/bin/bash
# Run the same steps as GitHub Actions CI
set -e

echo "=== Testing CI Environment ==="

echo ""
echo "=== Environment Info ==="
echo "Node: $(node --version 2>/dev/null || echo 'not installed')"
echo "Bun: $(bun --version 2>/dev/null || echo 'not installed')"
echo "uv: $(uv --version 2>/dev/null || echo 'not installed')"
echo "tmux: $(tmux -V 2>/dev/null || echo 'not installed')"
echo "Python: $(python3 --version 2>/dev/null || echo 'not installed')"

echo ""
echo "=== Step 1: Install dependencies ==="
bun install --frozen-lockfile

echo ""
echo "=== Step 2: Lint ==="
bun run lint

echo ""
echo "=== Step 3: Type check ==="
bun run typecheck

echo ""
echo "=== Step 4: Build ==="
bun run build

echo ""
echo "=== Step 5: Unit tests ==="
bun run test

echo ""
echo "=== Step 6: E2E tests (optional - run with --e2e flag) ==="
if [[ "$1" == "--e2e" ]]; then
  cd packages/cao-playwright-utils
  npx playwright test
  cd ../..
else
  echo "Skipped. Run with --e2e to include E2E tests."
fi

echo ""
echo "=== All CI steps passed! ==="
