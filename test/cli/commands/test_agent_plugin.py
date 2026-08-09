"""Tests for the ``cao plugin`` CLI group (W7).

_Requirements: 15.1, 15.2, 15.3, 16.1, 16.2, 16.3, 16.6, 22.1_

Every test drives the real Click group through ``CliRunner`` against an isolated
store, so the assertions are about what an operator actually sees.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from cli_agent_orchestrator.agent_plugins.store import InstalledPluginStore
from cli_agent_orchestrator.cli.commands.agent_plugin import (
    UNTRUSTED_CONTENT_WARNING,
    plugin,
)

SCHEMA_ID = "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json"


def _make_plugin(root: Path, name: str, skills=("alpha",)) -> Path:
    """Build a minimal valid plugin package."""
    root.mkdir(parents=True, exist_ok=True)
    (root / "plugin.json").write_text(
        json.dumps({"$schema": SCHEMA_ID, "name": name, "version": "1.0.0"}, indent=2),
        encoding="utf-8",
    )
    for skill in skills:
        folder = root / "skills" / skill
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "SKILL.md").write_text(
            f'---\nname: "{skill}"\ndescription: "A test skill."\n---\n\nBody\n',
            encoding="utf-8",
        )
    return root


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture(autouse=True)
def isolated_store(tmp_path: Path, monkeypatch) -> InstalledPluginStore:
    """Point the CLI's default store and projection target at ``tmp_path``.

    The CLI constructs ``InstalledPluginStore()`` with no arguments, so isolation
    has to come from the constants it defaults to. Without this a test would
    write into the developer's real plugin store.
    """
    plugins_dir = tmp_path / "agent-plugins"
    data_dir = tmp_path / "agent-plugin-data"
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir(parents=True, exist_ok=True)

    for target in (
        "cli_agent_orchestrator.agent_plugins.store.AGENT_PLUGINS_DIR",
        "cli_agent_orchestrator.constants.AGENT_PLUGINS_DIR",
    ):
        monkeypatch.setattr(target, plugins_dir, raising=False)
    for target in (
        "cli_agent_orchestrator.agent_plugins.store.AGENT_PLUGIN_DATA_DIR",
        "cli_agent_orchestrator.constants.AGENT_PLUGIN_DATA_DIR",
    ):
        monkeypatch.setattr(target, data_dir, raising=False)
    monkeypatch.setattr("cli_agent_orchestrator.agent_plugins.projection.SKILLS_DIR", skills_dir)
    monkeypatch.setattr("cli_agent_orchestrator.utils.skills.SKILLS_DIR", skills_dir)
    monkeypatch.setattr(
        "cli_agent_orchestrator.services.settings_service.get_extra_skill_dirs", lambda: []
    )
    # Never touch real provider artifacts from a unit test.
    monkeypatch.setattr(
        "cli_agent_orchestrator.utils.skill_injection.refresh_all_cao_managed_agents",
        lambda: [],
    )
    # No live sessions unless a test says otherwise.
    monkeypatch.setattr("cli_agent_orchestrator.services.session_service.list_sessions", lambda: [])

    return InstalledPluginStore(plugins_dir=plugins_dir, data_dir=data_dir)


class TestCommandShapeParityWithSkills:
    """_Requirements: 16.1 — add, list, remove, validate all present._"""

    def test_group_exposes_the_four_capabilities(self) -> None:
        assert set(plugin.commands) == {"add", "list", "remove", "validate"}

    def test_group_is_hidden_pending_m1(self) -> None:
        """_Requirements: 16.5 — must not ship to end users until M1 lands._"""
        assert plugin.hidden is True

    def test_add_accepts_the_documented_options(self) -> None:
        options = {
            opt for param in plugin.commands["add"].params for opt in getattr(param, "opts", [])
        }

        assert {"--ref", "--subdir", "--force", "--dry-run"} <= options

    def test_remove_accepts_purge_data_and_yes(self) -> None:
        options = {
            opt for param in plugin.commands["remove"].params for opt in getattr(param, "opts", [])
        }

        assert {"--purge-data", "--yes"} <= options

    @pytest.mark.parametrize("command", ["list", "validate"])
    def test_json_option_exists_where_required(self, command: str) -> None:
        """_Requirements: 16.2_"""
        options = {
            opt for param in plugin.commands[command].params for opt in getattr(param, "opts", [])
        }

        assert "--json" in options

    def test_help_renders_for_every_subcommand(self, runner: CliRunner) -> None:
        for name in plugin.commands:
            result = runner.invoke(plugin, [name, "--help"])
            assert result.exit_code == 0, f"{name} --help failed: {result.output}"


class TestUntrustedContentWarning:
    """_Requirements: 22.1 — stated at or before the point of install._"""

    def test_add_warns_before_installing(self, runner: CliRunner, tmp_path: Path) -> None:
        source = _make_plugin(tmp_path / "src", "example")

        result = runner.invoke(plugin, ["add", str(source)])

        assert result.exit_code == 0, result.output
        assert "untrusted code and content" in result.output

    def test_warning_says_there_is_no_signing_or_provenance_check(self) -> None:
        """CAO implements no trust model; the wording must not imply one."""
        assert "no signing" in UNTRUSTED_CONTENT_WARNING
        assert "does not verify" in UNTRUSTED_CONTENT_WARNING

    def test_warning_appears_even_for_a_dry_run(self, runner: CliRunner, tmp_path: Path) -> None:
        source = _make_plugin(tmp_path / "src", "example")

        result = runner.invoke(plugin, ["add", str(source), "--dry-run"])

        assert "untrusted" in result.output


class TestAdd:
    def test_installs_a_valid_plugin(self, runner: CliRunner, tmp_path: Path) -> None:
        source = _make_plugin(tmp_path / "src", "example", skills=("alpha", "beta"))

        result = runner.invoke(plugin, ["add", str(source)])

        assert result.exit_code == 0, result.output
        assert "installed successfully" in result.output
        assert "alpha" in result.output and "beta" in result.output

    def test_reports_an_invalid_plugin_and_installs_nothing(
        self, runner: CliRunner, tmp_path: Path, isolated_store: InstalledPluginStore
    ) -> None:
        source = tmp_path / "bad"
        source.mkdir()
        (source / "plugin.json").write_text("{ broken", encoding="utf-8")

        result = runner.invoke(plugin, ["add", str(source)])

        assert result.exit_code != 0
        assert "not loadable" in result.output
        assert "manifest.invalid_json" in result.output
        assert isolated_store.list_installed() == []

    def test_unreachable_source_is_a_click_exception(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        result = runner.invoke(plugin, ["add", str(tmp_path / "absent")])

        assert result.exit_code != 0
        assert "does not exist" in result.output

    def test_dry_run_installs_nothing(
        self, runner: CliRunner, tmp_path: Path, isolated_store: InstalledPluginStore
    ) -> None:
        source = _make_plugin(tmp_path / "src", "example")

        result = runner.invoke(plugin, ["add", str(source), "--dry-run"])

        assert result.exit_code == 0, result.output
        assert "nothing installed" in result.output
        assert isolated_store.list_installed() == []

    def test_second_add_is_refused_without_force(self, runner: CliRunner, tmp_path: Path) -> None:
        source = _make_plugin(tmp_path / "src", "example")
        assert runner.invoke(plugin, ["add", str(source)]).exit_code == 0

        result = runner.invoke(plugin, ["add", str(source)])

        assert result.exit_code != 0
        assert "--force" in result.output

    def test_force_replaces_the_installed_plugin(self, runner: CliRunner, tmp_path: Path) -> None:
        first = _make_plugin(tmp_path / "v1", "example", skills=("alpha",))
        assert runner.invoke(plugin, ["add", str(first)]).exit_code == 0
        second = _make_plugin(tmp_path / "v2", "example", skills=("beta",))

        result = runner.invoke(plugin, ["add", str(second), "--force"])

        assert result.exit_code == 0, result.output
        assert "beta" in result.output

    def test_reports_a_skipped_skill(self, runner: CliRunner, tmp_path: Path) -> None:
        source = _make_plugin(tmp_path / "src", "example", skills=("alpha",))
        broken = source / "skills" / "mismatch"
        broken.mkdir(parents=True)
        (broken / "SKILL.md").write_text(
            '---\nname: "other"\ndescription: "d"\n---\n', encoding="utf-8"
        )

        result = runner.invoke(plugin, ["add", str(source)])

        assert result.exit_code == 0, result.output
        assert "skill.invalid" in result.output


class TestList:
    def test_empty_store_says_so(self, runner: CliRunner) -> None:
        result = runner.invoke(plugin, ["list"])

        assert result.exit_code == 0, result.output
        assert "No agent plugins installed" in result.output

    def test_human_output_is_two_column_like_cao_skills_list(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        """_Requirements: 16.3_"""
        runner.invoke(plugin, ["add", str(_make_plugin(tmp_path / "src", "example"))])

        result = runner.invoke(plugin, ["list"])

        assert result.exit_code == 0, result.output
        assert "Name" in result.output and "Version" in result.output
        assert "example" in result.output
        assert "alpha" in result.output

    def test_json_output_is_machine_readable(self, runner: CliRunner, tmp_path: Path) -> None:
        """_Requirements: 16.2_"""
        runner.invoke(
            plugin, ["add", str(_make_plugin(tmp_path / "src", "example", skills=("alpha",)))]
        )

        result = runner.invoke(plugin, ["list", "--json"])

        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        assert [entry["name"] for entry in payload["plugins"]] == ["example"]
        assert payload["plugins"][0]["projected_skill_names"] == ["alpha"]
        assert payload["plugins"][0]["version"] == "1.0.0"

    def test_json_output_is_valid_json_when_empty(self, runner: CliRunner) -> None:
        result = runner.invoke(plugin, ["list", "--json"])

        assert json.loads(result.output) == {"plugins": [], "swept": []}

    def test_list_sweeps_dangling_projections(
        self, runner: CliRunner, tmp_path: Path, isolated_store: InstalledPluginStore
    ) -> None:
        """Design: the sweep runs on rebuild AND on ``plugin list``."""
        import shutil

        runner.invoke(plugin, ["add", str(_make_plugin(tmp_path / "src", "example"))])
        skills_dir = tmp_path / "skills"
        assert (skills_dir / "alpha").is_symlink()
        # Break the projection out of band.
        shutil.rmtree(isolated_store.plugin_root("example"))

        result = runner.invoke(plugin, ["list"])

        assert result.exit_code == 0, result.output
        assert not (skills_dir / "alpha").exists()
        assert "Swept" in result.output


class TestValidate:
    def test_valid_plugin_exits_zero(self, runner: CliRunner, tmp_path: Path) -> None:
        source = _make_plugin(tmp_path / "src", "example")

        result = runner.invoke(plugin, ["validate", str(source)])

        assert result.exit_code == 0, result.output
        assert "Loadable: yes" in result.output
        assert "example" in result.output

    def test_invalid_plugin_exits_non_zero(self, runner: CliRunner, tmp_path: Path) -> None:
        """CI and scripts gate on this."""
        source = tmp_path / "bad"
        source.mkdir()
        (source / "plugin.json").write_text("nope", encoding="utf-8")

        result = runner.invoke(plugin, ["validate", str(source)])

        assert result.exit_code == 1
        assert "Loadable: no" in result.output

    def test_validate_installs_nothing(
        self, runner: CliRunner, tmp_path: Path, isolated_store: InstalledPluginStore
    ) -> None:
        source = _make_plugin(tmp_path / "src", "example")

        runner.invoke(plugin, ["validate", str(source)])

        assert isolated_store.list_installed() == []

    def test_json_report_is_machine_readable(self, runner: CliRunner, tmp_path: Path) -> None:
        """_Requirements: 16.2_"""
        source = _make_plugin(tmp_path / "src", "example", skills=("alpha", "beta"))

        result = runner.invoke(plugin, ["validate", str(source), "--json"])

        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        assert payload["loadable"] is True
        assert payload["name"] == "example"
        assert sorted(skill["name"] for skill in payload["skills"]) == ["alpha", "beta"]
        assert payload["mcp_present"] is False

    def test_json_report_for_an_invalid_plugin_still_parses(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        source = tmp_path / "bad"
        source.mkdir()
        (source / "plugin.json").write_text("{", encoding="utf-8")

        result = runner.invoke(plugin, ["validate", str(source), "--json"])

        assert result.exit_code == 1
        payload = json.loads(result.output)
        assert payload["loadable"] is False
        assert any(f["code"] == "manifest.invalid_json" for f in payload["findings"])

    def test_reports_mcp_as_unsupported(self, runner: CliRunner, tmp_path: Path) -> None:
        source = _make_plugin(tmp_path / "src", "example")
        (source / "mcp.json").write_text("{}", encoding="utf-8")

        result = runner.invoke(plugin, ["validate", str(source)])

        assert result.exit_code == 0, result.output
        assert "unsupported in this version" in result.output


class TestRemove:
    def test_removes_an_installed_plugin(
        self, runner: CliRunner, tmp_path: Path, isolated_store: InstalledPluginStore
    ) -> None:
        runner.invoke(plugin, ["add", str(_make_plugin(tmp_path / "src", "example"))])

        result = runner.invoke(plugin, ["remove", "example"])

        assert result.exit_code == 0, result.output
        assert "removed successfully" in result.output
        assert isolated_store.get("example") is None

    def test_withdraws_the_projected_skills(self, runner: CliRunner, tmp_path: Path) -> None:
        runner.invoke(
            plugin, ["add", str(_make_plugin(tmp_path / "src", "example", skills=("alpha",)))]
        )

        result = runner.invoke(plugin, ["remove", "example"])

        assert "alpha" in result.output
        assert not (tmp_path / "skills" / "alpha").exists()

    def test_removing_an_absent_plugin_is_an_error(self, runner: CliRunner) -> None:
        result = runner.invoke(plugin, ["remove", "nope"])

        assert result.exit_code != 0
        assert "not installed" in result.output

    def test_purge_data_requires_confirmation(
        self, runner: CliRunner, tmp_path: Path, isolated_store: InstalledPluginStore
    ) -> None:
        runner.invoke(plugin, ["add", str(_make_plugin(tmp_path / "src", "example"))])
        data = isolated_store.plugin_data_dir("example", create=True)
        (data / "state").write_text("precious", encoding="utf-8")

        result = runner.invoke(plugin, ["remove", "example", "--purge-data"], input="n\n")

        assert "Aborted" in result.output
        assert (data / "state").is_file()
        assert isolated_store.get("example") is not None

    def test_purge_data_deletes_when_confirmed(
        self, runner: CliRunner, tmp_path: Path, isolated_store: InstalledPluginStore
    ) -> None:
        runner.invoke(plugin, ["add", str(_make_plugin(tmp_path / "src", "example"))])
        data = isolated_store.plugin_data_dir("example", create=True)
        (data / "state").write_text("doomed", encoding="utf-8")

        result = runner.invoke(plugin, ["remove", "example", "--purge-data"], input="y\n")

        assert result.exit_code == 0, result.output
        assert not data.exists()

    def test_yes_bypasses_the_purge_confirmation(
        self, runner: CliRunner, tmp_path: Path, isolated_store: InstalledPluginStore
    ) -> None:
        runner.invoke(plugin, ["add", str(_make_plugin(tmp_path / "src", "example"))])
        data = isolated_store.plugin_data_dir("example", create=True)
        (data / "state").write_text("doomed", encoding="utf-8")

        result = runner.invoke(plugin, ["remove", "example", "--purge-data", "--yes"])

        assert result.exit_code == 0, result.output
        assert not data.exists()


class TestRemovalSafetyConfirmation:
    """_Requirements: 15.1, 15.2, 15.3, 16.6 — warn, confirm, never refuse._"""

    @pytest.fixture
    def live_session(self, monkeypatch):
        """One live terminal whose provider reaches the whole skill store."""
        monkeypatch.setattr(
            "cli_agent_orchestrator.services.session_service.list_sessions",
            lambda: [{"id": "cao-demo"}],
        )
        monkeypatch.setattr(
            "cli_agent_orchestrator.clients.database.list_all_terminals",
            lambda: [
                {
                    "id": "abcd1234",
                    "tmux_session": "cao-demo",
                    "provider": "kiro_cli",
                    "agent_profile": "dev",
                }
            ],
        )

    def test_affected_sessions_are_reported(
        self, runner: CliRunner, tmp_path: Path, live_session
    ) -> None:
        runner.invoke(plugin, ["add", str(_make_plugin(tmp_path / "src", "example"))])

        result = runner.invoke(plugin, ["remove", "example"], input="n\n")

        assert "affects 1 live terminal" in result.output
        assert "cao-demo" in result.output
        assert "abcd1234" in result.output
        assert "alpha" in result.output

    def test_declining_leaves_the_plugin_installed(
        self, runner: CliRunner, tmp_path: Path, live_session, isolated_store
    ) -> None:
        runner.invoke(plugin, ["add", str(_make_plugin(tmp_path / "src", "example"))])

        result = runner.invoke(plugin, ["remove", "example"], input="n\n")

        assert "Aborted" in result.output
        assert isolated_store.get("example") is not None
        assert (tmp_path / "skills" / "alpha").is_symlink()

    def test_confirming_proceeds(
        self, runner: CliRunner, tmp_path: Path, live_session, isolated_store
    ) -> None:
        """_Requirements: 15.3 — it warns; it does not refuse._"""
        runner.invoke(plugin, ["add", str(_make_plugin(tmp_path / "src", "example"))])

        result = runner.invoke(plugin, ["remove", "example"], input="y\n")

        assert result.exit_code == 0, result.output
        assert "removed successfully" in result.output
        assert isolated_store.get("example") is None

    def test_yes_bypasses_the_prompt_entirely(
        self, runner: CliRunner, tmp_path: Path, live_session, isolated_store
    ) -> None:
        """_Requirements: 15.2, 16.6 — for scripted use._"""
        runner.invoke(plugin, ["add", str(_make_plugin(tmp_path / "src", "example"))])

        result = runner.invoke(plugin, ["remove", "example", "--yes"])

        assert result.exit_code == 0, result.output
        assert "Remove anyway?" not in result.output
        assert isolated_store.get("example") is None

    def test_no_prompt_when_nothing_is_affected(self, runner: CliRunner, tmp_path: Path) -> None:
        runner.invoke(plugin, ["add", str(_make_plugin(tmp_path / "src", "example"))])

        result = runner.invoke(plugin, ["remove", "example"])

        assert result.exit_code == 0, result.output
        assert "Remove anyway?" not in result.output


class TestRegisteredInMainCli:
    """_Requirements: 16.1 — the group is reachable from the root command._"""

    def test_group_is_registered(self) -> None:
        from cli_agent_orchestrator.cli.main import cli

        assert "plugin" in cli.commands

    def test_registered_group_is_the_agent_plugin_group(self) -> None:
        from cli_agent_orchestrator.cli.main import cli

        assert cli.commands["plugin"] is plugin

    def test_it_does_not_shadow_the_event_plugin_surface(self) -> None:
        """D7: unrelated to ``cao.plugins`` entry points and PluginRegistry."""
        from cli_agent_orchestrator.plugins import PluginRegistry

        assert PluginRegistry is not None

    def test_hidden_group_is_absent_from_root_help(self, runner: CliRunner) -> None:
        """_Requirements: 16.5 — not offered to end users pending M1._"""
        from cli_agent_orchestrator.cli.main import cli

        result = runner.invoke(cli, ["--help"])

        assert result.exit_code == 0
        assert "plugin" not in result.output
