"""Execution gate for the agent-plugin surface (#1393: graduated, default-on).

The surface runs by default. ``CAO_AGENT_PLUGINS_ENABLED`` set to a falsy spelling
(``0``, ``false``, ``no``, ``off``) is a kill switch that restores the pre-graduation
behaviour exactly: the four ``/plugins*`` routes answer 404 as an unregistered path would,
and every ``cao plugin`` subcommand refuses.

Every test here manages the environment variable itself (``monkeypatch.delenv`` or
``setenv`` rather than assuming a clean environment), so none depends on the package
``conftest`` or on the shell the suite runs in.
"""

from __future__ import annotations

import pytest
from click.testing import CliRunner
from fastapi import HTTPException
from fastapi.testclient import TestClient

from cli_agent_orchestrator.agent_plugins.gate import ENV_VAR, agent_plugins_surface_enabled
from cli_agent_orchestrator.cli.main import cli


@pytest.fixture
def gate_off(monkeypatch):
    """The kill switch: an explicit falsy value."""
    monkeypatch.setenv(ENV_VAR, "0")


@pytest.fixture
def gate_on(monkeypatch):
    monkeypatch.setenv(ENV_VAR, "1")


@pytest.fixture
def gate_default(monkeypatch):
    """The variable is absent: the graduated default."""
    monkeypatch.delenv(ENV_VAR, raising=False)


class TestPredicate:
    """The single predicate both surfaces consult."""

    def test_absent_env_var_means_enabled(self, gate_default):
        assert agent_plugins_surface_enabled() is True

    def test_empty_env_var_means_enabled(self, monkeypatch):
        monkeypatch.setenv(ENV_VAR, "")
        assert agent_plugins_surface_enabled() is True

    @pytest.mark.parametrize("value", ["1", "true", "TRUE", "yes", " Yes ", "enabled"])
    def test_truthy_and_unrecognised_spellings_keep_it_enabled(self, monkeypatch, value):
        monkeypatch.setenv(ENV_VAR, value)
        assert agent_plugins_surface_enabled() is True

    @pytest.mark.parametrize("value", ["0", "false", "FALSE", "no", "off", " Off "])
    def test_falsy_spellings_close_it(self, monkeypatch, value):
        monkeypatch.setenv(ENV_VAR, value)
        assert agent_plugins_surface_enabled() is False

    def test_the_value_is_read_per_call_not_at_import(self, monkeypatch):
        """An operator exporting the switch must not have to restart the process."""
        monkeypatch.delenv(ENV_VAR, raising=False)
        assert agent_plugins_surface_enabled() is True
        monkeypatch.setenv(ENV_VAR, "0")
        assert agent_plugins_surface_enabled() is False
        monkeypatch.setenv(ENV_VAR, "1")
        assert agent_plugins_surface_enabled() is True


@pytest.fixture
def api_client():
    from cli_agent_orchestrator.api.main import app

    return TestClient(app, base_url="http://localhost")


#: The whole surface, so a future route cannot be added ungated without noticing.
PLUGIN_ROUTES = [
    ("get", "/plugins", None),
    ("post", "/plugins", {"source": "/tmp/nonexistent-plugin"}),
    ("post", "/plugins/validate", {"source": "/tmp/nonexistent-plugin"}),
    ("delete", "/plugins/demo", None),
]


class TestApiGate:
    @pytest.mark.parametrize("method,path,body", PLUGIN_ROUTES)
    def test_every_route_is_absent_when_switched_off(
        self, api_client, gate_off, method, path, body
    ):
        response = getattr(api_client, method)(path, **({"json": body} if body else {}))

        assert response.status_code == 404
        assert "disabled" in response.json()["detail"].lower()

    def test_the_gate_precedes_the_work(self, api_client, gate_off, monkeypatch):
        """A 404 must come from the gate, not from the install failing anyway."""

        def _explode(*args, **kwargs):  # pragma: no cover - must never be reached
            raise AssertionError("install ran behind a closed gate")

        monkeypatch.setattr("cli_agent_orchestrator.agent_plugins.installer.install", _explode)

        response = api_client.post("/plugins", json={"source": "/tmp/nonexistent-plugin"})

        assert response.status_code == 404

    @pytest.mark.parametrize("path", ["/plugins", "/plugins/validate"])
    def test_a_malformed_body_does_not_disclose_the_route(self, api_client, gate_off, path):
        """The gate must precede request *validation*, not just the handler body.

        Found by an independent audit of the first attempt, which applied the gate
        as each handler's first statement. FastAPI validates the body — and solves
        the scope dependency — before the handler runs, so a malformed payload came
        back 422 and an unauthorized caller 401/403, each of which tells a prober
        that the gated route exists. An absent surface answers everything 404, which
        is what a route-level dependency delivers.
        """
        response = api_client.post(path, json={"not-the-expected-field": 1})

        assert response.status_code == 404, (
            "a 422 discloses that the gated route exists; the gate must be solved "
            "before body validation"
        )

    def test_the_gate_outranks_the_scope_dependency(self, api_client, gate_off, monkeypatch):
        """With auth on, a closed surface must 404 rather than 401/403."""
        import cli_agent_orchestrator.api.main as api_main

        def _unauthorized(*args, **kwargs):
            raise HTTPException(status_code=401, detail="unauthorized")

        monkeypatch.setattr(api_main, "require_any_scope", lambda *a, **k: _unauthorized)

        response = api_client.get("/plugins")

        assert response.status_code == 404

    @pytest.mark.parametrize("state", ["gate_default", "gate_on"])
    def test_the_route_answers_by_default(self, api_client, request, state, tmp_path, monkeypatch):
        request.getfixturevalue(state)
        monkeypatch.setattr(
            "cli_agent_orchestrator.agent_plugins.store.AGENT_PLUGINS_DIR", tmp_path / "p"
        )
        monkeypatch.setattr(
            "cli_agent_orchestrator.agent_plugins.store.AGENT_PLUGIN_DATA_DIR", tmp_path / "d"
        )

        response = api_client.get("/plugins")

        assert response.status_code == 200
        assert response.json()["plugins"] == []

    def test_switching_the_flag_back_on_restores_the_route(
        self, api_client, gate_on, tmp_path, monkeypatch
    ):
        monkeypatch.setattr(
            "cli_agent_orchestrator.agent_plugins.store.AGENT_PLUGINS_DIR", tmp_path / "p"
        )
        monkeypatch.setattr(
            "cli_agent_orchestrator.agent_plugins.store.AGENT_PLUGIN_DATA_DIR", tmp_path / "d"
        )

        response = api_client.get("/plugins")

        assert response.status_code == 200
        assert response.json()["plugins"] == []


