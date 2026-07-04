# CAO v2.5 Zellij TUI

CAO ships an opt-in [Zellij](https://zellij.dev/) layout (Phase 2) on top of
the v2.5 surfaces — the SSE bus, the ASI evaluator, the three-layer cache,
and the Agent Card listener. tmux + iTerm2 `-CC` remain the supported
compatibility path; Zellij is purely additive.

> **Audience:** operators who want a richer multi-pane experience than
> `cao launch` over tmux. If you are happy with tmux, do nothing — none of
> the lifespan paths exercised by Zellij are taken unless
> `CAO_ZELLIJ_ENABLED=true` is set.

---

## Phase 2 — One-time install

**Background.** The Zellij assets live under `zellij/` at the repo root:
the KDL layout (`zellij/layouts/cao.kdl`) and the pre-compiled status-bar
plugin (`zellij/zellaude.wasm`). They are mirrored into the wheel via
Hatch `force-include`, so no Rust toolchain is required at install time
for end users.

**Procedure.**

1. Install Zellij (`cargo install --locked zellij` or your package manager).
   CAO is tested against Zellij ≥ 0.42.
2. Install the layout + plugin into your Zellij config:
   ```
   cao zellij install
   ```
   This copies `cao.kdl` to `$XDG_CONFIG_HOME/zellij/layouts/` (defaulting
   to `~/.config/zellij/layouts/`) and `zellaude.wasm` to
   `$XDG_CONFIG_HOME/zellij/plugins/`.
3. Verify:
   ```
   ls ~/.config/zellij/layouts/cao.kdl ~/.config/zellij/plugins/zellaude.wasm
   ```

**Notes.**

- The install is idempotent — re-running overwrites the previous copies
  with whatever shipped in the current CAO wheel. Re-run after every
  `pip install --upgrade cli-agent-orchestrator` so the plugin matches
  the bridge.
- Windows is not supported by upstream Zellij. The CLI exits with a
  friendly error pointing at `cao launch` (tmux).

---

## Phase 2 — Launching the layout

**Background.** `cao zellij start` does three things: confirms the layout
exists, verifies the `zellij` binary is on `PATH`, and execs zellij with
`CAO_ZELLIJ_ENABLED=true` set. The CAO server picks up the env var in
its FastAPI lifespan and starts the hook bridge
(`services/zellij_bridge.py`), which subscribes to the in-process SSE
bus and pipes aggregated snapshots to the `zellaude` plugin.

**Procedure.**

1. Make sure the CAO server is running (`cao-server` or your supervisor).
2. Launch the TUI:
   ```
   cao zellij start
   ```
3. The layout opens with three panes:
   * **Control** — `cao session list` on a 2-second loop.
   * **Trace** — live event tail via `cao zellij tail` (timestamp +
     event type + key fields, ANSI-colored by severity).
   * **Shell** — free-form terminal in your `$SHELL`.
4. The status bar at the bottom shows:
   * Active session count.
   * Kill-switched task classes (red badge when present).
   * 60-second rolling cache hit-rate.
   * Most-recent ASI score, color-banded green / yellow / red.

**Notes.**

- Snapshots are pushed to the plugin no more than once per second to
  keep the status bar from flickering under bursty event traffic.
- If the bridge can't reach `zellij pipe` (no running zellij session,
  binary missing), it logs once at WARNING and stops trying — production
  traffic is never blocked by a broken TUI.
- Detach with `Ctrl+P d` (zellij default). The bridge will continue
  publishing snapshots in case you reattach.

---

## Phase 2 — Standalone trace tail

**Background.** `cao zellij tail` is the same SSE consumer used by the
Trace pane, packaged so you can also run it outside Zellij — handy for
piping to `grep` or for sanity-checking which events the server is
emitting.

**Procedure.**

```
cao zellij tail
cao zellij tail --max-events 50         # exit after 50 events
cao zellij tail --api http://other:9889 # remote CAO server
```

The tail reconnects with exponential backoff (1s → 30s) when the SSE
stream drops, so a transient server restart doesn't kill the pane.

---

## Phase 2 — Rebuilding the status-bar plugin

**Background.** The vendored `zellij/zellaude.wasm` is built from
`zellij/src/lib.rs` with `zellij-tile` 0.42. End users do not need
a Rust toolchain — the binary ships in the wheel. Maintainers who
edit `lib.rs` must rebuild and re-vendor:

**Procedure.**

```
rustup target add wasm32-wasip1
cd zellij
cargo build --target wasm32-wasip1 --release
cp target/wasm32-wasip1/release/zellaude.wasm zellaude.wasm
test "$(stat -c %s zellaude.wasm)" -lt 2000000   # 2 MB ceiling
```

Commit the new `zellaude.wasm` alongside the source change in the same
PR so users on the next `pip install` pick up the matching binary.

**Notes.**

- `*.wasm` is marked `binary -diff` in `zellij/.gitattributes` so PR
  diffs stay readable.
- The plugin is intentionally dumb: it stores only the latest snapshot
  and re-renders on each pipe message. All aggregation lives in the
  Python bridge so the WASM binary stays small (currently ~630 KB).

---

## Compatibility & rollback

- tmux launch (`cao launch`) is unchanged. Zellij is opt-in.
- Setting `CAO_ZELLIJ_ENABLED=false` (or unsetting it) at server start
  skips the bridge entirely — none of the Phase 2 code paths run.
- To uninstall: `rm ~/.config/zellij/layouts/cao.kdl
  ~/.config/zellij/plugins/zellaude.wasm`. The CAO server has no
  on-disk state tied to Zellij.
