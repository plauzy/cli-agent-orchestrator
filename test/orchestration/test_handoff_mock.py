"""Orchestration-layer tests using mock_cli provider (Tier 2, zero credentials).

W3 workstream: handoff lifecycle with credential-free provider.

These tests exercise the full handoff flow (spawn → send → wait for COMPLETED →
extract → exit) via the mock_cli provider, which does not require any external
CLI authentication. Tests run in fork CI without secrets and verify that CAO's
orchestration layer (terminal_service, provider_manager, output extraction) work
correctly regardless of the underlying CLI.

See docs/mock-cli-provider.md for the design rationale.

Run: uv run pytest test/orchestration/test_handoff_mock.py -v --no-cov
     uv run pytest test/orchestration/test_handoff_mock.py -v -k golden --no-cov
"""

from __future__ import annotations

import contextlib
import time
import uuid
from test.fixtures.cao_server import CaoServer

import pytest
import requests


@pytest.mark.orchestration
class TestHandoffMockGoldenPath:
    """Happy path: send message, reach COMPLETED, extract output."""

    def test_golden_path_simple_echo(self, cao_server: CaoServer) -> None:
        """Send a simple message and verify round-trip extraction."""
        session_name = f"w3-golden-{uuid.uuid4().hex[:8]}"
        terminal_id = None
        actual_session = None

        try:
            # Create terminal with mock_cli provider
            resp = requests.post(
                f"{cao_server.url}/sessions",
                params={
                    "provider": "mock_cli",
                    "agent_profile": "developer",
                    "session_name": session_name,
                },
            )
            assert resp.status_code in (200, 201), f"create failed: {resp.status_code} {resp.text}"
            data = resp.json()
            terminal_id = data["id"]
            actual_session = data["session_name"]

            # Wait for IDLE
            for _ in range(30):
                status_resp = requests.get(f"{cao_server.url}/terminals/{terminal_id}")
                assert status_resp.status_code == 200
                status = status_resp.json().get("status")
                if status in ("idle", "completed"):
                    break
                time.sleep(0.5)
            assert status in ("idle", "completed"), f"init: unexpected status {status}"

            # Send message via handoff
            msg = "hello-W3-orchestration"
            input_resp = requests.post(
                f"{cao_server.url}/terminals/{terminal_id}/input",
                params={"message": msg},
            )
            assert input_resp.status_code == 200

            # Poll for COMPLETED
            time.sleep(1.0)
            for _ in range(30):
                status_resp = requests.get(f"{cao_server.url}/terminals/{terminal_id}")
                assert status_resp.status_code == 200
                status = status_resp.json().get("status")
                if status == "completed":
                    break
                if status == "error":
                    raise AssertionError("unexpected error status during handoff")
                time.sleep(0.5)
            assert status == "completed", f"handoff: did not reach COMPLETED (status={status})"

            # Extract output
            output_resp = requests.get(
                f"{cao_server.url}/terminals/{terminal_id}/output",
                params={"mode": "last"},
            )
            assert output_resp.status_code == 200
            extracted = output_resp.json().get("output", "").strip()

            # Verify round-trip
            assert extracted == msg, f"extraction mismatch: expected {msg!r}, got {extracted!r}"

        finally:
            if terminal_id and actual_session:
                with contextlib.suppress(Exception):
                    requests.post(f"{cao_server.url}/terminals/{terminal_id}/exit")
                time.sleep(1.0)
                with contextlib.suppress(Exception):
                    requests.delete(f"{cao_server.url}/sessions/{actual_session}")

    def test_golden_path_multiple_turns(self, cao_server: CaoServer) -> None:
        """Send multiple messages and verify each round-trip."""
        session_name = f"w3-multi-{uuid.uuid4().hex[:8]}"
        terminal_id = None
        actual_session = None

        try:
            resp = requests.post(
                f"{cao_server.url}/sessions",
                params={
                    "provider": "mock_cli",
                    "agent_profile": "developer",
                    "session_name": session_name,
                },
            )
            assert resp.status_code in (200, 201)
            terminal_id = resp.json()["id"]
            actual_session = resp.json()["session_name"]

            # Wait for IDLE
            for _ in range(30):
                s = requests.get(f"{cao_server.url}/terminals/{terminal_id}").json().get("status")
                if s in ("idle", "completed"):
                    break
                time.sleep(0.5)

            # Sequence of messages
            messages = ["first-message", "second-message", "third-message"]
            for msg in messages:
                requests.post(
                    f"{cao_server.url}/terminals/{terminal_id}/input",
                    params={"message": msg},
                )
                time.sleep(1.0)
                # Verify COMPLETED after each
                s = requests.get(f"{cao_server.url}/terminals/{terminal_id}").json().get("status")
                assert s == "completed", f"msg {msg!r}: status={s}"
                # Verify extraction
                extracted = (
                    requests.get(
                        f"{cao_server.url}/terminals/{terminal_id}/output",
                        params={"mode": "last"},
                    )
                    .json()
                    .get("output", "")
                    .strip()
                )
                assert extracted == msg, f"extraction: expected {msg!r}, got {extracted!r}"

        finally:
            if terminal_id and actual_session:
                with contextlib.suppress(Exception):
                    requests.post(f"{cao_server.url}/terminals/{terminal_id}/exit")
                time.sleep(1.0)
                with contextlib.suppress(Exception):
                    requests.delete(f"{cao_server.url}/sessions/{actual_session}")


@pytest.mark.orchestration
class TestHandoffMockFailurePath:
    """Failure visibility: __mock_error__ injects ERROR status."""

    def test_failure_path_mock_error_injection(self, cao_server: CaoServer) -> None:
        """Send __mock_error__ magic string and verify status transitions to ERROR.

        This test validates Tenet #1 (provider-onboarding as a first-class concern,
        failure visibility wins). The orchestrator must surface provider-side errors
        as named ERROR status, not as cryptic extraction or timeout failures.
        """
        session_name = f"w3-error-{uuid.uuid4().hex[:8]}"
        terminal_id = None
        actual_session = None

        try:
            resp = requests.post(
                f"{cao_server.url}/sessions",
                params={
                    "provider": "mock_cli",
                    "agent_profile": "developer",
                    "session_name": session_name,
                },
            )
            assert resp.status_code in (200, 201)
            terminal_id = resp.json()["id"]
            actual_session = resp.json()["session_name"]

            # Wait for IDLE
            for _ in range(30):
                s = requests.get(f"{cao_server.url}/terminals/{terminal_id}").json().get("status")
                if s in ("idle", "completed"):
                    break
                time.sleep(0.5)

            # Inject error via magic string
            requests.post(
                f"{cao_server.url}/terminals/{terminal_id}/input",
                params={"message": "__mock_error__"},
            )
            time.sleep(1.5)

            # Status must transition to ERROR
            status = requests.get(f"{cao_server.url}/terminals/{terminal_id}").json().get("status")
            assert status == "error", f"error injection: expected status=error, got {status}"

            # Full output must contain the error indicator (for debugging)
            full_output = (
                requests.get(
                    f"{cao_server.url}/terminals/{terminal_id}/output",
                    params={"mode": "full"},
                )
                .json()
                .get("output", "")
            )
            assert (
                "ERROR: mock failure injected" in full_output
            ), f"error indicator not found in output:\n{full_output[-500:]}"

        finally:
            if terminal_id and actual_session:
                with contextlib.suppress(Exception):
                    requests.post(f"{cao_server.url}/terminals/{terminal_id}/exit")
                time.sleep(1.0)
                with contextlib.suppress(Exception):
                    requests.delete(f"{cao_server.url}/sessions/{actual_session}")
