#!/bin/bash
set -e

# Dev Container Validation Script
# Tests that the dev container configuration is valid and builds successfully

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "🧪 Dev Container Configuration Validation"
echo "=========================================="
echo ""

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test counter
TESTS_PASSED=0
TESTS_FAILED=0

# Test function
run_test() {
    local test_name="$1"
    local test_command="$2"

    echo -n "Testing: $test_name... "

    if eval "$test_command" > /dev/null 2>&1; then
        echo -e "${GREEN}✓ PASS${NC}"
        ((TESTS_PASSED++))
        return 0
    else
        echo -e "${RED}✗ FAIL${NC}"
        ((TESTS_FAILED++))
        return 1
    fi
}

# Test with details
run_test_with_details() {
    local test_name="$1"
    local test_command="$2"

    echo "Testing: $test_name"

    if eval "$test_command"; then
        echo -e "${GREEN}✓ PASS${NC}"
        echo ""
        ((TESTS_PASSED++))
        return 0
    else
        echo -e "${RED}✗ FAIL${NC}"
        echo ""
        ((TESTS_FAILED++))
        return 1
    fi
}

echo "📋 Phase 1: Configuration File Validation"
echo "-------------------------------------------"

# Test 1: Check devcontainer.json exists
run_test "devcontainer.json exists" \
    "test -f '$PROJECT_ROOT/.devcontainer/devcontainer.json'"

# Test 2: Check devcontainer.json is valid JSON
run_test "devcontainer.json is valid JSON" \
    "python3 -m json.tool '$PROJECT_ROOT/.devcontainer/devcontainer.json' > /dev/null"

# Test 3: Check image uses bookworm (not trixie)
if [ -f "$PROJECT_ROOT/.devcontainer/devcontainer.json" ]; then
    IMAGE=$(python3 -c "import json; f=open('$PROJECT_ROOT/.devcontainer/devcontainer.json'); d=json.load(f); print(d.get('image', ''))")

    if echo "$IMAGE" | grep -q "bookworm"; then
        echo -e "Testing: Image uses Debian Bookworm... ${GREEN}✓ PASS${NC}"
        ((TESTS_PASSED++))
    elif echo "$IMAGE" | grep -q "trixie"; then
        echo -e "Testing: Image uses Debian Bookworm... ${RED}✗ FAIL${NC}"
        echo -e "${RED}ERROR: Image uses Debian Trixie which is not compatible with Docker-in-Docker${NC}"
        ((TESTS_FAILED++))
    else
        echo -e "Testing: Image uses Debian Bookworm... ${YELLOW}⚠ WARN (image: $IMAGE)${NC}"
    fi
fi

