# Evidence for awslabs/cli-agent-orchestrator#1198 at 15a24d48

These are screenshots and videos of the CAO Dojo end-to-end check
(`examples/ag-ui/cao-dojo/tools/e2e-local.sh` and `e2e-local.mjs`), recorded
on 2026-11-02 against `cao-server` built from commit
`15a24d48b5025bb510c7a6f48c33a6629c55e55c` on `feat/agui-1.0-conformance`.
Every frame carries the caption `CAO 15a24d48 | <phase>`. `SHA256SUMS` lists
the hash of every file (`shasum -a 256 -c SHA256SUMS`).

This branch holds evidence only. It shares no history with the code and is
not meant to be merged.

## Phases

| Phase | What it checks | Files |
|---|---|---|
| page | No server. A scripted `EventSource` and a stubbed run exercise the page's own state handling, including a `RUN_FINISHED` whose `result.skippedResume` lists the decided card, which must end `skipped` rather than approved or rejected. | `shots/page-1-final.png`, `video/page.webm` |
| approve | A real Claude Code agent (`dojo-approver`, model haiku) raises a permission prompt, which shows up as an approval card. Approve posts `resume[]`; the run ends `RUN_FINISHED` (success) and the agent writes its file. | `shots/approve-1-card.png`, `shots/approve-2-settled.png`, `video/approve.webm` |
| reject | A fresh agent; Reject; `RUN_FINISHED` (success); no file is written. | `shots/reject-1-card.png`, `shots/reject-2-settled.png`, `video/reject.webm` |
| none | Nothing pending: `RUN_FINISHED` (success) with no card. A resume for an unknown id is skipped. The run still ends `RUN_FINISHED` (success), and `result.skippedResume` lists the id. | `shots/none-2-settled.png`, `shots/none-3-unknown-interrupt-skipped.png`, `video/none.webm` |
| skipped | No agent. An approval card for an id CAO never raised is sent through `POST /agui/v1/emit_ui`. Approve ends `RUN_FINISHED` (success), `result.skippedResume` lists the id, and the card reads "answer not used — this prompt was no longer pending". | `shots/skipped-1-card.png`, `shots/skipped-2-skipped.png`, `video/skipped.webm` |

All five phases passed.

## Isolation

- `cao-server` ran on `127.0.0.1:19898` and the page on `127.0.0.1:18798`. The
  developer's own server on 9889 was not used.
- Each run used a private `CAO_HOME_DIR` and a private tmux server
  (`TMUX_TMPDIR`) under a temp directory. `TMUX` was unset, and everything was
  removed when the run ended.
- The page, none and skipped phases ran with an isolated `HOME`.
- The approve and reject phases ran with the real `HOME`, so the agent could
  use the existing Claude Code login.
- Because of that split, the phases ran in two passes of the script's logic
  rather than as one run of the committed `e2e-local.sh`.
- The page phase has no recording hooks in `e2e-local.mjs`. Its video and
  screenshot come from a preload, loaded with `node --import`, that wraps
  Playwright's `chromium.launch`. The phase's assertions are unchanged.
