## Testing Guide

This document describes the testing infrastructure for the CLI Agent Orchestrator project.

## Overview

The project includes comprehensive testing to ensure:
1. Dev container configuration is compatible
2. Extension builds successfully
3. Infrastructure code is valid
4. Dependencies are correctly specified

## Test Structure

```
tests/
├── test_devcontainer_config.py    # Python test for dev container config
├── validate-devcontainer.sh       # Bash validation for container setup
└── validate-build.sh              # Complete build validation

.github/workflows/
├── test-devcontainer.yml          # CI for dev container
├── test-extension-build.yml       # CI for VSCode extension
└── test-cdk.yml                   # CI for CDK infrastructure
```

## Running Tests Locally

### 1. Dev Container Configuration Test

Tests that the dev container uses compatible base images:

```bash
# Run Python test
python3 tests/test_devcontainer_config.py

# Or run full validation
./tests/validate-devcontainer.sh
```

**What it checks:**
- ✅ devcontainer.json exists and is valid JSON
- ✅ Uses Debian Bookworm (not Trixie)
- ✅ Docker-in-Docker feature is configured
- ✅ Dockerfile uses compatible base image
- ✅ Required features are present

**Why this matters:**
- Debian Trixie removed moby packages, breaking Docker-in-Docker
- Using Bookworm ensures Docker compatibility
- This test prevents the build error we encountered

### 2. Build Validation Test

Tests that all components build successfully:

```bash
./tests/validate-build.sh
```

**What it checks:**
- ✅ VSCode extension compiles
- ✅ React webview builds
- ✅ CDK infrastructure builds
- ✅ Python dependencies are valid
- ✅ Output files are created

**Output artifacts verified:**
- `vscode-extension/out/extension.js`
- `vscode-extension/webview/dist/index.js`
- `cdk/lib/*.js`

### 3. Individual Component Tests

#### Extension Build
```bash
cd vscode-extension
npm install
npm run compile
npm run lint
```

#### Webview Build
```bash
cd vscode-extension/webview
npm install
npm run build
```

#### CDK Build
```bash
cd cdk
npm install
npm run build
cdk synth --no-lookups
```

## Continuous Integration

### GitHub Actions Workflows

All workflows run automatically on push and pull requests.

#### 1. **test-devcontainer.yml**

Runs on changes to:
- `.devcontainer/**`
- `tests/**`

**Jobs:**
- `test-devcontainer-config`: Validates configuration
- `build-devcontainer`: Builds container and tests

**Key checks:**
- JSON validation
- Debian Trixie detection (fails if found)
- Bookworm verification
- Container build test

#### 2. **test-extension-build.yml**

Runs on changes to:
- `vscode-extension/**`
- `scripts/build-extension.sh`

**Jobs:**
- `validate-config`: Validates package.json and tsconfig.json
- `build-extension`: Builds extension and webview
- `test-build-script`: Tests build script execution

**Key checks:**
- JSON validation for all configs
- TypeScript compilation
- Webview build
- Output artifact verification
- Linting

#### 3. **test-cdk.yml**

Runs on changes to:
- `cdk/**`

**Jobs:**
- `validate-cdk`: Validates CDK configuration
- `build-cdk`: Builds and synthesizes stacks

**Key checks:**
- JSON validation for package.json and cdk.json
- TypeScript compilation
- CDK synthesis
- Stack template generation

## Critical Test: Debian Compatibility

### The Problem We're Preventing

**Issue:** Docker-in-Docker feature fails on Debian Trixie
```
ERROR: The 'moby' option is not supported on Debian 'trixie'
because 'moby-cli' and related system packages have been removed
```

### Our Solution

1. **Python Test** (`test_devcontainer_config.py`):
   - Parses devcontainer.json
   - Checks image tag for "bookworm" or "trixie"
   - Fails build if Trixie is detected

2. **GitHub Actions Check**:
   - Greps for "trixie" in config files
   - Fails CI if found
   - Prevents merging incompatible changes

3. **Documentation**:
   - Clear error messages
   - Suggests fix: use bookworm
   - Points to compatible images

### How to Fix if Test Fails

If you see this error:
```
✗ CRITICAL: Image uses Debian Trixie
```

