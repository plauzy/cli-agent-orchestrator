# AG-UI Stock Client Live Example

Proves the AG-UI run plane (`POST /agui/v1/run`) works with a raw HTTP client
speaking the stock protocol. No CopilotKit, no JavaScript, no custom adapter
needed.

## What it shows

- Booting `cao-server` with `CAO_AGUI_ENABLED=1`
- POSTing a `RunAgentInput` payload (threadId, runId) to `/agui/v1/run`
- Parsing `data:`-only SSE frames (camelCase JSON with `type` field)
- Verifying lifecycle-legal frame order (RUN_STARTED first)
- At least one frame received from post-connect server activity

## Running

```sh
./examples/agui-stock-client-live/run.sh
```

Uses `mock_cli` on PATH for credentials-free operation. The server starts in
the background, the client POSTs and verifies, then everything is cleaned up.

## What the run plane returns

A successful connection produces this frame sequence:

```
RUN_STARTED        -> echo threadId/runId
STATE_SNAPSHOT     -> current fleet state
[live frames...]   -> STATE_DELTA, STEP_STARTED/FINISHED, TOOL_CALL_*, CUSTOM
RUN_FINISHED       -> outcome: {type: "success"} or {type: "interrupt", ...}
```

If the `[agui]` extra (`ag-ui-protocol`) is not installed, the endpoint returns
HTTP 501 with an install hint. This is also considered a PASS for this example
(it proves the endpoint responds correctly).

## Stock client code (minimal)

```python
import requests, json, uuid

payload = {"threadId": str(uuid.uuid4()), "runId": str(uuid.uuid4())}
resp = requests.post(
    "http://localhost:9889/agui/v1/run",
    json=payload,
    stream=True,
    timeout=30,
)
for line in resp.iter_lines(decode_unicode=True):
    if line.startswith("data: "):
        frame = json.loads(line[6:])
        print(frame["type"])
```
