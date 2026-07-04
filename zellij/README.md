# `zellij/` — CAO v2.5 Phase 2 assets

This directory holds the source-of-truth for the Zellij TUI experience:

| Path | Purpose |
| --- | --- |
| `layouts/cao.kdl` | Three-pane Zellij layout (Control / Trace / Shell). |
| `src/lib.rs` | Rust source for the `zellaude` status-bar plugin. |
| `Cargo.toml` | Cargo manifest for the WASM plugin crate. |
| `zellaude.wasm` | **Vendored** pre-compiled plugin binary. Do not delete. |
| `.gitattributes` | Marks `*.wasm` as binary so diffs stay sane. |

The `cao zellij install` command copies `layouts/cao.kdl` and `zellaude.wasm`
into the user's `~/.config/zellij/{layouts,plugins}/`. End users do **not**
need a Rust toolchain — the `.wasm` ships in the wheel via Hatch
`force-include` (see `pyproject.toml`).

## Rebuilding the plugin

When `src/lib.rs` or `Cargo.toml` change, rebuild and re-vendor:

```bash
rustup target add wasm32-wasip1
cd zellij
cargo build --target wasm32-wasip1 --release
cp target/wasm32-wasip1/release/zellaude.wasm zellaude.wasm
```

Verify size budget (must stay under 2 MB so checkouts stay fast):

```bash
test "$(stat -c %s zellaude.wasm)" -lt 2000000
```

Then commit `zellaude.wasm` along with the source change so users on the
next `pip install` pick up the new binary without needing Rust.

## Local smoke test

```bash
cao zellij install
cao zellij start
```

The status bar at the bottom of the layout shows the live snapshot piped
in by `services/zellij_bridge.py`. The Python bridge starts in the FastAPI
lifespan when `CAO_ZELLIJ_ENABLED=true` (set automatically by
`cao zellij start`). See `docs/zellij.md` for the full bootstrap guide.