# Test 4: Check Docker-in-Docker feature is configured
if [ -f "$PROJECT_ROOT/.devcontainer/devcontainer.json" ]; then
    DOCKER_FEATURE=$(python3 -c "
import json
f = open('$PROJECT_ROOT/.devcontainer/devcontainer.json')
d = json.load(f)
features = d.get('features', {})
for key in features:
    if 'docker-in-docker' in key.lower():
        print('found')
        break
" 2>/dev/null || echo "not found")

    if [ "$DOCKER_FEATURE" = "found" ]; then
        echo -e "Testing: Docker-in-Docker feature configured... ${GREEN}✓ PASS${NC}"
        ((TESTS_PASSED++))
    else
        echo -e "Testing: Docker-in-Docker feature configured... ${RED}✗ FAIL${NC}"
        ((TESTS_FAILED++))
    fi
fi

# Test 5: Check Dockerfile exists (if referenced)
if [ -f "$PROJECT_ROOT/.devcontainer/Dockerfile" ]; then
    run_test "Dockerfile exists" "test -f '$PROJECT_ROOT/.devcontainer/Dockerfile'"

    # Check Dockerfile uses bookworm
    if grep -q "bookworm" "$PROJECT_ROOT/.devcontainer/Dockerfile"; then
        echo -e "Testing: Dockerfile uses Debian Bookworm... ${GREEN}✓ PASS${NC}"
        ((TESTS_PASSED++))
    else
        echo -e "Testing: Dockerfile uses Debian Bookworm... ${YELLOW}⚠ WARN${NC}"
    fi
fi

echo ""
echo "📋 Phase 2: System Prerequisites"
echo "-------------------------------------------"

# Test system tools
run_test "Python 3.11+ installed" "python3 --version | grep -E 'Python 3\.(1[1-9]|[2-9][0-9])'"
run_test "Node.js 20+ installed" "node --version | grep -E 'v(2[0-9]|[3-9][0-9])'"
run_test "npm installed" "npm --version"
run_test "tmux installed" "tmux -V"
run_test "git installed" "git --version"
run_test "curl installed" "curl --version"

echo ""
echo "📋 Phase 3: Project Structure"
echo "-------------------------------------------"

# Test project structure
run_test "Root pyproject.toml exists" "test -f '$PROJECT_ROOT/pyproject.toml'"
run_test "Extension package.json exists" "test -f '$PROJECT_ROOT/vscode-extension/package.json'"
run_test "Webview package.json exists" "test -f '$PROJECT_ROOT/vscode-extension/webview/package.json'"
run_test "CDK package.json exists" "test -f '$PROJECT_ROOT/cdk/package.json'"
run_test "Scripts directory exists" "test -d '$PROJECT_ROOT/scripts'"
run_test "Build script exists" "test -f '$PROJECT_ROOT/scripts/build-extension.sh'"

echo ""
echo "📋 Phase 4: Python Environment"
echo "-------------------------------------------"

cd "$PROJECT_ROOT"

# Check if uv is installed
if command -v uv &> /dev/null; then
    echo -e "Testing: uv is installed... ${GREEN}✓ PASS${NC}"
    ((TESTS_PASSED++))

    # Try to sync dependencies
    run_test_with_details "Python dependencies can be synced" "uv sync --dry-run"
else
    echo -e "Testing: uv is installed... ${YELLOW}⚠ SKIP (uv not installed)${NC}"
fi

echo ""
echo "📋 Phase 5: Extension Build System"
echo "-------------------------------------------"

# Test extension dependencies
cd "$PROJECT_ROOT/vscode-extension"

if [ -f "package.json" ]; then
    run_test "Extension package.json is valid" "python3 -m json.tool package.json > /dev/null"

    # Check for required scripts
    SCRIPTS=$(python3 -c "import json; f=open('package.json'); d=json.load(f); print(' '.join(d.get('scripts', {}).keys()))" 2>/dev/null || echo "")

    if echo "$SCRIPTS" | grep -q "compile"; then
        echo -e "Testing: Extension has compile script... ${GREEN}✓ PASS${NC}"
        ((TESTS_PASSED++))
    else
        echo -e "Testing: Extension has compile script... ${RED}✗ FAIL${NC}"
        ((TESTS_FAILED++))
    fi
fi

# Test webview dependencies
cd "$PROJECT_ROOT/vscode-extension/webview"

if [ -f "package.json" ]; then
    run_test "Webview package.json is valid" "python3 -m json.tool package.json > /dev/null"

    # Check for required scripts
    SCRIPTS=$(python3 -c "import json; f=open('package.json'); d=json.load(f); print(' '.join(d.get('scripts', {}).keys()))" 2>/dev/null || echo "")

    if echo "$SCRIPTS" | grep -q "build"; then
        echo -e "Testing: Webview has build script... ${GREEN}✓ PASS${NC}"
        ((TESTS_PASSED++))
    else
        echo -e "Testing: Webview has build script... ${RED}✗ FAIL${NC}"
        ((TESTS_FAILED++))
    fi
fi

echo ""
echo "📋 Phase 6: CDK Infrastructure"
echo "-------------------------------------------"

cd "$PROJECT_ROOT/cdk"

if [ -f "package.json" ]; then
    run_test "CDK package.json is valid" "python3 -m json.tool package.json > /dev/null"
    run_test "CDK cdk.json exists" "test -f cdk.json"
    run_test "CDK app entrypoint exists" "test -f bin/cdk-app.ts"
    run_test "CDK stacks exist" "test -f lib/cao-network-stack.ts && test -f lib/cao-auth-stack.ts && test -f lib/cao-infrastructure-stack.ts"
fi

echo ""
echo "=========================================="
echo "📊 Test Results Summary"
echo "=========================================="
echo -e "Tests Passed: ${GREEN}$TESTS_PASSED${NC}"
echo -e "Tests Failed: ${RED}$TESTS_FAILED${NC}"
echo "Total Tests:  $((TESTS_PASSED + TESTS_FAILED))"
echo ""

if [ $TESTS_FAILED -eq 0 ]; then
    echo -e "${GREEN}✓ All tests passed!${NC}"
    exit 0
else
    echo -e "${RED}✗ Some tests failed!${NC}"
    exit 1
fi
