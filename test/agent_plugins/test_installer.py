"""Unit tests for the installer and removal safety (W5).

_Requirements: 9.1, 9.2, 9.3, 9.5, 10.1, 10.2, 10.3, 10.4, 15.1, 15.2, 15.3_
"""

from __future__ import annotations

from pathlib import Path

import pytest

from cli_agent_orchestrator.agent_plugins import installer
from cli_agent_orchestrator.agent_plugins.installer import (
    PluginInstallError,
    affected_sessions,
    removal_impact,
)
from cli_agent_orchestrator.agent_plugins.models import PluginSource, Severity
from cli_agent_orchestrator.agent_plugins.resolver import PluginResolutionError

from .conftest import ProjectionEnv, make_plugin, write_skill


class TestInstallHappyPath:
    def test_installs_and_reports_success(self, env: ProjectionEnv) -> None:
        outcome = env.install("example", skills=("alpha",))

        assert outcome.installed is True
        assert outcome.report.loadable is True
        assert outcome.record is not None
        assert outcome.record.name == "example"

    def test_records_the_version_and_schema(self, env: ProjectionEnv) -> None:
        outcome = env.install("example")

        assert outcome.record is not None
        assert outcome.record.version == "1.0.0"
        assert outcome.record.schema_id is not None

    def test_records_the_source(self, env: ProjectionEnv) -> None:
        outcome = env.install("example")

        assert outcome.record is not None
        assert outcome.record.source is not None
        assert outcome.record.source.kind == "path"

    def test_records_projected_skill_names(self, env: ProjectionEnv) -> None:
        outcome = env.install("example", skills=("alpha", "beta"))

        assert outcome.record is not None
        assert outcome.record.projected_skill_names == ("alpha", "beta")
        assert outcome.projected_skill_names == ("alpha", "beta")

    def test_projected_names_are_a_subset_of_skill_names(self, env: ProjectionEnv) -> None:
        write_skill(env.skills_dir / "alpha")  # pre-existing wins

        outcome = env.install("example", skills=("alpha", "beta"))

        assert outcome.record is not None
        assert set(outcome.record.projected_skill_names) < set(outcome.record.skill_names)
        assert outcome.record.projected_skill_names == ("beta",)

    def test_the_difference_is_explained_by_a_finding(self, env: ProjectionEnv) -> None:
        write_skill(env.skills_dir / "alpha")

        outcome = env.install("example", skills=("alpha", "beta"))

        assert any(f.code == "projection.preexisting_skill" for f in outcome.findings)

    def test_publishes_the_package_bytes(self, env: ProjectionEnv) -> None:
        env.install("example", skills=("alpha",))

        root = env.store.plugin_root("example")
        assert (root / "plugin.json").is_file()
        assert (root / "skills" / "alpha" / "SKILL.md").is_file()

    def test_no_staging_directories_are_left_behind(self, env: ProjectionEnv) -> None:
        env.install("example")

        leftovers = [
            entry.name
            for entry in env.store.plugins_dir.iterdir()
            if entry.name.startswith(".") and entry.name != ".state"
        ]
        assert leftovers == []

    def test_non_fatal_findings_are_carried_into_the_record(self, env: ProjectionEnv) -> None:
        from .conftest import make_manifest

        source = make_plugin(
            env.sources / "example",
            "example",
            manifest=make_manifest("example", surprise="v"),
        )

        outcome = env.install("example", source_dir=source)

        assert outcome.record is not None
        assert any(f.code == "manifest.unknown_field" for f in outcome.record.findings)


