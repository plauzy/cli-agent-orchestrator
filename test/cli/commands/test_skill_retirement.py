"""Tests for the M4 skill-rename retirement mechanism (W10, task 11.5).

_Requirements: 21.5_

The mechanism exists because seeding only ever *adds* directories: renaming a
shipped skill would otherwise leave an upgraded installation with both the old
and the new directory, and the stale copy would keep appearing in every agent's
skill catalog.

It is **inactive** while M4 is unresolved, so the tests do two things: prove it
is inert as shipped, and prove it behaves correctly when activated (by
monkeypatching the mapping, which is exactly the one-line edit M4 would make).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from cli_agent_orchestrator.cli.commands import init as init_module


def _write_skill(folder: Path, name: str) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "SKILL.md").write_text(
        f'---\nname: "{name}"\ndescription: "A skill."\n---\n\nBody\n', encoding="utf-8"
    )


@pytest.fixture
def skills_dir(tmp_path: Path, monkeypatch) -> Path:
    store = tmp_path / "skills"
    store.mkdir()
    monkeypatch.setattr(init_module, "SKILLS_DIR", store)
    return store


class TestInactiveAsShipped:
    """_Requirements: 21.5 — M4 is unresolved, so this must not act yet._"""

    def test_the_rename_mapping_is_empty(self) -> None:
        assert init_module.RETIRED_SKILL_RENAMES == {}

    def test_retirement_is_a_no_op(self, skills_dir: Path) -> None:
        _write_skill(skills_dir / "cao-plugin", "cao-plugin")
        _write_skill(skills_dir / "cao-event-plugin", "cao-event-plugin")

        removed = init_module.retire_renamed_skills()

        assert removed == []
        # Both survive: nothing has been decided, so nothing is retired.
        assert (skills_dir / "cao-plugin" / "SKILL.md").is_file()
        assert (skills_dir / "cao-event-plugin" / "SKILL.md").is_file()

    def test_the_shipped_allowlist_still_names_the_old_skill(self) -> None:
        """The rename has not happened, so the packaged skill is still cao-plugin."""
        import importlib.util
        import sys

        repo_root = Path(__file__).resolve().parents[3]
        spec = importlib.util.spec_from_file_location(
            "_sync_skills_retire", repo_root / "scripts" / "sync_skills.py"
        )
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)

        assert "cao-plugin" in module.SHIPPED_SKILLS
        assert "cao-event-plugin" not in module.SHIPPED_SKILLS


class TestBehaviourWhenActivated:
    """What M4 would switch on. Exercised now so it is not first run in anger."""

    @pytest.fixture(autouse=True)
    def activated(self, monkeypatch):
        monkeypatch.setattr(
            init_module, "RETIRED_SKILL_RENAMES", {"cao-plugin": "cao-event-plugin"}
        )

    def test_removes_the_old_directory_once_the_new_one_exists(self, skills_dir: Path) -> None:
        _write_skill(skills_dir / "cao-plugin", "cao-plugin")
        _write_skill(skills_dir / "cao-event-plugin", "cao-event-plugin")

        removed = init_module.retire_renamed_skills()

        assert removed == ["cao-plugin"]
        assert not (skills_dir / "cao-plugin").exists()
        assert (skills_dir / "cao-event-plugin" / "SKILL.md").is_file()

    def test_keeps_the_old_directory_when_the_new_one_is_absent(self, skills_dir: Path) -> None:
        """Never leave the user with neither copy."""
        _write_skill(skills_dir / "cao-plugin", "cao-plugin")

        removed = init_module.retire_renamed_skills()

        assert removed == []
        assert (skills_dir / "cao-plugin" / "SKILL.md").is_file()

    def test_keeps_the_old_directory_when_the_new_one_is_incomplete(self, skills_dir: Path) -> None:
        """A directory without a readable SKILL.md is not a usable replacement."""
        _write_skill(skills_dir / "cao-plugin", "cao-plugin")
        (skills_dir / "cao-event-plugin").mkdir()

        removed = init_module.retire_renamed_skills()

        assert removed == []
        assert (skills_dir / "cao-plugin" / "SKILL.md").is_file()

    def test_is_idempotent(self, skills_dir: Path) -> None:
        _write_skill(skills_dir / "cao-plugin", "cao-plugin")
        _write_skill(skills_dir / "cao-event-plugin", "cao-event-plugin")

        first = init_module.retire_renamed_skills()
        second = init_module.retire_renamed_skills()

        assert first == ["cao-plugin"]
        assert second == []

    def test_nothing_to_do_on_a_fresh_install(self, skills_dir: Path) -> None:
        _write_skill(skills_dir / "cao-event-plugin", "cao-event-plugin")

        assert init_module.retire_renamed_skills() == []

    def test_a_symlinked_old_skill_is_unlinked_not_followed(
        self, skills_dir: Path, tmp_path: Path
    ) -> None:
        """Removing must not delete whatever a user symlinked in."""
        external = tmp_path / "external-skill"
        _write_skill(external, "cao-plugin")
        (skills_dir / "cao-plugin").symlink_to(external, target_is_directory=True)
        _write_skill(skills_dir / "cao-event-plugin", "cao-event-plugin")

        removed = init_module.retire_renamed_skills()

        assert removed == ["cao-plugin"]
        assert not (skills_dir / "cao-plugin").exists()
        # The link target is untouched.
        assert (external / "SKILL.md").is_file()

    def test_an_unremovable_directory_does_not_raise(self, skills_dir: Path, monkeypatch) -> None:
        """A stale skill is cosmetic; a failed `cao init` is not."""
        import shutil

        _write_skill(skills_dir / "cao-plugin", "cao-plugin")
        _write_skill(skills_dir / "cao-event-plugin", "cao-event-plugin")

        def _refuse(*args, **kwargs):
            raise PermissionError("cannot remove")

        monkeypatch.setattr(shutil, "rmtree", _refuse)

        assert init_module.retire_renamed_skills() == []


class TestSeedingCallsRetirement:
    def test_seed_default_skills_runs_retirement_after_seeding(
        self, skills_dir: Path, monkeypatch
    ) -> None:
        """Ordering matters: the replacement must exist before the old is removed."""
        calls: list[str] = []
        monkeypatch.setattr(
            init_module,
            "retire_renamed_skills",
            lambda: calls.append("retired") or [],
        )

        init_module.seed_default_skills()

        assert calls == ["retired"]
