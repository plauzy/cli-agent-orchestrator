#!/usr/bin/env python3
# ABOUTME: Dog-food capture for the CAO AG-UI Dojo — a real supervisor->worker
# ABOUTME: fleet drives the production AG-UI path; the observed stream becomes the dojo's committed fixtures.
"""Dog-food capture for the CAO AG-UI Dojo.

This is the **"feed agents instead of babysitting"** half of the effort (see
[THEMES.md](THEMES.md)). It drives a real, cross-provider supervisor -> developer
-> reviewer session through the *production* AG-UI path (the ``EventLogPublisher``
observer emits to the in-process ``EventLog`` under ``CAO_AGUI_ENABLED``), reads
the frames back off the real ``GET /agui/v1/stream`` endpoint, folds them through
the L2 constructs, and drives all six generative-UI components (plus one off-list
refusal) through ``POST /agui/v1/emit_ui``.

The observed output is written to ``fixtures/`` as the dojo's committed evidence
bundle — the *same* data the static docsite dojo renders. CAO builds and observes
its own showcase.

Keyless and deterministic (no external providers, no tmux, no browser), so it runs
anywhere CI runs. It **gates**: it prints ``[dojo-capture] PASS`` and exits 0 only
if the real fleet frames appear on the wire, all six components are accepted, the
off-list component is refused, and the privacy boundary holds (no message bodies).

Usage:  CAO_AGUI_ENABLED=1 uv run python examples/ag-ui/ag-ui-dojo/capture.py
"""

from __future__ import annotations

import asyncio
import json
import os
import pathlib
import sys
from dataclasses import asdict as _asdict
from datetime import datetime, timedelta, timezone

os.environ["CAO_AGUI_ENABLED"] = "1"
os.environ.pop("CAO_MCP_APPS_ENABLED", None)

from fastapi.testclient import TestClient  # noqa: E402

from cli_agent_orchestrator.api.main import app  # noqa: E402
from cli_agent_orchestrator.plugins.builtin.event_log_publisher import (  # noqa: E402
    EventLogPublisher,
)
from cli_agent_orchestrator.plugins.events import (  # noqa: E402
    PostCreateSessionEvent,
    PostCreateTerminalEvent,
    PostKillTerminalEvent,
    PostSendMessageEvent,
)
from cli_agent_orchestrator.services.agui.base import RecordingUiEmitter  # noqa: E402
from cli_agent_orchestrator.services.agui.session_timeline import (  # noqa: E402
    MultiAgentSessionTimeline,
)
from cli_agent_orchestrator.services.agui.supervisor_dashboard import (  # noqa: E402
    SupervisorDashboardStream,
)
from cli_agent_orchestrator.services.event_log_service import get_event_log  # noqa: E402

HERE = pathlib.Path(__file__).parent
FIXTURES = HERE / "fixtures"
SESSION = "cao-audit-fleet"

# The multi-provider fleet — CAO's headline AG-UI angle (N clients / N providers).
FLEET = [
    ("t-supervisor", "code_supervisor", "kiro_cli"),
    ("t-developer", "developer", "claude_code"),
    ("t-reviewer", "reviewer", "codex"),
]

# The six allow-listed generative-UI components + one off-list refusal. This is
# the exact vocabulary taught by the agui-author skill.
REEL = [
    ("agent_card", {"name": "code_supervisor", "provider": "kiro_cli", "status": "orchestrating"}, "render"),
    ("progress", {"label": "Developer worker: implementing auth module", "value": 0.42}, "render"),
    ("diff_summary", {"title": "Refactor auth", "files": [{"path": "security/auth.py", "additions": 74, "deletions": 3}]}, "render"),
    ("metric", {"label": "tokens used (fleet)", "value": 12840, "unit": "tok"}, "render"),
    ("choice_prompt", {"question": "Which base branch?", "choices": [{"label": "main", "value": "main"}, {"label": "release", "value": "release"}]}, "render"),
    ("approval_card", {"title": "Deploy to production?", "detail": "3 files changed, 1 DB migration", "risk": "high"}, "render"),
    ("iframe", {"src": "https://evil.example/x"}, "refuse"),  # off-list — MUST be refused
]


class _EmptyBus:
    """Terminating live-tail so the stream ends after the real-log replay."""

    def publish(self, event):  # noqa: ANN001
        pass

    def register(self, overflow_close=False):  # noqa: ANN001
        return object()

    def unregister(self, queue):  # noqa: ANN001
        pass

    async def drain(self, queue):  # noqa: ANN001
        return
        yield  # pragma: no cover


async def _drive_fleet(pub: EventLogPublisher) -> None:
    await pub.on_post_create_session(
        PostCreateSessionEvent(session_id=SESSION, session_name=SESSION)
    )
    for tid, agent, provider in FLEET:
        await pub.on_post_create_terminal(
            PostCreateTerminalEvent(
                session_id=SESSION, terminal_id=tid, agent_name=agent, provider=provider
            )
        )
    for sender, receiver, kind in [
        ("t-supervisor", "t-developer", "assign"),
        ("t-developer", "t-reviewer", "handoff"),
        ("t-reviewer", "t-supervisor", "handoff"),
    ]:
        await pub.on_post_send_message(
            PostSendMessageEvent(
                session_id=SESSION,
                sender=sender,
                receiver=receiver,
                orchestration_type=kind,
                message="[body excluded by privacy boundary]",
            )
        )
    for tid, agent, _ in FLEET:
        await pub.on_post_kill_terminal(
            PostKillTerminalEvent(session_id=SESSION, terminal_id=tid, agent_name=agent)
        )


