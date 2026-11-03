# Evidence for awslabs/cli-agent-orchestrator#1198 at 7f2028a2

These are screenshots and videos of the CAO Dojo end-to-end check
(`examples/ag-ui/cao-dojo/tools/e2e-local.sh` and `e2e-local.mjs`), recorded
on 2026-11-03 against `cao-server` built from commit
`7f2028a2a8a6ddee8b8c984a2805006e596cc33e` on `feat/agui-1.0-conformance`.
That commit is the round-3 review follow-up (on top of the fix `186b3e2a` and the merge of `upstream/main`
at `3dd21d5b`).

Every frame carries the caption `CAO 7f2028a2 | <phase>`. `SHA256SUMS` lists
the hash of every file (`shasum -a 256 -c SHA256SUMS`).

This branch holds evidence only. It shares no history with the code and is
not meant to be merged.

## Phases

| Phase | What it checks | Files |
|---|---|---|
| approve | A real Claude Code agent (`dojo-approver`) raises a permission prompt, which shows up as an approval card. Approve posts `resume[]`; the run ends `RUN_FINISHED` (success) and the agent writes its file. | `shots/approve-1-card.png`, `shots/approve-2-settled.png`, `video/approve.webm` |
| reject | A fresh agent; Reject; `RUN_FINISHED` (success); no file is written. | `shots/reject-1-card.png`, `shots/reject-2-settled.png`, `video/reject.webm` |
| none | Nothing pending: `RUN_FINISHED` (success). A resume for an unknown id is skipped; the run still ends `RUN_FINISHED` (success), and `result.skippedResume` lists the id. | `shots/none-2-settled.png`, `shots/none-3-unknown-interrupt-skipped.png`, `video/none.webm` |
| skipped | An approval card for an id CAO never raised, sent through `POST /agui/v1/emit_ui`. Approve ends `RUN_FINISHED` (success), `result.skippedResume` lists the id, and the card reads "answer not used — this prompt was no longer pending". | `shots/skipped-1-card.png`, `shots/skipped-2-skipped.png`, `video/skipped.webm` |

The page phase passed too. It records no media.

## Isolation and runs

- `cao-server` ran on `127.0.0.1:19898` and the page on `127.0.0.1:18798`.
  The developer's own server on 9889 was not used.
- Each run used a private `CAO_HOME_DIR` and a private tmux server
  (`TMUX_TMPDIR`). `TMUX` was unset.
- **The media come from two passes of the script's logic:**
  - page, none and skipped, with an isolated `HOME`;
  - approve and reject, with the real `HOME` for the existing Claude Code
    login.
- **The committed `e2e-local.sh` was also run once, unchanged**, with the real
  `HOME` and the same ports. All five phases passed (`e2e-local: PASS`). That
  run recorded no media.
