# ABOUTME: Shift-left gate for the AG-UI Dojo fixtures — validates the frame contract,
# ABOUTME: the metadata-only privacy boundary, and the generative-UI allow-list, with no server.
"""Frame-contract tests for the committed CAO AG-UI Dojo fixture bundle.

These run in CI ahead of the pipeline (shift-left): if the committed fixtures
drift from the AG-UI frame contract, violate the metadata-only privacy boundary,
or the off-list generative component is not marked for refusal, the suite fails
before any renderer or recorder runs. See ``examples/ag-ui/ag-ui-dojo/THEMES.md``.
"""

from __future__ import annotations

import json
import pathlib

import pytest

FIXTURES = (
    pathlib.Path(__file__).resolve().parents[3]
    / "examples"
    / "ag-ui"
    / "ag-ui-dojo"
    / "fixtures"
)

# The AG-UI typed events CAO emits (docs/agui.md).
ALLOWED_AGUI_TYPES = {
    "RUN_STARTED",
    "RUN_FINISHED",
    "RUN_ERROR",
    "STEP_STARTED",
    "STEP_FINISHED",
    "TOOL_CALL_START",
    "TOOL_CALL_END",
    "TOOL_CALL_RESULT",
    "TEXT_MESSAGE_CONTENT",
    "STATE_SNAPSHOT",
    "STATE_DELTA",
    "GENERATIVE_UI",
}

# The closed generative-UI allow-list (services/agui_stream.py GENERATIVE_UI_COMPONENTS).
GENERATIVE_ALLOW_LIST = {
    "approval_card",
    "choice_prompt",
    "diff_summary",
    "progress",
    "metric",
    "agent_card",
}

# Substrings that would indicate a leaked message body (privacy boundary breach).
BODY_LEAK_MARKERS = ("body excluded", "message\":")


def _read_jsonl(path: pathlib.Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def test_fixture_bundle_exists() -> None:
    for name in ("frames.jsonl", "dashboard.json", "timeline.json", "generative-reel.jsonl", "manifest.json"):
        assert (FIXTURES / name).exists(), f"missing fixture: {name}"


def test_frames_conform_to_agui_type_contract() -> None:
    frames = _read_jsonl(FIXTURES / "frames.jsonl")
    assert frames, "frames.jsonl is empty"
    for f in frames:
        assert f.get("agui_type") in ALLOWED_AGUI_TYPES, f"bad agui_type: {f.get('agui_type')}"
        assert f.get("event_id"), "every frame must carry an event_id cursor"


def test_tool_call_lifecycle_is_well_formed() -> None:
    """Every TOOL_CALL_END must close a TOOL_CALL_START (no orphan closers)."""
    frames = _read_jsonl(FIXTURES / "frames.jsonl")
    opened = {f["tool_call_id"] for f in frames if f.get("agui_type") == "TOOL_CALL_START"}
    for f in frames:
        if f.get("agui_type") in ("TOOL_CALL_END", "TOOL_CALL_RESULT"):
            assert f.get("tool_call_id") in opened, f"orphan closer: {f.get('tool_call_id')}"


def test_privacy_boundary_no_message_bodies() -> None:
    """The AG-UI surface is metadata-only: no message text on the wire."""
    blob = (FIXTURES / "frames.jsonl").read_text()
    for marker in BODY_LEAK_MARKERS:
        assert marker not in blob, f"privacy boundary breach: found {marker!r} in frames.jsonl"
    # Delegation frames carry only sender/receiver/orchestration_type metadata.
    for f in _read_jsonl(FIXTURES / "frames.jsonl"):
        md = f.get("metadata") or {}
        assert "message" not in md and "body" not in md, "delegation metadata leaked a body"


def test_generative_reel_has_six_valid_and_one_offlist() -> None:
    reel = _read_jsonl(FIXTURES / "generative-reel.jsonl")
    valid = [r for r in reel if r["expect"] == "render"]
    offlist = [r for r in reel if r["expect"] == "refuse"]
    assert len(valid) == 6, "reel must exercise all six allow-listed components"
    assert len(offlist) == 1, "reel must include exactly one off-list refusal"
    for r in valid:
        assert r["component"] in GENERATIVE_ALLOW_LIST, f"{r['component']} not in allow-list"
    for r in offlist:
        assert r["component"] not in GENERATIVE_ALLOW_LIST, "off-list case must be off-list"


def test_manifest_declares_metadata_only() -> None:
    manifest = json.loads((FIXTURES / "manifest.json").read_text())
    assert manifest["privacy"]["metadata_only"] is True
    assert manifest["privacy"]["message_bodies_present"] is False
    # The headline multi-provider angle: more than one provider in the fleet.
    assert len(set(manifest["providers"])) >= 2, "dojo must showcase multi-provider orchestration"


def test_dashboard_and_timeline_shapes() -> None:
    dash = json.loads((FIXTURES / "dashboard.json").read_text())
    assert {"active_sessions", "counts", "by_provider", "last_activity"} <= set(dash)
    timeline = json.loads((FIXTURES / "timeline.json").read_text())
    assert isinstance(timeline, list) and timeline, "timeline must have entries"
    for e in timeline:
        assert {"id", "kind", "orchestration_type", "sender", "receiver", "status"} <= set(e)


if __name__ == "__main__":  # allow `python test_dojo_fixtures.py` as a quick gate
    raise SystemExit(pytest.main([__file__, "-q"]))
