# Evidence for #1482: robotics replay page in a browser

Head under test: `7c5862d6` (branch `feat/1166-robotics-agui-replay`), served as static files from `examples/ag-ui/robotics-replay/` with `python3 -m http.server` on 127.0.0.1, opened in Playwright Chromium at 1280x1020.

The page replays a recorded MOCK run (mock_cli seats, scripted decisions). It shows 31 rows in a table, not an animated floor. The "factory" rows are the MuJoCo side log.

| File | Shows |
|---|---|
| `pr1482/pr1482-still-1-start.png` | Page loaded, 0 of 31 rows, MOCK banner and legend |
| `pr1482/pr1482-still-2-approval.png` | 4 of 31 rows: approval card raised, operator resumes the run |
| `pr1482/pr1482-still-3-factory-floor.png` | 20 of 31 rows: team formation and start_line / start_shipping factory rows |
| `pr1482/pr1482-still-4-end.png` | 31 of 31 rows: all seats and the session ended |
| `pr1482/pr1482-replay-play.gif` | One take of Play, 31 rows at 450 ms each, about 17 s |
| `pr1482/pr1482-replay-play.webm` | The same take, full resolution |
