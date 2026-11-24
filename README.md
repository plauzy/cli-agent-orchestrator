# Evidence for #1481: post-3.0 previews against a live server

Head under test: `3eb9073b` (branch `feat/519-agui-post-3-previews`), extracted with `git archive` and run as a private `cao-server` on 127.0.0.1 with `CAO_AGUI_ENABLED=1 CAO_AGUI_POST3_PREVIEW=1`, a temporary home, its own `CAO_HOME_DIR` and its own tmux socket. Three `mock_cli` seats were started in one session so the team-composition route has members. A second server without `CAO_AGUI_POST3_PREVIEW` gave the 404 stills.

The page in the clips is a small static HTML page. A script fetched each route from the live server and passed the real response to the page, which draws it. The page does not call the server itself.

The decision log was empty in this run: filling it needs a live approval prompt through the run plane, which these clips do not exercise.

| File | Shows |
|---|---|
| `pr1481/pr1481-still-1-live.png` | A2UI metric surface (Tokens 2,047), 3 team members from the real route, decision counts all 0, request log |
| `pr1481/pr1481-still-2-refusal.png` | The same page after `POST /agui/v1/preview/a2ui` with the off-list component `script`: HTTP 400 and the allow-list |
| `pr1481/pr1481-still-3-flag-off-404.png` | Flag off: the three preview routes answer 404 `{"detail":"Not Found"}`, same as a path that was never registered |
| `pr1481/pr1481-previews-live.gif` | One take: team composition, decisions, the metric surface updating 1,284 to 1,531 to 2,047, then the refusal (about 12 s) |
| `pr1481/pr1481-previews-live.webm` | The same take, full resolution |
