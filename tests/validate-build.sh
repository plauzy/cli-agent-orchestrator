#!/bin/bash
set -e

# Build Validation Script
# Tests that all components can be built successfully

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "🏗️  Build Validation Test Suite"
echo "================================="
echo ""

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

TESTS_PASSED=0
TESTS_FAILED=0

run_test() {
    local test_name="$1"
    local test_command="$2"

    echo -e "${BLUE}▶${NC} $test_name"

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

echo "📦 Phase 1: Extension Build"
echo "----------------------------"

cd "$PROJECT_ROOT/vscode-extension"

# Install dependencies if needed
if [ ! -d "node_modules" ]; then
    echo "Installing extension dependencies..."
    npm install
fi

# Compile extension
echo "Compiling extension..."
if npm run compile > /tmp/extension-build.log 2>&1; then
    echo -e "${GREEN}✓ Extension compiled successfully${NC}"
    ((TESTS_PASSED++))
else
    echo -e "${RED}✗ Extension compilation failed${NC}"
    echo "See /tmp/extension-build.log for details"
    ((TESTS_FAILED++))
fi

# Verify output
if [ -f "out/extension.js" ]; then
    echo -e "${GREEN}✓ Extension output file exists${NC}"
    ((TESTS_PASSED++))
else
    echo -e "${RED}✗ Extension output file missing${NC}"
    ((TESTS_FAILED++))
fi

echo ""
echo "📱 Phase 2: Webview Build"
echo "----------------------------"

cd "$PROJECT_ROOT/vscode-extension/webview"

# Install dependencies if needed
if [ ! -d "node_modules" ]; then
    echo "Installing webview dependencies..."
    npm install
fi

# Build webview
echo "Building webview..."
if npm run build > /tmp/webview-build.log 2>&1; then
    echo -e "${GREEN}✓ Webview built successfully${NC}"
    ((TESTS_PASSED++))
else
    echo -e "${RED}✗ Webview build failed${NC}"
    echo "See /tmp/webview-build.log for details"
    ((TESTS_FAILED++))
fi

# Verify output
if [ -f "dist/index.js" ]; then
    echo -e "${GREEN}✓ Webview JS output exists${NC}"
    ((TESTS_PASSED++))
else
    echo -e "${RED}✗ Webview JS output missing${NC}"
    ((TESTS_FAILED++))
fi

if [ -f "dist/index.css" ]; then
    echo -e "${GREEN}✓ Webview CSS output exists${NC}"
    ((TESTS_PASSED++))
else
    echo -e "${YELLOW}⚠ Webview CSS output missing (may be optional)${NC}"
fi

echo ""
echo "☁️  Phase 3: CDK Build"
echo "----------------------------"

cd "$PROJECT_ROOT/cdk"

# Install dependencies if needed
if [ ! -d "node_modules" ]; then
    echo "Installing CDK dependencies..."
    npm install
fi

# Build CDK
echo "Building CDK..."
if npm run build > /tmp/cdk-build.log 2>&1; then
    echo -e "${GREEN}✓ CDK built successfully${NC}"
    ((TESTS_PASSED++))
else
    echo -e "${RED}✗ CDK build failed${NC}"
    echo "See /tmp/cdk-build.log for details"
    ((TESTS_FAILED++))
fi

# Verify JavaScript output
if [ -d "lib" ] && ls lib/*.js > /dev/null 2>&1; then
    echo -e "${GREEN}✓ CDK JavaScript output exists${NC}"
    ((TESTS_PASSED++))
else
    echo -e "${RED}✗ CDK JavaScript output missing${NC}"
    ((TESTS_FAILED++))
fi

# Test CDK synth (if cdk is installed)
if command -v cdk &> /dev/null; then
    echo "Testing CDK synth..."
    if cdk synth --no-lookups > /tmp/cdk-synth.log 2>&1; then
        echo -e "${GREEN}✓ CDK synth successful${NC}"
        ((TESTS_PASSED++))
    else
        echo -e "${YELLOW}⚠ CDK synth failed (may need AWS credentials)${NC}"
    fi
else
    echo -e "${YELLOW}⚠ CDK CLI not installed, skipping synth test${NC}"
fi

echo ""
echo "🐍 Phase 4: Python Package"
echo "----------------------------"

cd "$PROJECT_ROOT"

# Check if uv is available
if command -v uv &> /dev/null; then
    echo "Testing Python package..."

    # Dry run sync
    if uv sync --dry-run > /tmp/uv-sync.log 2>&1; then
        echo -e "${GREEN}✓ Python dependencies valid${NC}"
        ((TESTS_PASSED++))
    else
        echo -e "${RED}✗ Python dependencies check failed${NC}"
        echo "See /tmp/uv-sync.log for details"
        ((TESTS_FAILED++))
    fi
else
    echo -e "${YELLOW}⚠ uv not installed, skipping Python tests${NC}"
fi

echo ""
echo "================================="
echo "📊 Build Validation Summary"
echo "================================="
echo -e "Tests Passed: ${GREEN}$TESTS_PASSED${NC}"
echo -e "Tests Failed: ${RED}$TESTS_FAILED${NC}"
echo "Total Tests:  $((TESTS_PASSED + TESTS_FAILED))"
echo ""

if [ $TESTS_FAILED -eq 0 ]; then
    echo -e "${GREEN}✓ All builds completed successfully!${NC}"
    echo ""
    echo "Built artifacts:"
    echo "  • vscode-extension/out/extension.js"
    echo "  • vscode-extension/webview/dist/index.js"
    echo "  • cdk/lib/*.js"
    exit 0
else
    echo -e "${RED}✗ Some builds failed!${NC}"
    echo ""
    echo "Check log files for details:"
    echo "  • /tmp/extension-build.log"
    echo "  • /tmp/webview-build.log"
    echo "  • /tmp/cdk-build.log"
    exit 1
fi