class TestInstallOrdering:
    """_Requirements: 9.1, 9.2 — validate the staged copy before publishing._"""

    def test_invalid_plugin_publishes_nothing(self, env: ProjectionEnv) -> None:
        source = make_plugin(env.sources / "bad", "bad", raw_manifest="{ broken")

        outcome = env.install("bad", source_dir=source)

        assert outcome.installed is False
        assert outcome.report.loadable is False
        assert env.store.list_installed() == []

    def test_invalid_plugin_leaves_the_projection_untouched(self, env: ProjectionEnv) -> None:
        env.install("good", skills=("alpha",))
        before = env.skill_names()

        source = make_plugin(env.sources / "bad", "bad", raw_manifest="nope")
        env.install("bad", source_dir=source)

        assert env.skill_names() == before

    def test_invalid_plugin_writes_no_record(self, env: ProjectionEnv) -> None:
        source = make_plugin(env.sources / "bad", "bad", raw_manifest="{")

        env.install("bad", source_dir=source)

        assert env.store.get("bad") is None

    def test_unreachable_source_raises_and_changes_nothing(self, env: ProjectionEnv) -> None:
        env.install("good", skills=("alpha",))
        before = env.skill_names()

        with pytest.raises(PluginResolutionError):
            installer.install(
                PluginSource(kind="path", location=str(env.sources / "absent")),
                store=env.store,
                skills_dir=env.skills_dir,
                refresh_agents=False,
            )

        assert env.skill_names() == before
        assert [r.name for r in env.store.list_installed()] == ["good"]

    def test_the_published_name_comes_from_the_manifest(self, env: ProjectionEnv) -> None:
        """Not from the source directory name, which is arbitrary."""
        source = make_plugin(env.sources / "some-folder", "declared-name")

        outcome = env.install("ignored", source_dir=source)

        assert outcome.record is not None
        assert outcome.record.name == "declared-name"
        assert env.store.get("declared-name") is not None


class TestNameCollision:
    """_Requirements: 9.5 — refuse unless force, and suggest force._"""

    def test_second_install_of_the_same_name_is_refused(self, env: ProjectionEnv) -> None:
        env.install("example")

        with pytest.raises(PluginInstallError, match="--force"):
            env.install("example")

    def test_refusal_leaves_the_original_installed(self, env: ProjectionEnv) -> None:
        env.install("example", skills=("alpha",))

        with pytest.raises(PluginInstallError):
            env.install("example", skills=("beta",))

        assert (env.store.plugin_root("example") / "skills" / "alpha").is_dir()

    def test_force_replaces_the_installed_plugin(self, env: ProjectionEnv) -> None:
        env.install("example", skills=("alpha",))
        replacement = make_plugin(env.sources / "v2", "example", skills=("beta",))

        outcome = env.install("example", source_dir=replacement, force=True)

        assert outcome.installed is True
        assert env.skill_names() == ["beta"]


class TestDryRun:
    """_Requirements: 9.1 — dry run resolves and validates only._"""

    def test_dry_run_does_not_install(self, env: ProjectionEnv) -> None:
        source = env.make_plugin("example")

        outcome = installer.install(
            PluginSource(kind="path", location=str(source)),
            dry_run=True,
            store=env.store,
            skills_dir=env.skills_dir,
            refresh_agents=False,
        )

        assert outcome.installed is False
        assert outcome.dry_run is True
        assert env.store.list_installed() == []
        assert env.skill_names() == []

    def test_dry_run_still_reports_the_full_validation(self, env: ProjectionEnv) -> None:
        source = env.make_plugin("example", skills=("alpha", "beta"))

        outcome = installer.install(
            PluginSource(kind="path", location=str(source)),
            dry_run=True,
            store=env.store,
            skills_dir=env.skills_dir,
            refresh_agents=False,
        )

        assert outcome.report.loadable is True
        assert sorted(outcome.report.skill_names) == ["alpha", "beta"]

    def test_dry_run_reports_an_invalid_plugin(self, env: ProjectionEnv) -> None:
        source = make_plugin(env.sources / "bad", "bad", raw_manifest="{")

        outcome = installer.install(
            PluginSource(kind="path", location=str(source)),
            dry_run=True,
            store=env.store,
            skills_dir=env.skills_dir,
            refresh_agents=False,
        )

        assert outcome.installed is False
        assert outcome.report.loadable is False

    def test_dry_run_leaves_no_staging_behind(self, env: ProjectionEnv) -> None:
        source = env.make_plugin("example")

        installer.install(
            PluginSource(kind="path", location=str(source)),
            dry_run=True,
            store=env.store,
            skills_dir=env.skills_dir,
            refresh_agents=False,
        )

        remaining = (
            [entry.name for entry in env.store.plugins_dir.iterdir()]
            if env.store.plugins_dir.is_dir()
            else []
        )
        assert [name for name in remaining if name.startswith(".staging.")] == []


