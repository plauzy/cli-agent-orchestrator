# CAO Dojo: live fleet view with an approval card you can answer

A **single HTML file with zero dependencies** (no npm, no framework, no build step). It
connects to your own local `cao-server`, shows the fleet and the six allow-listed
generative-UI components, and renders `approval_card` with working **Approve** and
**Reject** buttons. When an agent hits a permission prompt, you answer it here and CAO
types the answer into that agent's terminal.

It is built from [`../ag-ui-eventsource-viewer/index.html`](../ag-ui-eventsource-viewer/index.html),
the Renderer source named in the docs-site Dojo spec
(`.kiro/specs/cao-docsite-dojo/`, FR-11).

## Requirements

- A `cao-server` that includes the run-plane fix from
  [plauzy/cli-agent-orchestrator#44](https://github.com/plauzy/cli-agent-orchestrator/pull/44)
  (`/agui/v1/run` always ends with `RUN_FINISHED` or `RUN_ERROR`), installed with the
  `[agui]` extra. Older servers keep the run stream open and the page waits for its
  150 s backstop.
- For a real permission prompt: Claude Code 2.1.310 or later, which CAO detects as a
  `claude-code:permission_request` interrupt (also in #44).

## Run it

1. **Serve the page over http.** A `file://` page sends `Origin: null`, which CAO's
   Origin check rejects for the resume `POST`.

   ```bash
   cd examples/ag-ui/cao-dojo
   python3 -m http.server 8790 --bind 127.0.0.1
   ```

2. **Start `cao-server` with AG-UI on and the page's origin allowed.** Use a port that is
   not your working fleet's, and keep it on loopback: `cao-server` runs commands for
   whoever can reach it.

   ```bash
   CAO_AGUI_ENABLED=1 CAO_CORS_ORIGINS=http://localhost:8790 \
     cao-server --host 127.0.0.1 --port 9890
   ```

3. **Give an agent something to ask about, in a throwaway directory.** The bundled
   `dojo-approver` profile asks permission to write one file and does nothing else.

   ```bash
   export CAO_API_HOST=127.0.0.1 CAO_API_PORT=9890
   cao install examples/ag-ui/cao-dojo/dojo-approver.md
   cao launch --agents dojo-approver --session-name dojo-demo \
     --working-directory "$(mktemp -d)" --headless --auto-approve --async "Do your task now."
   ```

   `--auto-approve` only skips `cao launch`'s own confirmation. The profile sets
   `permissionMode: default`, so the file write still prompts.

4. **Open** `http://localhost:8790/index.html`, set the endpoint to
   `http://127.0.0.1:9890`, and click **Connect**. When the agent's prompt is up
   (about 20 s), the card appears. If it does not, click **Send run**: the run answers
   with every open approval.

5. **Approve or Reject.** The page posts the decision and shows the run's result.
   Approve writes `approved-by-dojo.txt` in the agent's directory; Reject leaves none.

6. **Tear down.** `cao shutdown --session cao-dojo-demo`, then stop `cao-server` and the
   http server (Ctrl-C, or `kill <pid>`).

The endpoint field defaults to `http://localhost:9889`, CAO's default port. You can also
pass it in the URL: `index.html?endpoint=http://127.0.0.1:9890`.

## What goes over the wire

| Transport | Request | Used for |
|---|---|---|
| Live (`EventSource`) | `GET /agui/v1/stream?since=<10 min ago>` | Fleet state and `GENERATIVE_UI` frames. `since` replays a card raised before the page opened. |
| Run (`fetch`, SSE body) | `POST /agui/v1/run` with a `RunAgentInput` | Collects open approvals. Ends `RUN_FINISHED` with outcome `interrupt` (and the interrupts) or `success`. |
| Run, resuming | same, plus `resume: [{interruptId, status: "resolved", payload: {approved: true \| false}}]` | Answers one approval. Ends `RUN_FINISHED` (success) once CAO has delivered it, or `RUN_ERROR` (for example an unknown interrupt). |

- The `approval_card` props are `interrupt_id`, `reason`, `message`, `options`,
  `provider` and `terminal_id`. The page shows them as plain text. `message` is always
  empty: CAO never puts the prompt body on the wire.
- `RUN_FINISHED` after a resume means the answer reached the terminal, not that the agent
  finished. A later prompt arrives as a new interrupt on the next run.
- The message box is sent as the run's user message. CAO's run plane uses the run to
  collect and answer approvals; it does not deliver that text to an agent.
- With auth enabled, the access token goes to the stream as `?access_token=` (EventSource
  cannot set headers) and to the run as `Authorization: Bearer`. A resume needs
  `cao:write`. The token is held in memory only.

## End-to-end check (local only)

`tools/e2e-local.sh` starts its own `cao-server` and static server, launches the
`dojo-approver` agent, and drives the page with Playwright through three phases:

- **approve**: the card appears, Approve posts the resume, the run ends `RUN_FINISHED`
  (success) and the file is written;
- **reject**: a fresh agent, Reject, `RUN_FINISHED` (success), no file;
- **none**: nothing pending, the run ends `RUN_FINISHED` (success) with no pending card,
  and a resume for an unknown interrupt shows `RUN_ERROR`.

```bash
(cd examples/ag-ui/cao-dojo/tools && npm install && npx playwright install chromium)
examples/ag-ui/cao-dojo/tools/e2e-local.sh
```

It needs `cao`, `cao-server` (at #44 or later, with `[agui]`) and a logged-in `claude`
on `PATH`, so it is not wired into CI. It refuses port 9889 and any port already in use.
It is isolated by default: unless you set `CAO_HOME_DIR` or `TMUX_TMPDIR`, it uses a
fresh CAO home (so the profile install never reaches your own store) and a private tmux
server, and removes both on exit. `E2E_SHOT_DIR`, `E2E_VIDEO_DIR`, `E2E_CAPTION` and
`E2E_HOLD_MS` record screenshots and video.

## Not in this page yet

- Replay mode (the embedded fixture) and the docs-site build under
  `docusaurus/static/dojo/`.
- A CI gate.
- The "edit" option. CAO offers it, but this page sends only approve and reject.