**Fix:**
```json
{
  "image": "mcr.microsoft.com/devcontainers/python:3.11-bookworm"
}
```

Or in Dockerfile:
```dockerfile
FROM mcr.microsoft.com/devcontainers/python:3.11-bookworm
```

## Test Development

### Adding New Tests

#### 1. Add to Python test suite:

```python
# tests/test_devcontainer_config.py

def test_my_new_check(config):
    """Test description"""
    # Your test logic
    assert condition, "Error message"
    print("✓ Test passed")
    return True
```

#### 2. Add to bash validation:

```bash
# tests/validate-devcontainer.sh

run_test "My test description" \
    "command_to_test"
```

#### 3. Update GitHub Actions:

```yaml
# .github/workflows/test-devcontainer.yml

- name: My new check
  run: |
    # Test commands
```

### Test Best Practices

1. **Fast Feedback**: Tests should run quickly (<1 minute)
2. **Clear Messages**: Errors should explain what's wrong and how to fix it
3. **Actionable**: Tests should suggest solutions
4. **Comprehensive**: Cover all critical paths
5. **Documented**: Explain why tests exist

## Debugging Failed Tests

### Dev Container Test Fails

```bash
# Run with verbose output
python3 -v tests/test_devcontainer_config.py

# Check JSON syntax
python3 -m json.tool .devcontainer/devcontainer.json

# Verify image tag
cat .devcontainer/devcontainer.json | grep image
```

### Build Test Fails

```bash
# Check logs
cat /tmp/extension-build.log
cat /tmp/webview-build.log
cat /tmp/cdk-build.log

# Run individual builds
cd vscode-extension && npm run compile
cd vscode-extension/webview && npm run build
cd cdk && npm run build
```

### GitHub Actions Fails

1. Check the workflow logs in GitHub
2. Reproduce locally:
   ```bash
   # Same commands as in workflow
   python3 tests/test_devcontainer_config.py
   ./tests/validate-build.sh
   ```
3. Fix the issue
4. Re-run tests
5. Push changes

## Test Coverage

Current test coverage:

| Component | Tests | Status |
|-----------|-------|--------|
| **Dev Container** | ✅ Configuration validation | Complete |
| **Dev Container** | ✅ Docker compatibility | Complete |
| **Dev Container** | ✅ Build test | Complete |
| **Extension** | ✅ TypeScript compilation | Complete |
| **Extension** | ✅ Config validation | Complete |
| **Extension** | ✅ Build script | Complete |
| **Webview** | ✅ React build | Complete |
| **Webview** | ✅ Output verification | Complete |
| **CDK** | ✅ TypeScript compilation | Complete |
| **CDK** | ✅ Stack synthesis | Complete |
| **Python** | ✅ Dependency validation | Complete |

## Pre-commit Hooks (Optional)

To run tests before committing:

```bash
# Create .git/hooks/pre-commit
cat > .git/hooks/pre-commit <<'EOF'
#!/bin/bash
echo "Running pre-commit tests..."
python3 tests/test_devcontainer_config.py || exit 1
echo "✓ Tests passed"
EOF

chmod +x .git/hooks/pre-commit
```

## Continuous Improvement

### When to Add Tests

Add tests when:
1. ✅ A bug is found (add regression test)
2. ✅ New features are added
3. ✅ Configuration changes
4. ✅ Dependencies are updated

### Test Maintenance

- Review tests quarterly
- Update for new dependencies
- Add tests for reported issues
- Keep documentation current

## Resources

- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [Dev Containers Testing](https://containers.dev/guide/testing)
- [Python unittest](https://docs.python.org/3/library/unittest.html)
- [Bash Testing Best Practices](https://github.com/sstephenson/bats)

## Questions?

If you have questions about testing:
1. Check this documentation
2. Review test files for examples
3. Look at GitHub Actions workflow logs
4. Ask in pull request comments

## Summary

Our testing infrastructure ensures:
- ✅ Dev container builds correctly
- ✅ No Debian Trixie issues
- ✅ All components build successfully
- ✅ CI catches issues before merge
- ✅ Clear error messages and fixes

This prevents the Docker-in-Docker issue we encountered and catches similar problems early.
