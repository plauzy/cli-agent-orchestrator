# CAO Testing Guide

This document describes the test-suite layout, the provider tier model that
determines which tests run where, and the canonical fixture surface shipped in
W1/W5.

---

## Provider tier model

Every e2e test surface chooses one of three tiers. The choice must be explicit
in the PR description (see `docs/TENETS.md` §1).

| Tier | Audience | Mechanism | Secrets needed |
|---|---|---|---|
| **1 — Default-off** | Unit + integration on every PR | W1 fixtures (`cao_server`). `cao_terminal` skips when the provider can't boot. | None. |
| **2 — Mock provider** | E2e in CI on PRs from forks | `mock_cli` provider — deterministic echo loop, no external CLI. | None. |
| **3 — Real-provider matrix** | Nightly + manual `workflow_dispatch` only | One workflow per provider (`e2e-anthropic.yml`, …), gated on `github.repository` to deny forks. | Per-provider CI service-account keys. |

The guiding principle: a new contributor who has just cloned the repo and run
`uv sync` must be able to run the Tier-1 and Tier-2 suites without any
additional setup. Any test that blocks on an API key belongs in Tier 3.

---

## Fixture surface (W1 + W5)

All fixtures listed here are available to every module under `test/` via
`conftest.py`'s `pytest_plugins` tuple. Import them from their defining
module, or simply declare them as function parameters — pytest discovers them
automatically.

### `test/fixtures/cao_server.py` — W1 subprocess fixtures

| Fixture | Scope | What it provides |
|---|---|---|
| `cao_server` | session | Spawned `cao-server` subprocess on a free localhost port. No auth enforcement. `CaoServer.url` is the base HTTP URL. |
| `cao_server_with_auth` | session | Same, but with Auth0 enforcement enabled. Points the subprocess at an in-process JWKS server. Bundle: `AuthCaoServer(server, jwks, private_pem, public_jwk)`. |
| `cao_terminal` | function | Creates one terminal on `cao_server` via POST /sessions. Provider/profile parameterisable via `indirect`. Skips gracefully if provider can't boot. |

`CaoServer` and `AuthCaoServer` are importable dataclasses for type hints.

**When to use:** Any test that needs a real HTTP server. Unit tests that mock
the HTTP layer don't need this.

---

### `test/fixtures/jwt_factory.py` — W5 JWT minting (Python)

| Symbol | Kind | What it provides |
|---|---|---|
| `JWTFactory` | class | Wraps an RSA-2048 keypair. Methods: `mint(scopes=…)`, `mint_admin()`, `mint_operator()`, `mint_viewer()`, `mint_expired()`, `jwks()`. |
| `JWTFactory.generate()` | classmethod | Generate a fresh keypair and return a `JWTFactory`. |
| `jwt_factory` | fixture (session) | One `JWTFactory` per pytest session. Use when the factory's lifetime should match `cao_server_with_auth`. |
| `jwt_factory_fn` | fixture (function) | Fresh `JWTFactory` per test. Use for security tests where key isolation matters. |

Wire format (matches `test/conftest.py:mint_test_token` and the Auth0
validation path in `src/cli_agent_orchestrator/security/auth.py`):

```
alg=RS256, kid="test-kid"
iss="https://test.local/"
aud="cao://test"
scope="<space-separated scopes>"
```

**Typical usage:**

```python
def test_viewer_is_rejected_on_write(cao_server_with_auth, jwt_factory):
    token = jwt_factory.mint_viewer()
    # … pass token via Sec-WebSocket-Protocol: cao.bearer.<token>
```

---

### `test/fixtures/jwks_server.py` — W5 JWKS HTTP server

| Symbol | Kind | What it provides |
|---|---|---|
| `JWKSServer` | class | Stdlib HTTP server that serves one JWKS document on `/.well-known/jwks.json`. Context-manager and `start()`/`stop()` API. |
| `JWKSServer.from_factory(factory)` | classmethod | Build directly from a `JWTFactory`. |
| `jwks_server` | fixture (session) | Session-scoped `JWKSServer` backed by `jwt_factory`. Bind `jwks_server.url` to `CAO_AUTH_JWKS_URI` when pointing a subprocess at the test JWKS. |
| `jwks_server_fn` | fixture (function) | Function-scoped variant backed by `jwt_factory_fn`. |

**When to use:** When you need to point a **subprocess** at the JWKS endpoint.
For in-process tests, prefer the `mock_jwks` fixture in `test/conftest.py`
(patches `requests.get` directly — no network required).