class TestCliGate:
    @pytest.mark.parametrize(
        "argv",
        [
            ["plugin", "list"],
            ["plugin", "add", "/tmp/nonexistent-plugin"],
            ["plugin", "validate", "/tmp/nonexistent-plugin"],
            ["plugin", "remove", "demo"],
        ],
    )
    def test_every_verb_refuses_when_switched_off(self, gate_off, argv):
        result = CliRunner().invoke(cli, argv)

        assert result.exit_code != 0
        assert ENV_VAR in result.output

    def test_the_refusal_says_how_to_reopen_the_surface(self, gate_off):
        result = CliRunner().invoke(cli, ["plugin", "list"])

        assert result.exit_code != 0
        output = " ".join(result.output.split())
        assert "disabled by CAO_AGENT_PLUGINS_ENABLED" in output
        assert "not released yet" not in output

    @pytest.mark.parametrize("state", ["gate_off", "gate_on", "gate_default"])
    def test_the_group_help_explains_the_switch_and_keeps_repo_references_out(self, request, state):
        """``cao plugin --help`` prints the group docstring with or without the gate."""
        request.getfixturevalue(state)
        result = CliRunner().invoke(cli, ["plugin", "--help"])

        assert result.exit_code == 0, result.output
        output = " ".join(result.output.split())
        assert "Set CAO_AGENT_PLUGINS_ENABLED=0" in output
        assert "pending graduation" not in output
        assert "#573" not in output and "maintainer decision" not in output

    def test_the_gate_module_records_the_graduation(self):
        from cli_agent_orchestrator.agent_plugins import gate

        doc = " ".join((gate.__doc__ or "").split())
        assert "graduated (#1393)" in doc
        assert "default-on" in doc
        assert "maintainer decision M1" not in doc

    def test_the_gate_precedes_the_work(self, gate_off, monkeypatch):
        def _explode(*args, **kwargs):  # pragma: no cover - must never be reached
            raise AssertionError("install ran behind a closed gate")

        monkeypatch.setattr("cli_agent_orchestrator.cli.commands.agent_plugin.install", _explode)

        result = CliRunner().invoke(cli, ["plugin", "add", "/tmp/nonexistent-plugin"])

        assert result.exit_code != 0

    @pytest.mark.parametrize("state", ["gate_default", "gate_on"])
    def test_the_verb_runs_by_default(self, request, state, tmp_path, monkeypatch):
        request.getfixturevalue(state)
        monkeypatch.setattr(
            "cli_agent_orchestrator.agent_plugins.store.AGENT_PLUGINS_DIR", tmp_path / "p"
        )
        monkeypatch.setattr(
            "cli_agent_orchestrator.agent_plugins.store.AGENT_PLUGIN_DATA_DIR", tmp_path / "d"
        )

        result = CliRunner().invoke(cli, ["plugin", "list"])

        assert result.exit_code == 0
        assert "No agent plugins installed" in result.output

    @pytest.mark.parametrize("state", ["gate_off", "gate_on", "gate_default"])
    def test_help_lists_the_verb_in_every_state(self, request, state):
        """Graduation un-hides ``cao plugin``; the kill switch does not hide it again."""
        request.getfixturevalue(state)

        result = CliRunner().invoke(cli, ["--help"])

        assert result.exit_code == 0
        listed = [
            line.split()[0]
            for line in result.output.splitlines()
            if line.startswith("  ") and line.strip() and not line.strip().startswith("-")
        ]
        assert "plugin" in listed, listed