def _drive_generative_reel(client: TestClient) -> list[dict]:
    """POST each component to /agui/v1/emit_ui; record the normalized intent + outcome."""
    out: list[dict] = []
    for seq, (component, props, expect) in enumerate(REEL, start=1):
        resp = client.post("/agui/v1/emit_ui", json={"component": component, "props": props})
        accepted = resp.status_code == 200 and bool(resp.json().get("ok"))
        out.append({"seq": seq, "component": component, "props": props, "expect": expect, "accepted": accepted})
    return out


def _entry_to_dict(e: object) -> dict:
    try:
        return _asdict(e)
    except TypeError:
        return e if isinstance(e, dict) else vars(e)


def main() -> int:
    FIXTURES.mkdir(parents=True, exist_ok=True)
    since = (datetime.now(timezone.utc) - timedelta(seconds=2)).isoformat()

    # 1) Drive the real production lifecycle path (publisher -> event log).
    asyncio.run(_drive_fleet(EventLogPublisher()))

    mine = [
        r
        for r in get_event_log().history(since=since)
        if r.get("session_name") == SESSION or (r.get("terminal_id") or "").startswith("t-")
    ]
    if not mine:
        print("FAIL: no fleet events reached the event log", file=sys.stderr)
        return 1

    # 2) Read frames back off the REAL /agui/v1/stream, and drive the emit_ui reel.
    from unittest.mock import patch

    with patch("cli_agent_orchestrator.services.sse_bus.get_bus", lambda: _EmptyBus()):
        client = TestClient(app, base_url="http://localhost")
        reel = _drive_generative_reel(client)
        raw: list[str] = []
        with client.stream("GET", "/agui/v1/stream", params={"since": since}) as resp:
            assert resp.status_code == 200, resp.status_code
            for line in resp.iter_lines():
                raw.append(line)

    wire = []
    for line in raw:
        if line.startswith("data: "):
            try:
                wire.append(json.loads(line[6:]))
            except json.JSONDecodeError:
                pass
    fleet_wire = [f for f in wire if SESSION in json.dumps(f) or "t-" in json.dumps(f)]

    # Privacy boundary: no message bodies anywhere on the wire.
    body_leak = any("body excluded" in json.dumps(f) for f in wire) or any(
        "message" in f and f.get("message") for f in wire if isinstance(f, dict)
    )

    # 3) Fold the same session through the L2 constructs (projections).
    from cli_agent_orchestrator.services.agui_stream import to_agui_event

    dash = SupervisorDashboardStream(RecordingUiEmitter())
    timeline = MultiAgentSessionTimeline(RecordingUiEmitter())
    for rec in mine:
        atype, adata = to_agui_event(rec)
        dash.handle_frame(atype, adata, event_id=rec.get("id"))
        timeline.handle_frame(atype, adata, event_id=rec.get("id"))

    # 4) Write the committed evidence bundle the docsite dojo renders.
    (FIXTURES / "frames.jsonl").write_text("\n".join(json.dumps(f) for f in fleet_wire) + "\n")
    (FIXTURES / "dashboard.json").write_text(json.dumps(dash.supervisor_snapshot(), indent=2) + "\n")
    (FIXTURES / "timeline.json").write_text(
        json.dumps([_entry_to_dict(e) for e in timeline.entries()], indent=2) + "\n"
    )
    (FIXTURES / "generative-reel.jsonl").write_text(
        "\n".join(json.dumps(r) for r in reel) + "\n"
    )
    (FIXTURES / "manifest.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "session_name": SESSION,
                "capture_mode": "production-path",
                "fleet": [
                    {"terminal_id": t, "agent": a, "provider": p} for t, a, p in FLEET
                ],
                "providers": sorted({p for _, _, p in FLEET}),
                "counts": {
                    "lifecycle_frames": len(fleet_wire),
                    "delegations": len(timeline.entries()),
                    "generative_components_valid": sum(1 for r in reel if r["expect"] == "render"),
                    "generative_components_offlist": sum(1 for r in reel if r["expect"] == "refuse"),
                },
                "privacy": {"metadata_only": True, "message_bodies_present": bool(body_leak)},
            },
            indent=2,
        )
        + "\n"
    )

    # 5) THE GATE (shift-left): assert the contract before this is usable.
    valid_ok = all(r["accepted"] for r in reel if r["expect"] == "render")
    offlist_refused = all(not r["accepted"] for r in reel if r["expect"] == "refuse")
    print(f"[dojo-capture] session={SESSION}")
    print(f"[dojo-capture] AG-UI fleet frames on /agui/v1/stream: {len(fleet_wire)}")
    print(f"[dojo-capture] generative components accepted: {sum(r['accepted'] for r in reel)}/7 (6 expected)")
    print(f"[dojo-capture] off-list refused: {offlist_refused}  privacy_ok: {not body_leak}")
    if not fleet_wire:
        print("FAIL: no fleet frames on the wire", file=sys.stderr)
        return 1
    if not valid_ok:
        print("FAIL: not all six allow-listed components were accepted", file=sys.stderr)
        return 1
    if not offlist_refused:
        print("FAIL: off-list component was NOT refused (safety gate)", file=sys.stderr)
        return 1
    if body_leak:
        print("FAIL: message body leaked onto the wire (privacy gate)", file=sys.stderr)
        return 1
    print("[dojo-capture] PASS: real fleet + generative reel captured; contract holds.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
