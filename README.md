# Evidence for #1481 (v2): post-3.0 previews against a live server, decision log filled

Head under test: `3eb9073b` (branch `feat/519-agui-post-3-previews`), extracted with `git archive` and run as a private `cao-server` on 127.0.0.1 with `CAO_AGUI_ENABLED=1 CAO_AGUI_POST3_PREVIEW=1 CAO_MOCK_CLI_SCRIPTED_PROMPTS=1`, a temporary home, its own `CAO_HOME_DIR` and its own tmux socket. Three `mock_cli` seats run in one session. A second server without `CAO_AGUI_POST3_PREVIEW` gave the 404 still.

The page in the clips is a small static HTML page. A script fetched each route from the live server and passed the real response to the page, which draws it. The page does not call the server itself.

How the three decisions were produced, all through the real route `POST /agui/v1/interrupts/{id}/resume`:
- approve and deny: two `mock_cli` seats were sent `__mock_approval__ ...`, went to `waiting_user_answer`, and the real approval bridge raised one interrupt each (`mock-cli:unknown_prompt`, which offers approve and deny only). The interrupt ids came from the run plane (`POST /agui/v1/run`).
- edit: `mock_cli` interrupts cannot offer edit, so this one was raised with the same call the decision-log tests make, `construct.on_provider_waiting(provider="kiro_cli", raw_prompt="Allow this action? [y/n/t]:")`, on the server's own approval bridge (`kiro:permission_request`, options approve, deny, edit). It was resumed with `{"decision": "edit", "edited_text": "<41 characters>"}`. This one is fixture-raised, not a real Kiro prompt.
- The decision log was not written by hand. The edited text appears nowhere in the log's response or file.

| File | Shows |
|---|---|
| `pr1481/pr1481-still-1-live.png` | A2UI metric surface (Tokens 2,047), 3 team members, decisions total 3 (approve 1, deny 1, edit 1) with id-only recent entries, request log |
| `pr1481/pr1481-still-2-refusal.png` | The same page after `POST /agui/v1/preview/a2ui` with the off-list component `script`: HTTP 400 and the allow-list |
| `pr1481/pr1481-still-3-flag-off-404.png` | Flag off: the preview routes answer 404 `{"detail":"Not Found"}`, same as a path that was never registered |
| `pr1481/pr1481-previews-live.gif` | One take, about 21 s: team composition, decisions at 0, the surface updating, then approve, deny and edit with the count rising 1, 2, 3, then the refusal |
| `pr1481/pr1481-previews-live.webm` | The same take, full resolution |
