"""Tests for the ``cao zellij`` CLI group (Phase 2).

Placed under ``test/cli/commands/`` to match the existing convention
for CLI subcommand tests in this repo.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner

from cli_agent_orchestrator.cli.commands import zellij as zellij_module
from cli_agent_orchestrator.cli.commands.zellij import zellij


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


class TestInstall:
    def test_copies_layout_and_plugin(self, runner, tmp_path, monkeypatch):
        # Stage fake source assets resolved by _resolve_asset.
        src_layout = tmp_path / "src" / "layouts" / "cao.kdl"
        src_layout.parent.mkdir(parents=True)
        src_layout.write_text("layout {}\n")
        src_plugin = tmp_path / "src" / "zellaude.wasm"
        src_plugin.write_bytes(b"\x00asm")

        def fake_resolve(relpath: str) -> Path:
            return tmp_path / "src" / relpath

        monkeypatch.setattr(zellij_module, "_resolve_asset", fake_resolve)
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
        monkeypatch.setattr(zellij_module.sys, "platform", "linux")

        result = runner.invoke(zellij, ["install"])

        assert result.exit_code == 0, result.output
        assert (tmp_path / "xdg" / "zellij" / "layouts" / "cao.kdl").read_text() == "layout {}\n"
        assert (
            tmp_path / "xdg" / "zellij" / "plugins" / "zellaude.wasm"
        ).read_bytes() == b"\x00asm"
        assert "Installed layout" in result.output
        assert "Installed plugin" in result.output

    def test_skips_on_windows(self, runner, monkeypatch):
        monkeypatch.setattr(zellij_module.sys, "platform", "win32")
        result = runner.invoke(zellij, ["install"])
        assert result.exit_code != 0
        assert "Windows" in result.output


class TestStart:
    def test_start_invokes_zellij_with_layout_and_env(self, runner, tmp_path, monkeypatch):
        layouts_dir = tmp_path / "xdg" / "zellij" / "layouts"
        layouts_dir.mkdir(parents=True)
        layout_path = layouts_dir / "cao.kdl"
        layout_path.write_text("layout {}\n")

        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
        monkeypatch.setattr(zellij_module.sys, "platform", "linux")
        monkeypatch.setattr(zellij_module.shutil, "which", lambda b: "/usr/bin/zellij")

        captured: dict[str, object] = {}

        def fake_call(argv, env):
            captured["argv"] = argv
            captured["env"] = env
            return 0

        monkeypatch.setattr(zellij_module.subprocess, "call", fake_call)

        result = runner.invoke(zellij, ["start"])

        # SystemExit(0) is propagated; CliRunner reports exit_code == 0.
        assert result.exit_code == 0, result.output
        argv = captured["argv"]
        assert argv[0] == "zellij"
        assert "--layout" in argv
        assert str(layout_path) in argv
        env = captured["env"]
        assert env.get("CAO_ZELLIJ_ENABLED") == "true"

    def test_errors_when_zellij_binary_missing(self, runner, tmp_path, monkeypatch):
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
        monkeypatch.setattr(zellij_module.sys, "platform", "linux")
        monkeypatch.setattr(zellij_module.shutil, "which", lambda b: None)

        result = runner.invoke(zellij, ["start"])
        assert result.exit_code != 0
        assert "zellij" in result.output.lower()

    def test_errors_when_layout_not_installed(self, runner, tmp_path, monkeypatch):
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
        monkeypatch.setattr(zellij_module.sys, "platform", "linux")
        monkeypatch.setattr(zellij_module.shutil, "which", lambda b: "/usr/bin/zellij")

        result = runner.invoke(zellij, ["start"])
        assert result.exit_code != 0
        assert "install" in result.output.lower()


class TestTail:
    def test_prints_streamed_events(self, runner, monkeypatch):
        events = [
            {"type": "session.created", "session_name": "cao-x"},
            {
                "type": "asi.mitigation",
                "task_class": "review",
                "overall": 0.2,
                "severity": "kill",
            },
        ]

        def fake_stream(url):
            assert url.endswith("/events")
            yield from events

        monkeypatch.setattr(zellij_module, "_stream_events", fake_stream)

        result = runner.invoke(zellij, ["tail", "--max-events", "2"])

        assert result.exit_code == 0, result.output
        assert "session.created" in result.output
        assert "asi.mitigation" in result.output
        assert "task_class=review" in result.output

    def test_reconnects_on_stream_failure(self, runner, monkeypatch):
        attempts = {"n": 0}

        def fake_stream(url):
            attempts["n"] += 1
            if attempts["n"] == 1:
                raise RuntimeError("boom")
            yield {"type": "session.created", "session_name": "cao-y"}

        monkeypatch.setattr(zellij_module, "_stream_events", fake_stream)
        # Don't actually sleep during the test.
        monkeypatch.setattr(zellij_module.time, "sleep", lambda _s: None)

        result = runner.invoke(zellij, ["tail", "--max-events", "1"])

        assert result.exit_code == 0, result.output
        assert attempts["n"] == 2
        assert "session.created" in result.output


class TestStreamEventsParsing:
    def test_skips_blank_and_non_data_lines(self, monkeypatch):
        # Build a fake response whose iter_lines returns SSE-formatted lines.
        lines = [
            "",
            ": ping",
            'data: {"type": "session.created", "session_name": "cao-z"}',
            "",
            "data:",
            'data: {"type": "session.killed", "session_name": "cao-z"}',
        ]

        class FakeResponse:
            def raise_for_status(self) -> None: ...

            def iter_lines(self, decode_unicode: bool = False):
                yield from lines

        def fake_get(url, stream, timeout):  # noqa: D401
            return FakeResponse()

        monkeypatch.setattr(zellij_module.requests, "get", fake_get)

        out = list(zellij_module._stream_events("http://x/events"))
        assert out == [
            {"type": "session.created", "session_name": "cao-z"},
            {"type": "session.killed", "session_name": "cao-z"},
        ]
