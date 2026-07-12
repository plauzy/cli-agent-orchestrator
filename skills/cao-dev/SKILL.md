---
name: cao-dev
description: Use when modifying CAO source code. Provides quality checklist (pytest, black, isort, mypy), conventional commit conventions, and pre-commit validation. Do NOT use for plugin or provider creation — use cao-plugin or cao-provider instead.
allowed-tools: [Bash, Read, Edit, Write, Grep, Glob]
user-invocable: true
---

# CAO Development Workflow

Quality checklist for changes to the CLI Agent Orchestrator codebase.

## Project Root

All commands run from `/Volumes/workplace/cao/`.

## Quality Checks (run in order)

### 1. Tests

```bash
# Run all non-e2e tests with coverage
uv run pytest

# Run a specific test file
uv run pytest test/path/to/test_file.py -v

# Run a single test
uv run pytest test/path/to/test_file.py::test_name -vv
```

If tests fail, fix the issue before proceeding.

### 2. Formatting

```bash
# Check formatting (don't auto-fix — review first)
uv run black --check src/ test/
uv run isort --check src/ test/

# Auto-fix if needed
uv run black src/ test/
uv run isort src/ test/
```

Line length: 100 characters. Target: Python 3.10.

### 3. Type Checking

```bash
uv run mypy src/
```

Strict mode is enabled. Fix type errors before committing.

## Commit Convention

Use Conventional Commits format:

- `feat:` — new feature
- `fix:` — bug fix
- `doc:` — documentation only
- `chore:` — maintenance, dependencies, CI
- `refactor:` — code change that doesn't fix a bug or add a feature
- `test:` — adding or updating tests

Example: `feat: add Gemini CLI provider with streaming support`

## Pre-Commit Checklist

Before committing, confirm:
- [ ] Tests pass (`uv run pytest`)
- [ ] Formatting clean (`uv run black --check src/ test/` and `uv run isort --check src/ test/`)
- [ ] Types pass (`uv run mypy src/`)
- [ ] Commit message uses conventional format

## Key References

- Architecture: `cao/CODEBASE.md`
- Full dev guide: `cao/DEVELOPMENT.md`
- Contributing: `cao/CONTRIBUTING.md`