**Not needed for `cao_server_with_auth`:** that fixture manages its own
in-process JWKS server internally.

---

### `test/fixtures/terminal_factory.py` — W5 terminal lifecycle helper

| Symbol | Kind | What it provides |
|---|---|---|
| `TerminalHandle` | dataclass | `terminal_id`, `session_name`, `window_name`, `server_url`, `auth_token`, `.cleanup()`. |
| `TerminalFactory` | class | `create(server, *, provider, agent_profile, token, session_prefix)` — POST /sessions, skip on provider boot failure. |
| `cao_terminal_mock` | fixture (function) | Terminal on `cao_server` using `mock_cli` (Tier 2). |
| `cao_terminal_authed` | fixture (function) | Terminal on `cao_server_with_auth` using `mock_cli`, with admin JWT. |

**When to use:** When `cao_terminal` (W1, supports parametrised providers) is
overkill and you only need `mock_cli`. Also use `TerminalFactory.create`
directly when you need fine-grained control over creation parameters or when
building your own fixtures.

---

## TypeScript JWT helpers (W5)

For Playwright e2e tests and Node.js scripts that need to mint tokens for an
auth-enabled cao-server, use the TypeScript mirrors of `JWTFactory`:

| Path | Used by |
|---|---|
| `web/e2e/helpers/jwt.ts` | Playwright specs in `web/e2e/` (W3) |
| `cao_mcp_apps/e2e/helpers/jwt.ts` | MCP Apps e2e scripts in `cao_mcp_apps/e2e/` (W4/W6) |

Both files expose the same `JwtFactory` class:

```ts
import { JwtFactory } from './helpers/jwt';

const factory = JwtFactory.generate();         // RSA-2048 keypair
const token   = factory.mintViewer();          // cao:read only
const jwksDoc = factory.jwks();                // serve as /.well-known/jwks.json
const raw     = factory.mint({ expOffset: -1 }); // already expired
```

The JWKS document can be served by a local Node HTTP server and pointed at
via `CAO_AUTH_JWKS_URI` in the subprocess environment. This matches exactly
what Python's `JWKSServer.from_factory(factory)` does.

Zero additional npm dependencies — both files use `node:crypto` only.

---

## Test layout

```
test/
├── conftest.py                    # Global env + pytest_plugins
├── fixtures/
│   ├── cao_server.py              # W1: subprocess + auth fixtures
│   ├── jwt_factory.py             # W5: JWTFactory (Python)
│   ├── jwks_server.py             # W5: JWKSServer (Python)
│   ├── terminal_factory.py        # W5: TerminalFactory + handle
│   └── test_jwt_factory.py        # W5: self-tests for JWTFactory
├── e2e/
│   ├── helpers/
│   │   └── ws.py                  # W2: WebSocket connect helper
│   └── test_websocket_auth.py     # W2: 4 WS auth scenarios
├── providers/
│   └── ...                        # Provider unit tests
└── security/
    └── ...                        # Auth unit tests

web/
└── e2e/
    └── helpers/
        └── jwt.ts                 # W5: JwtFactory (TypeScript, Playwright)

cao_mcp_apps/
└── e2e/
    └── helpers/
        └── jwt.ts                 # W5: JwtFactory (TypeScript, MCP apps)
```

---

## Running the suite

```bash
# Tier-1 + Tier-2 (unit + integration, no providers needed)
uv run pytest --no-cov

# Tier-2 e2e only (mock_cli, no external CLIs)
uv run pytest -m e2e --no-cov

# W5 fixture self-tests
uv run pytest test/fixtures/test_jwt_factory.py -v

# W2 WebSocket auth smoke (Tier 2, needs cao-server)
uv run pytest -m e2e test/e2e/test_websocket_auth.py -v

# With coverage (default when addopts not overridden)
uv run pytest
```

---

## Adding a new provider (Tier 3)

See `skills/cao-provider/SKILL.md` for the full 20-lesson playbook. The short
version:

1. Subclass `providers/base.Provider`.
2. Implement `initialize()`, status detection regexes, and trust-prompt handling.
3. Add unit tests in `test/providers/test_<name>.py` using the fixture
   pattern in `test/providers/fixtures/generate_fixtures.py`.
4. Add a `test-<name>-provider.yml` workflow gated on `github.repository`
   (Tier 3 — never on fork PRs).
5. Add `<name>_API_KEY` to the provider-key table in this doc.
