"""OpenCode agent config survives an unrelated plugin add/remove lifecycle.

**Validates: Requirement 2 of the pr584-review-5209646575 spec.**

Reproduces review pullrequestreview-5209646575's P1 F1 exactly and turns it into a
regression test. At the reviewed head, ``_materialize_opencode_mcp`` replaced the
whole ``agent.<id>.tools`` object on the has-servers branch and deleted the whole
``agent.<id>`` entry on the no-servers branch. Because
``refresh_installed_agents_for_plugin_mcp`` re-runs the delivery for every installed
OpenCode agent on every plugin add/remove, an unrelated plugin operation erased a
user's ``model`` selection and custom grants and could drop an explicit denial such
as ``bash: false`` — widening the next agent's permissions.

This test drives ``_materialize_opencode_mcp`` directly (the exact seam the two
call sites live in), first with one delivered server, then with none — the add then
the remove of the reproduction — against a pre-populated agent entry.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import cli_agent_orchestrator.agent_plugins.store as store_module
import cli_agent_orchestrator.services.install_service as install_module
import cli_agent_orchestrator.utils.opencode_config as cfg_module
from cli_agent_orchestrator.agent_plugins.mcp_delivery import McpDeliveryResult
from cli_agent_orchestrator.services.install_service import _materialize_opencode_mcp

PRE_POPULATED = {
    "agent": {
        "worker": {
            "model": "custom/model",
            "tools": {"bash": False, "user*": True},
        }
    }
}


@pytest.fixture
def opencode_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redirect OPENCODE_CONFIG_FILE and the plugin store to temp dirs.

    The plugin-store roots are redirected so the delivered server's command — which
    a real delivery expands to a path under ``PLUGIN_ROOT`` — resolves inside the
    store, exercising the true CAO-ownership containment signal rather than a
    contrived one.
    """
    config_file = tmp_path / "opencode" / "opencode.json"
    config_file.parent.mkdir(parents=True)
    config_file.write_text(json.dumps(PRE_POPULATED), encoding="utf-8")
    monkeypatch.setattr(cfg_module, "OPENCODE_CONFIG_FILE", config_file)

    plugins_dir = tmp_path / "plugins"
    data_dir = tmp_path / "plugin-data"
    plugins_dir.mkdir()
    data_dir.mkdir()
    monkeypatch.setattr(store_module, "AGENT_PLUGINS_DIR", plugins_dir)
    monkeypatch.setattr(store_module, "AGENT_PLUGIN_DATA_DIR", data_dir)
    # `install_service` imported `InstalledPluginStore` by name; it reads the module
    # globals above at construction, so no further patch is needed there.
    _ = install_module  # keep the import meaningful for readers
    return config_file


def _plugin_server(plugins_dir: Path) -> dict:
    """A delivered server whose command resolves inside the plugin store."""
    return {
        "plugin-tools": {
            "type": "stdio",
            "command": str(plugins_dir / "demo-plugin" / "bin" / "server"),
            "args": ["--serve"],
        }
    }


def _delivery(servers: dict) -> McpDeliveryResult:
    return McpDeliveryResult(
        servers=dict(servers),
        owners={name: "demo-plugin" for name in servers},
    )


def _worker(config_file: Path) -> dict:
    return json.loads(config_file.read_text())["agent"]["worker"]


class TestAnUnrelatedPluginLifecycleLeavesUserConfigIntact:
    def test_install_then_remove_preserves_model_grants_and_denials(self, opencode_config: Path):
        plugin_server = _plugin_server(opencode_config.parent.parent / "plugins")
        # ── add a plugin delivering one server ───────────────────────────────
        _materialize_opencode_mcp(
            "worker", dict(plugin_server), _delivery(plugin_server), agent_name="worker"
        )
        worker = _worker(opencode_config)
        assert worker["model"] == "custom/model", "the model must survive an install"
        assert worker["tools"]["bash"] is False, "an explicit denial must survive"
        assert worker["tools"]["user*"] is True, "a user grant must survive"
        assert worker["tools"]["plugin-tools*"] is True, "the plugin grant is added"

        # ── remove the plugin (no servers delivered) ─────────────────────────
        _materialize_opencode_mcp("worker", {}, _delivery({}), agent_name="worker")
        assert (
            "worker" in json.loads(opencode_config.read_text())["agent"]
        ), "the agent entry must NOT be deleted on removal"
        worker = _worker(opencode_config)
        assert worker["model"] == "custom/model", "the model must survive removal"
        assert worker["tools"]["bash"] is False, "the denial must survive removal"
        assert worker["tools"]["user*"] is True, "the user grant must survive removal"
        assert "plugin-tools*" not in worker["tools"], "only the CAO grant is withdrawn"

    def test_remove_on_a_pristine_user_agent_is_a_no_op_for_user_fields(
        self, opencode_config: Path
    ):
        """A removal for an agent that never got a CAO grant touches nothing of the
        user's."""
        _materialize_opencode_mcp("worker", {}, _delivery({}), agent_name="worker")
        worker = _worker(opencode_config)
        assert worker["model"] == "custom/model"
        assert worker["tools"]["bash"] is False
        assert worker["tools"]["user*"] is True
