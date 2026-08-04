# AG-UI Dojo — dog-food capture + shift-left fixtures

> **The CAO AG-UI Dojo is CAO feeding agents to build its own showcase
> (dog-food), with every artifact gated by an assertion that runs before the
> pipeline (shift-left).** — see [THEMES.md](THEMES.md) for the frontier-team
> practices this embodies ([kiro.dev/topics/frontier-teams](https://kiro.dev/topics/frontier-teams/)).

This directory is the **data + verification half** of the dojo. The interactive
renderer lives in the docsite ([`docusaurus/dojo-src/`](../../../docusaurus/dojo-src/))
and ships to `awslabs.github.io/cli-agent-orchestrator/dojo/`.

## What's here

| Path | Role | Frontier-team practice |
|---|---|---|
| [`THEMES.md`](THEMES.md) | The "why" — the manifesto every artifact links to | Make intent explicit |
| [`capture.py`](capture.py) | Drives a real cross-provider fleet through the production AG-UI path and writes `fixtures/` | **Feed agents instead of babysitting** |
| [`fixtures/`](fixtures/) | Committed evidence bundle the static dojo renders (no backend needed) | Rich context |
| [`tools/record-dojo.mjs`](tools/record-dojo.mjs) | Gated recorder: asserts the dojo renders, then exports the GIF | **Shift testing left** |
| `../../../test/services/agui/test_dojo_fixtures.py` | Pure pytest gate over the fixtures (frame contract + privacy + allow-list) | Verify before ship |

## The dog-food loop (produce)

```sh
CAO_AGUI_ENABLED=1 uv run python examples/ag-ui/ag-ui-dojo/capture.py
# or: ./examples/ag-ui/ag-ui-dojo/run.sh
```

A `kiro_cli` **supervisor** delegates to a `claude_code` **developer** and a
`codex` **reviewer** (`assign` → `handoff` → `handoff`). The lifecycle flows
through the *production* event path, is observed on the real
`GET /agui/v1/stream`, folded through `SupervisorDashboardStream` and
`MultiAgentSessionTimeline`, and all six generative-UI components (plus one
off-list refusal) are driven through `POST /agui/v1/emit_ui`. The observed
output is written to `fixtures/`. **CAO builds and observes its own showcase.**

It is keyless and deterministic, and it **gates**: it prints
`[dojo-capture] PASS` and exits 0 only if the fleet frames appear, the six
components are accepted, the off-list component is refused, and no message body
leaks (privacy boundary).

## The shift-left loop (verify — runs before the pipeline)

1. **Frame contract (pytest, no server):**
   ```sh
   uv run pytest test/services/agui/test_dojo_fixtures.py -q
   ```
   Asserts every frame's `agui_type`, a well-formed tool-call lifecycle, the
   metadata-only privacy boundary, and that the reel has 6 allow-listed
   components + exactly 1 off-list refusal.

2. **Renderer assertion + gated media (Playwright):**
   ```sh
   cd docusaurus && npm run build-dojo          # assembles static/dojo/
   cd ../examples/ag-ui/ag-ui-dojo/tools
   npm ci && npm run playwright:install && npm run record
   ```
   Loads the assembled dojo, replays the fixtures, and **only** exports
   `docs/media/ag-ui-dojo-demo.gif` if all four panels + six components render
   and the off-list component is refused to an inert placeholder. A broken dojo
   cannot produce a green recording.

## Fixture bundle contract

The docsite dojo consumes a **normalized, pre-computed** bundle so the browser
never re-implements the Python fold logic (single source of truth):

| File | Contents |
|---|---|
| `frames.jsonl` | Raw AG-UI wire frames observed on `/agui/v1/stream` (evidence + raw-frame inspector). |
| `dashboard.json` | `SupervisorDashboardStream` projection (fleet rollup). |
| `timeline.json` | `MultiAgentSessionTimeline` projection (delegation chain, **metadata only**). |
| `generative-reel.jsonl` | Normalized `{component, props, expect}` intents — 6 render + 1 refuse. |
| `manifest.json` | Provenance, provider set, counts, privacy flags. |

## See also

- [`docs/agui.md`](../../../docs/agui.md) — the AG-UI reference.
- [`skills/agui-author/`](../../../skills/agui-author/) — the component vocabulary the workers use.
- [`ag-ui-meta-dogfood/`](../ag-ui-meta-dogfood/) — the sibling loop this capture extends.
- [`ag-ui-construct-demos/`](../ag-ui-construct-demos/) — the gated-recorder pattern this mirrors.