class TestUninstall:
    """_Requirements: 10.2, 10.3, 10.4_"""

    def test_removes_the_plugin_and_its_projection(self, env: ProjectionEnv) -> None:
        env.install("example", skills=("alpha",))

        outcome = env.uninstall("example")

        assert outcome.removed is True
        assert env.store.get("example") is None
        assert env.skill_names() == []

    def test_removing_an_absent_plugin_is_not_an_error(self, env: ProjectionEnv) -> None:
        outcome = env.uninstall("never-installed")

        assert outcome.removed is False

    def test_retains_plugin_data_by_default(self, env: ProjectionEnv) -> None:
        env.install("example")
        data = env.store.plugin_data_dir("example", create=True)
        (data / "state.db").write_text("precious", encoding="utf-8")

        outcome = env.uninstall("example")

        assert outcome.purged_data is False
        assert (data / "state.db").is_file()

    def test_purge_data_removes_plugin_data(self, env: ProjectionEnv) -> None:
        env.install("example")
        data = env.store.plugin_data_dir("example", create=True)
        (data / "state.db").write_text("precious", encoding="utf-8")

        outcome = env.uninstall("example", purge_data=True)

        assert outcome.purged_data is True
        assert not data.exists()

    def test_other_plugins_are_unaffected(self, env: ProjectionEnv) -> None:
        env.install("keep", skills=("kept",))
        env.install("drop", skills=("dropped",))

        env.uninstall("drop")

        assert env.skill_names() == ["kept"]
        assert [r.name for r in env.store.list_installed()] == ["keep"]

    def test_preexisting_skills_survive_removal(self, env: ProjectionEnv) -> None:
        write_skill(env.skills_dir / "mine")
        env.install("example", skills=("alpha",))

        env.uninstall("example")

        assert env.skill_names() == ["mine"]


class TestAgentRefresh:
    """Step 6: baked provider artifacts are refreshed, best-effort."""

    def test_install_refreshes_baked_agents(self, env: ProjectionEnv, monkeypatch) -> None:
        calls = []
        monkeypatch.setattr(
            "cli_agent_orchestrator.utils.skill_injection.refresh_all_cao_managed_agents",
            lambda: calls.append("called") or [Path("a.agent.md")],
        )
        source = env.make_plugin("example")

        outcome = installer.install(
            PluginSource(kind="path", location=str(source)),
            store=env.store,
            skills_dir=env.skills_dir,
        )

        assert calls == ["called"]
        assert outcome.refreshed_agents == 1

    def test_uninstall_refreshes_baked_agents(self, env: ProjectionEnv, monkeypatch) -> None:
        env.install("example")
        calls = []
        monkeypatch.setattr(
            "cli_agent_orchestrator.utils.skill_injection.refresh_all_cao_managed_agents",
            lambda: calls.append("called") or [],
        )

        installer.uninstall("example", store=env.store, skills_dir=env.skills_dir)

        assert calls == ["called"]

    def test_a_refresh_failure_does_not_fail_the_install(
        self, env: ProjectionEnv, monkeypatch
    ) -> None:
        """The install already succeeded; a stale catalog is not a rollback."""

        def _boom():
            raise RuntimeError("copilot dir unreadable")

        monkeypatch.setattr(
            "cli_agent_orchestrator.utils.skill_injection.refresh_all_cao_managed_agents",
            _boom,
        )
        source = env.make_plugin("example", skills=("alpha",))

        outcome = installer.install(
            PluginSource(kind="path", location=str(source)),
            store=env.store,
            skills_dir=env.skills_dir,
        )

        assert outcome.installed is True
        assert outcome.refreshed_agents == 0
        assert (env.skills_dir / "alpha").is_symlink()


