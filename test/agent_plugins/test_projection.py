"""Unit tests for the projection engine and provenance (W5).

_Requirements: 13.1, 13.3, 13.4, 14.1, 14.2, 14.3, 14.4, 14.5, 15.4, 15.5_
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from cli_agent_orchestrator.agent_plugins import provenance
from cli_agent_orchestrator.agent_plugins.models import Severity
from cli_agent_orchestrator.agent_plugins.projection import (
    PROJECTION_MODE_COPY,
    PROJECTION_MODE_SYMLINK,
    rebuild_projection,
    sweep_dangling,
)

from .conftest import ProjectionEnv, write_skill


def find(outcome, code: str):
    return next((f for f in outcome.findings if f.code == code), None)


class TestBasicProjection:
    """_Requirements: 13.1 — plugin skills reach the existing skill store._"""

    def test_projects_a_skill_as_a_symlink(self, env: ProjectionEnv) -> None:
        env.install("example", skills=("alpha",))

        link = env.skills_dir / "alpha"
        assert link.is_symlink()
        assert (link / "SKILL.md").is_file()

    def test_link_points_into_the_plugin_root(self, env: ProjectionEnv) -> None:
        env.install("example", skills=("alpha",))

        expected = env.store.plugin_root("example") / "skills" / "alpha"
        assert (env.skills_dir / "alpha").resolve() == expected.resolve()

    def test_projects_every_valid_skill(self, env: ProjectionEnv) -> None:
        env.install("example", skills=("alpha", "beta", "gamma"))

        assert env.skill_names() == ["alpha", "beta", "gamma"]

    def test_link_uses_the_unprefixed_skill_name(self, env: ProjectionEnv) -> None:
        """Name equality is required by ``_load_skill_folder`` and Agent Skills."""
        env.install("my-plugin", skills=("alpha",))

        assert env.skill_names() == ["alpha"]

    def test_invalid_skill_is_not_projected(self, env: ProjectionEnv) -> None:
        source = env.make_plugin("example", skills=("alpha",))
        write_skill(source / "skills" / "broken", name="mismatch")

        env.install("example", source_dir=source)

        assert env.skill_names() == ["alpha"]

    def test_projection_ledger_is_written(self, env: ProjectionEnv) -> None:
        env.install("example", skills=("alpha",))

        assert env.store.read_projection() == {"alpha": "example"}

    def test_ledger_lives_outside_any_plugin_root(self, env: ProjectionEnv) -> None:
        env.install("example", skills=("alpha",))

        ledger = env.store.projection_state_path()
        assert ledger.is_file()
        assert env.store.plugin_root("example") not in ledger.parents


class TestPurityAndIdempotence:
    """_Requirements: 13.3 — a pure function of the installed set._"""

    def test_repeated_rebuild_is_stable(self, env: ProjectionEnv) -> None:
        env.install("example", skills=("alpha", "beta"))

        first = env.rebuild()
        second = env.rebuild()

        assert first.projected == second.projected
        assert env.skill_names() == ["alpha", "beta"]

    def test_rebuild_recreates_a_deleted_projection(self, env: ProjectionEnv) -> None:
        """Derived state: a rebuild restores what the installed set implies."""
        env.install("example", skills=("alpha",))
        (env.skills_dir / "alpha").unlink()

        env.rebuild()

        assert (env.skills_dir / "alpha").is_symlink()

    def test_rebuild_removes_a_projection_whose_plugin_is_gone(self, env: ProjectionEnv) -> None:
        env.install("example", skills=("alpha",))
        env.store.unpublish("example")

        outcome = env.rebuild()

        assert outcome.projected == {}
        assert env.skill_names() == []

    def test_rebuild_drops_skills_removed_from_an_updated_plugin(self, env: ProjectionEnv) -> None:
        env.install("example", skills=("alpha", "beta"))
        replacement = env.make_plugin("example-v2", skills=("alpha",))
        # Reuse the same plugin name with different content.
        (replacement / "plugin.json").write_text(
            (env.sources / "example" / "plugin.json").read_text(encoding="utf-8"),
            encoding="utf-8",
        )

        env.install("example", source_dir=replacement, force=True)

        assert env.skill_names() == ["alpha"]

    def test_unloadable_installed_plugin_projects_nothing(self, env: ProjectionEnv) -> None:
        """A plugin corrupted after install must not keep projecting."""
        env.install("example", skills=("alpha",))
        (env.store.plugin_root("example") / "plugin.json").write_text("{", encoding="utf-8")

        outcome = env.rebuild()

        assert outcome.projected == {}
        assert env.skill_names() == []
        assert find(outcome, "projection.plugin_unloadable") is not None


class TestPreExistingSkillWins:
    """_Requirements: 14.1 — a built-in or user-added skill always wins._"""

    def test_pre_existing_skill_is_not_overwritten(self, env: ProjectionEnv) -> None:
        write_skill(env.skills_dir / "alpha", description="the original")

        env.install("example", skills=("alpha",))

        assert not (env.skills_dir / "alpha").is_symlink()
        assert "the original" in (env.skills_dir / "alpha" / "SKILL.md").read_text(encoding="utf-8")

    def test_collision_is_reported(self, env: ProjectionEnv) -> None:
        write_skill(env.skills_dir / "alpha")

        outcome = env.install("example", skills=("alpha",)).projection

        finding = find(outcome, "projection.preexisting_skill")
        assert finding is not None
        assert finding.severity is Severity.SKIPPED
        assert "alpha" in finding.message

    def test_other_skills_still_project(self, env: ProjectionEnv) -> None:
        write_skill(env.skills_dir / "alpha")

        env.install("example", skills=("alpha", "beta"))

        assert (env.skills_dir / "beta").is_symlink()

    def test_pre_existing_skill_is_not_claimed_in_the_ledger(self, env: ProjectionEnv) -> None:
        write_skill(env.skills_dir / "alpha")

        env.install("example", skills=("alpha",))

        assert "alpha" not in env.store.read_projection()
        assert provenance.owning_plugin("alpha", env.store) is None


class TestPluginVersusPluginCollision:
    """_Requirements: 14.2, 14.5 — lexicographically smallest plugin wins._"""

    def test_smallest_plugin_name_wins(self, env: ProjectionEnv) -> None:
        env.install("zzz", skills=("shared",))
        env.install("aaa", skills=("shared",))

        assert provenance.owning_plugin("shared", env.store) == "aaa"

    def test_winner_is_independent_of_install_order(self, tmp_path: Path) -> None:
        """_Requirements: 14.4_"""
        from cli_agent_orchestrator.agent_plugins.store import InstalledPluginStore

        winners = set()
        for index, order in enumerate([("aaa", "mmm", "zzz"), ("zzz", "mmm", "aaa")]):
            base = tmp_path / f"run{index}"
            skills = base / "skills"
            skills.mkdir(parents=True)
            local = ProjectionEnv(
                store=InstalledPluginStore(
                    plugins_dir=base / "agent-plugins", data_dir=base / "data"
                ),
                skills_dir=skills,
                sources=base / "sources",
            )
            for name in order:
                local.install(name, skills=("shared",))
            winners.add(provenance.owning_plugin("shared", local.store))

        assert winners == {"aaa"}

    def test_loser_gets_a_skipped_finding_naming_the_winner(self, env: ProjectionEnv) -> None:
        env.install("aaa", skills=("shared",))
        outcome = env.install("zzz", skills=("shared",)).projection

        finding = find(outcome, "projection.plugin_collision")
        assert finding is not None
        assert finding.severity is Severity.SKIPPED
        assert "zzz" in finding.message and "aaa" in finding.message

    def test_exactly_k_minus_one_losers_are_reported(self, env: ProjectionEnv) -> None:
        for name in ("aaa", "bbb", "ccc"):
            env.install(name, skills=("shared",))

        outcome = env.rebuild()

        collisions = [f for f in outcome.findings if f.code == "projection.plugin_collision"]
        assert len(collisions) == 2  # k - 1 for k == 3

    def test_winner_changed_is_reported_on_reassignment(self, env: ProjectionEnv) -> None:
        """_Requirements: 14.x — a silently changed source needs a signal._"""
        env.install("mmm", skills=("shared",))
        assert provenance.owning_plugin("shared", env.store) == "mmm"

        outcome = env.install("aaa", skills=("shared",)).projection

        finding = find(outcome, "projection.winner_changed")
        assert finding is not None
        assert finding.severity is Severity.WARNING
        assert "mmm" in finding.message  # previous winner
        assert "aaa" in finding.message  # new winner

    def test_no_winner_changed_when_the_winner_is_unchanged(self, env: ProjectionEnv) -> None:
        env.install("aaa", skills=("shared",))
        outcome = env.install("zzz", skills=("shared",)).projection

        assert find(outcome, "projection.winner_changed") is None

    def test_link_actually_points_at_the_winner(self, env: ProjectionEnv) -> None:
        env.install("zzz", skills=("shared",))
        env.install("aaa", skills=("shared",))

        expected = env.store.plugin_root("aaa") / "skills" / "shared"
        assert (env.skills_dir / "shared").resolve() == expected.resolve()

    def test_removing_the_winner_promotes_the_next_claimant(self, env: ProjectionEnv) -> None:
        env.install("aaa", skills=("shared",))
        env.install("zzz", skills=("shared",))

        env.uninstall("aaa")

        assert provenance.owning_plugin("shared", env.store) == "zzz"
        expected = env.store.plugin_root("zzz") / "skills" / "shared"
        assert (env.skills_dir / "shared").resolve() == expected.resolve()


class TestCopyModeFallback:
    """_Requirements: 13.4 — fall back to copying and report it._"""

    def test_copy_mode_materializes_real_directories(self, env: ProjectionEnv) -> None:
        env.install("example", skills=("alpha",))

        env.rebuild(mode=PROJECTION_MODE_COPY)

        target = env.skills_dir / "alpha"
        assert target.is_dir()
        assert not target.is_symlink()
        assert (target / "SKILL.md").is_file()

    def test_copy_mode_is_idempotent(self, env: ProjectionEnv) -> None:
        env.install("example", skills=("alpha",))

        first = env.rebuild(mode=PROJECTION_MODE_COPY)
        second = env.rebuild(mode=PROJECTION_MODE_COPY)

        assert first.projected == second.projected
        assert (env.skills_dir / "alpha" / "SKILL.md").is_file()

    def test_copy_mode_projections_are_still_recognized_as_managed(
        self, env: ProjectionEnv
    ) -> None:
        """The ledger is what makes a copy distinguishable from a user skill."""
        env.install("example", skills=("alpha",))
        env.rebuild(mode=PROJECTION_MODE_COPY)
        assert env.store.read_projection() == {"alpha": "example"}

        env.store.unpublish("example")
        env.rebuild(mode=PROJECTION_MODE_COPY)

        # Removed because the ledger identified it as ours, not user-owned.
        assert env.skill_names() == []

    def test_symlink_failure_falls_back_to_copy_with_a_warning(
        self, env: ProjectionEnv, monkeypatch
    ) -> None:
        env.install("example", skills=("alpha",))
        (env.skills_dir / "alpha").unlink()

        original = Path.symlink_to

        def _refuse(self, *args, **kwargs):
            raise OSError("symlink creation unsupported")

        monkeypatch.setattr(Path, "symlink_to", _refuse)
        outcome = env.rebuild(mode=PROJECTION_MODE_SYMLINK)
        monkeypatch.setattr(Path, "symlink_to", original)

        finding = find(outcome, "projection.symlink_unsupported")
        assert finding is not None
        assert finding.severity is Severity.WARNING
        target = env.skills_dir / "alpha"
        assert target.is_dir() and not target.is_symlink()
        assert outcome.projected == {"alpha": "example"}

    def test_mode_comes_from_settings_by_default(self, env: ProjectionEnv, monkeypatch) -> None:
        monkeypatch.setattr(
            "cli_agent_orchestrator.services.settings_service.get_skill_projection_mode",
            lambda: PROJECTION_MODE_COPY,
        )
        env.install("example", skills=("alpha",))

        outcome = env.rebuild()

        assert outcome.mode == PROJECTION_MODE_COPY
        assert not (env.skills_dir / "alpha").is_symlink()

    def test_unreadable_settings_do_not_block_projection(
        self, env: ProjectionEnv, monkeypatch
    ) -> None:
        def _boom():
            raise RuntimeError("settings unavailable")

        monkeypatch.setattr(
            "cli_agent_orchestrator.services.settings_service.get_skill_projection_mode",
            _boom,
        )

        outcome = env.install("example", skills=("alpha",)).projection

        assert outcome.mode == PROJECTION_MODE_SYMLINK
        assert outcome.projected == {"alpha": "example"}


class TestDanglingSweep:
    """_Requirements: 15.4, 15.5 — the sweep never raises, never halts._"""

    def test_sweep_removes_a_dangling_projection(self, env: ProjectionEnv) -> None:
        env.install("example", skills=("alpha",))
        # Break the link by removing its target out of band.
        import shutil

        shutil.rmtree(env.store.plugin_root("example"))

        swept = sweep_dangling(env.store, skills_dir=env.skills_dir)

        assert "alpha" in swept
        assert not (env.skills_dir / "alpha").exists()

    def test_sweep_leaves_healthy_projections_alone(self, env: ProjectionEnv) -> None:
        env.install("example", skills=("alpha",))

        swept = sweep_dangling(env.store, skills_dir=env.skills_dir)

        assert swept == ()
        assert (env.skills_dir / "alpha").is_symlink()

    def test_sweep_leaves_user_skills_alone(self, env: ProjectionEnv) -> None:
        write_skill(env.skills_dir / "mine")

        sweep_dangling(env.store, skills_dir=env.skills_dir)

        assert (env.skills_dir / "mine" / "SKILL.md").is_file()

    def test_sweep_never_raises_on_a_missing_skills_dir(self, env: ProjectionEnv) -> None:
        import shutil

        shutil.rmtree(env.skills_dir)

        assert sweep_dangling(env.store, skills_dir=env.skills_dir) == ()

    def test_sweep_continues_past_a_link_it_cannot_remove(
        self, env: ProjectionEnv, monkeypatch
    ) -> None:
        """_Requirements: 15.5 — log and continue, do not halt._"""
        import shutil

        env.install("example", skills=("alpha", "beta", "gamma"))
        shutil.rmtree(env.store.plugin_root("example"))

        original_unlink = Path.unlink
        blocked = env.skills_dir / "beta"

        def _selective_unlink(self, *args, **kwargs):
            if self == blocked:
                raise PermissionError("cannot unlink")
            return original_unlink(self, *args, **kwargs)

        monkeypatch.setattr(Path, "unlink", _selective_unlink)
        swept = sweep_dangling(env.store, skills_dir=env.skills_dir)
        monkeypatch.setattr(Path, "unlink", original_unlink)

        # The other two were still swept despite beta failing.
        assert set(swept) == {"alpha", "gamma"}

    def test_dangling_link_is_swept_before_collision_election(self, env: ProjectionEnv) -> None:
        """A broken projection must not masquerade as a pre-existing skill.

        If the sweep ran after the election, a dangling link would look like an
        existing entry and beat every plugin claiming that name, leaving the
        skill permanently unavailable.
        """
        env.install("example", skills=("alpha",))
        # Point the projection at a target that no longer exists.
        link = env.skills_dir / "alpha"
        link.unlink()
        link.symlink_to(env.skills_dir / "gone-away", target_is_directory=True)

        outcome = env.rebuild()

        assert outcome.projected == {"alpha": "example"}
        assert (env.skills_dir / "alpha" / "SKILL.md").is_file()

    def test_rebuild_reports_what_it_swept(self, env: ProjectionEnv) -> None:
        import shutil

        env.install("example", skills=("alpha",))
        shutil.rmtree(env.store.plugin_root("example"))

        outcome = env.rebuild()

        assert "alpha" in outcome.swept


class TestLaunchSafety:
    """A broken projection must never raise into terminal creation.

    _Requirements: 15.4_
    """

    def test_list_skills_tolerates_a_dangling_projection(
        self, env: ProjectionEnv, monkeypatch
    ) -> None:
        import shutil

        from cli_agent_orchestrator.utils import skills as skills_module

        env.install("example", skills=("alpha",))
        write_skill(env.skills_dir / "healthy")
        shutil.rmtree(env.store.plugin_root("example"))

        monkeypatch.setattr(skills_module, "SKILLS_DIR", env.skills_dir)
        monkeypatch.setattr(
            "cli_agent_orchestrator.services.settings_service.get_extra_skill_dirs",
            lambda: [],
        )

        listed = skills_module.list_skills()

        # The dangling projection is simply not enumerated; no exception.
        assert [skill.name for skill in listed] == ["healthy"]

    def test_build_skill_catalog_tolerates_a_dangling_projection(
        self, env: ProjectionEnv, monkeypatch
    ) -> None:
        import shutil

        from cli_agent_orchestrator.utils import skills as skills_module

        env.install("example", skills=("alpha",))
        write_skill(env.skills_dir / "healthy")
        shutil.rmtree(env.store.plugin_root("example"))

        monkeypatch.setattr(skills_module, "SKILLS_DIR", env.skills_dir)
        monkeypatch.setattr(
            "cli_agent_orchestrator.services.settings_service.get_extra_skill_dirs",
            lambda: [],
        )

        catalog = skills_module.build_skill_catalog()

        assert "healthy" in catalog
        assert "alpha" not in catalog

    def test_sweep_concurrent_with_a_launch_read_does_not_raise(
        self, env: ProjectionEnv, monkeypatch
    ) -> None:
        """Break a projection *while* the launch path is enumerating skills."""
        import shutil

        from cli_agent_orchestrator.utils import skills as skills_module

        env.install("example", skills=("alpha",))
        write_skill(env.skills_dir / "healthy")
        monkeypatch.setattr(skills_module, "SKILLS_DIR", env.skills_dir)
        monkeypatch.setattr(
            "cli_agent_orchestrator.services.settings_service.get_extra_skill_dirs",
            lambda: [],
        )

        original_is_dir = Path.is_dir
        fired = {"done": False}

        def _break_midway(self, *args, **kwargs):
            # The first time the enumeration inspects our projection, delete the
            # plugin root underneath it and sweep, then answer honestly.
            if not fired["done"] and self.name == "alpha":
                fired["done"] = True
                shutil.rmtree(env.store.plugin_root("example"))
                sweep_dangling(env.store, skills_dir=env.skills_dir)
            return original_is_dir(self, *args, **kwargs)

        monkeypatch.setattr(Path, "is_dir", _break_midway)
        try:
            listed = skills_module.list_skills()  # must not raise
        finally:
            monkeypatch.setattr(Path, "is_dir", original_is_dir)

        assert fired["done"] is True
        assert "healthy" in [skill.name for skill in listed]


class TestProvenance:
    """_Requirements: 13.1 — recover which plugin provides a skill._"""

    def test_reports_the_owning_plugin(self, env: ProjectionEnv) -> None:
        env.install("example", skills=("alpha",))

        assert provenance.owning_plugin("alpha", env.store) == "example"

    def test_returns_none_for_a_builtin_skill(self, env: ProjectionEnv) -> None:
        write_skill(env.skills_dir / "mine")

        assert provenance.owning_plugin("mine", env.store) is None

    def test_returns_none_for_an_unknown_skill(self, env: ProjectionEnv) -> None:
        assert provenance.owning_plugin("nope", env.store) is None

    def test_maps_every_projected_skill(self, env: ProjectionEnv) -> None:
        env.install("aaa", skills=("one", "two"))
        env.install("bbb", skills=("three",))

        assert provenance.projected_skills(env.store) == {
            "one": "aaa",
            "two": "aaa",
            "three": "bbb",
        }

    def test_falls_back_to_install_records_without_a_ledger(self, env: ProjectionEnv) -> None:
        env.install("example", skills=("alpha",))
        env.store.projection_state_path().unlink()

        assert provenance.owning_plugin("alpha", env.store) == "example"

    def test_is_read_only(self, env: ProjectionEnv) -> None:
        env.install("example", skills=("alpha",))
        before = env.skill_names()

        provenance.projected_skills(env.store)
        provenance.owning_plugin("alpha", env.store)

        assert env.skill_names() == before

    def test_survives_a_corrupt_ledger(self, env: ProjectionEnv) -> None:
        env.install("example", skills=("alpha",))
        env.store.projection_state_path().write_text("{ broken", encoding="utf-8")

        # Degrades to the install-record fallback rather than raising.
        assert provenance.owning_plugin("alpha", env.store) == "example"