class TestRemovalSafety:
    """_Requirements: 15.1, 15.2, 15.3 — warn, never refuse._"""

    def test_no_live_sessions_means_nothing_affected(self, env: ProjectionEnv, monkeypatch) -> None:
        monkeypatch.setattr(
            "cli_agent_orchestrator.services.session_service.list_sessions", lambda: []
        )

        assert affected_sessions(["alpha"]) == []

    def test_empty_skill_list_is_short_circuited(self, env: ProjectionEnv) -> None:
        assert affected_sessions([]) == []

    def test_a_live_terminal_referencing_a_skill_is_reported(
        self, env: ProjectionEnv, monkeypatch
    ) -> None:
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

        affected = affected_sessions(["alpha"])

        assert len(affected) == 1
        assert affected[0].terminal_id == "abcd1234"
        assert affected[0].session_name == "cao-demo"
        assert affected[0].skill_names == ("alpha",)

    def test_stale_database_rows_for_dead_sessions_are_ignored(
        self, env: ProjectionEnv, monkeypatch
    ) -> None:
        monkeypatch.setattr(
            "cli_agent_orchestrator.services.session_service.list_sessions",
            lambda: [{"id": "cao-live"}],
        )
        monkeypatch.setattr(
            "cli_agent_orchestrator.clients.database.list_all_terminals",
            lambda: [
                {
                    "id": "dead0001",
                    "tmux_session": "cao-gone",
                    "provider": "kiro_cli",
                    "agent_profile": "dev",
                }
            ],
        )

        assert affected_sessions(["alpha"]) == []

    def test_native_providers_see_the_whole_skill_store(
        self, env: ProjectionEnv, monkeypatch
    ) -> None:
        """Kiro/OpenCode/Copilot ignore a profile's ``skills`` allowlist.

        Kiro reads a ``skill://SKILLS_DIR/**`` glob and OpenCode a symlink to the
        whole directory, so per-profile scoping cannot narrow what they reach and
        every projected skill must count as referenced.
        """
        monkeypatch.setattr(
            "cli_agent_orchestrator.services.session_service.list_sessions",
            lambda: [{"id": "cao-demo"}],
        )
        monkeypatch.setattr(
            "cli_agent_orchestrator.clients.database.list_all_terminals",
            lambda: [
                {
                    "id": "t1",
                    "tmux_session": "cao-demo",
                    "provider": "opencode_cli",
                    "agent_profile": "narrow",
                }
            ],
        )

        class _Profile:
            skills = ["something-else"]  # would exclude alpha for a filtered provider

        monkeypatch.setattr(
            "cli_agent_orchestrator.utils.agent_profiles.load_agent_profile",
            lambda name: _Profile(),
        )

        affected = affected_sessions(["alpha"])

        assert len(affected) == 1

    def test_filtered_provider_respects_the_profile_allowlist(
        self, env: ProjectionEnv, monkeypatch
    ) -> None:
        monkeypatch.setattr(
            "cli_agent_orchestrator.services.session_service.list_sessions",
            lambda: [{"id": "cao-demo"}],
        )
        monkeypatch.setattr(
            "cli_agent_orchestrator.clients.database.list_all_terminals",
            lambda: [
                {
                    "id": "t1",
                    "tmux_session": "cao-demo",
                    "provider": "claude_code",
                    "agent_profile": "narrow",
                }
            ],
        )

        class _Profile:
            skills = ["something-else"]

        monkeypatch.setattr(
            "cli_agent_orchestrator.utils.agent_profiles.load_agent_profile",
            lambda name: _Profile(),
        )

        assert affected_sessions(["alpha"]) == []

    def test_filtered_provider_matches_glob_patterns(self, env: ProjectionEnv, monkeypatch) -> None:
        monkeypatch.setattr(
            "cli_agent_orchestrator.services.session_service.list_sessions",
            lambda: [{"id": "cao-demo"}],
        )
        monkeypatch.setattr(
            "cli_agent_orchestrator.clients.database.list_all_terminals",
            lambda: [
                {
                    "id": "t1",
                    "tmux_session": "cao-demo",
                    "provider": "codex",
                    "agent_profile": "globby",
                }
            ],
        )

        class _Profile:
            skills = ["ads-*"]

        monkeypatch.setattr(
            "cli_agent_orchestrator.utils.agent_profiles.load_agent_profile",
            lambda name: _Profile(),
        )

        assert affected_sessions(["ads-report"])
        assert affected_sessions(["other"]) == []

    def test_profile_with_none_skills_sees_everything(
        self, env: ProjectionEnv, monkeypatch
    ) -> None:
        monkeypatch.setattr(
            "cli_agent_orchestrator.services.session_service.list_sessions",
            lambda: [{"id": "cao-demo"}],
        )
        monkeypatch.setattr(
            "cli_agent_orchestrator.clients.database.list_all_terminals",
            lambda: [
                {
                    "id": "t1",
                    "tmux_session": "cao-demo",
                    "provider": "claude_code",
                    "agent_profile": "wide",
                }
            ],
        )

        class _Profile:
            skills = None

        monkeypatch.setattr(
            "cli_agent_orchestrator.utils.agent_profiles.load_agent_profile",
            lambda name: _Profile(),
        )

        assert len(affected_sessions(["alpha"])) == 1

    def test_profile_with_empty_skills_sees_nothing(self, env: ProjectionEnv, monkeypatch) -> None:
        monkeypatch.setattr(
            "cli_agent_orchestrator.services.session_service.list_sessions",
            lambda: [{"id": "cao-demo"}],
        )
        monkeypatch.setattr(
            "cli_agent_orchestrator.clients.database.list_all_terminals",
            lambda: [
                {
                    "id": "t1",
                    "tmux_session": "cao-demo",
                    "provider": "claude_code",
                    "agent_profile": "none",
                }
            ],
        )

        class _Profile:
            skills = []

        monkeypatch.setattr(
            "cli_agent_orchestrator.utils.agent_profiles.load_agent_profile",
            lambda name: _Profile(),
        )

        assert affected_sessions(["alpha"]) == []

    def test_unreadable_profile_warns_rather_than_under_reporting(
        self, env: ProjectionEnv, monkeypatch
    ) -> None:
        """Under-warning is the worse failure, so assume reachable."""
        monkeypatch.setattr(
            "cli_agent_orchestrator.services.session_service.list_sessions",
            lambda: [{"id": "cao-demo"}],
        )
        monkeypatch.setattr(
            "cli_agent_orchestrator.clients.database.list_all_terminals",
            lambda: [
                {
                    "id": "t1",
                    "tmux_session": "cao-demo",
                    "provider": "claude_code",
                    "agent_profile": "missing",
                }
            ],
        )

        def _boom(name):
            raise FileNotFoundError(name)

        monkeypatch.setattr("cli_agent_orchestrator.utils.agent_profiles.load_agent_profile", _boom)

        assert len(affected_sessions(["alpha"])) == 1

    def test_never_raises_when_no_server_or_database_is_available(
        self, env: ProjectionEnv, monkeypatch
    ) -> None:
        def _boom():
            raise RuntimeError("no tmux server")

        monkeypatch.setattr("cli_agent_orchestrator.services.session_service.list_sessions", _boom)

        assert affected_sessions(["alpha"]) == []

    def test_never_raises_when_the_terminal_query_fails(
        self, env: ProjectionEnv, monkeypatch
    ) -> None:
        monkeypatch.setattr(
            "cli_agent_orchestrator.services.session_service.list_sessions",
            lambda: [{"id": "cao-demo"}],
        )

        def _boom():
            raise RuntimeError("database locked")

        monkeypatch.setattr("cli_agent_orchestrator.clients.database.list_all_terminals", _boom)

        assert affected_sessions(["alpha"]) == []


class TestRemovalImpact:
    def test_reports_the_skills_a_plugin_projects(self, env: ProjectionEnv) -> None:
        env.install("example", skills=("alpha", "beta"))

        owned, _affected = removal_impact("example", env.store)

        assert owned == ("alpha", "beta")

    def test_excludes_skills_the_plugin_lost_to_a_collision(self, env: ProjectionEnv) -> None:
        env.install("aaa", skills=("shared",))
        env.install("zzz", skills=("shared", "own"))

        owned, _affected = removal_impact("zzz", env.store)

        assert owned == ("own",)

    def test_reports_nothing_for_an_absent_plugin(self, env: ProjectionEnv) -> None:
        owned, affected = removal_impact("nope", env.store)

        assert owned == ()
        assert affected == []

    def test_removal_is_never_blocked_by_a_live_session(
        self, env: ProjectionEnv, monkeypatch
    ) -> None:
        """_Requirements: 15.3 — the check warns; it does not refuse._"""
        env.install("example", skills=("alpha",))
        monkeypatch.setattr(
            "cli_agent_orchestrator.services.session_service.list_sessions",
            lambda: [{"id": "cao-demo"}],
        )
        monkeypatch.setattr(
            "cli_agent_orchestrator.clients.database.list_all_terminals",
            lambda: [
                {
                    "id": "t1",
                    "tmux_session": "cao-demo",
                    "provider": "kiro_cli",
                    "agent_profile": "dev",
                }
            ],
        )
        owned, affected = removal_impact("example", env.store)
        assert owned == ("alpha",) and len(affected) == 1

        outcome = env.uninstall("example")

        assert outcome.removed is True
        assert env.skill_names() == []
