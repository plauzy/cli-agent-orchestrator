"""Docs vocabulary and the prepared skill-rename retirement step (W10).

**Validates: Requirements 21.4, 21.5**

Two things are asserted here, and neither resolves a maintainer decision.

The **docs vocabulary rule** — "event plugin" and "agent plugin" are always
qualified, bare "plugin" only inside a document whose title already scopes it —
is checked mechanically, because a rule enforced by review alone decays.

The **retirement step** for renaming ``cao-plugin`` to ``cao-event-plugin`` is
built and tested while its rename map stays empty. M4 is unresolved, so
activating it must be a data edit rather than a migration project; the tests
below drive the mechanism through a synthetic rename to prove that.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from cli_agent_orchestrator.cli.commands import init as init_module

REPO_ROOT = Path(__file__).resolve().parents[2]
DOCS = REPO_ROOT / "docs"


class TestDocsVocabulary:
    """Requirement 21.4."""

    def test_agent_plugins_doc_exists(self):
        assert (DOCS / "agent-plugins.md").is_file()

    def test_event_plugin_doc_keeps_its_path(self):
        """Renaming the file would break inbound links for no comprehension gain."""
        assert (DOCS / "plugins.md").is_file()

    def test_event_plugin_doc_is_retitled(self):
        first_line = (DOCS / "plugins.md").read_text(encoding="utf-8").splitlines()[0]
        assert first_line.strip() == "# Event Plugins"

    def test_each_doc_banners_the_other(self):
        """A reader who lands on either page learns the other exists."""
        event_doc = (DOCS / "plugins.md").read_text(encoding="utf-8")
        agent_doc = (DOCS / "agent-plugins.md").read_text(encoding="utf-8")

        assert "agent-plugins.md" in event_doc
        assert "Agent Plugins" in event_doc.split("## ")[0]  # in the banner, before any section
        assert "plugins.md" in agent_doc
        assert "Event Plugins" in agent_doc.split("## ")[0]

    def test_the_retracted_roadmap_promise_is_recorded_not_deleted(self):
        """The `cao plugin` verb conflict is called out where it was promised."""
        event_doc = (DOCS / "plugins.md").read_text(encoding="utf-8")
        assert "M1" in event_doc

    @pytest.mark.parametrize("doc", ["agent-plugins.md", "plugins.md", "skills.md"])
    def test_bare_plugin_is_qualified_outside_a_scoped_title(self, doc):
        """Requirement 21.4, enforced rather than reviewed.

        ``docs/plugins.md`` and ``docs/agent-plugins.md`` both carry a scoping
        H1, so bare "plugin" is acceptable there. ``docs/skills.md`` does not,
        so every occurrence in it must be qualified.
        """
        text = (DOCS / doc).read_text(encoding="utf-8")
        title = text.splitlines()[0]
        if "Plugin" in title:
            return  # the title scopes the document

        # Strip fenced code, inline code, links, and paths — a bare `plugin`
        # inside `cao plugin add` or `docs/plugins.md` is not prose.
        prose = re.sub(r"```.*?```", "", text, flags=re.DOTALL)
        prose = re.sub(r"`[^`]*`", "", prose)
        prose = re.sub(r"\[[^\]]*\]\([^)]*\)", "", prose)

        unqualified = [
            match.group(0)
            for match in re.finditer(r"(?<![\w-])(?<!agent )(?<!event )plugins?\b", prose, re.I)
        ]
        assert unqualified == [], f"{doc}: unqualified 'plugin' in prose: {unqualified}"


class TestRenameRetirementIsPreparedNotActivated:
    """Requirement 21.5 — the mechanism exists; the decision does not."""

    def test_the_rename_map_is_empty_pending_m4(self):
        """This document does not settle M4, so nothing is renamed yet."""
        assert init_module.SKILL_RENAMES == {}

    def test_sync_skills_still_ships_the_current_name(self):
        """No rename has been applied to the shipped allowlist either."""
        import sys

        sys.path.insert(0, str(REPO_ROOT / "scripts"))
        import sync_skills

        assert "cao-plugin" in sync_skills.SHIPPED_SKILLS
        assert "cao-event-plugin" not in sync_skills.SHIPPED_SKILLS

    def test_the_coupling_is_documented_where_a_renamer_would_look(self):
        """A future renamer reads the allowlist; the warning has to be there."""
        source = (REPO_ROOT / "scripts" / "sync_skills.py").read_text(encoding="utf-8")
        assert "SKILL_RENAMES" in source


class TestRetirementMechanism:
    """Drive the mechanism through a synthetic rename, so M4 is a data edit."""

    @pytest.fixture
    def skills_dir(self, tmp_path, monkeypatch):
        path = tmp_path / "skills"
        path.mkdir()
        monkeypatch.setattr(init_module, "SKILLS_DIR", path)
        return path

    def _write(self, folder: Path, name: str, body: str = "Shared body.") -> Path:
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "SKILL.md").write_text(
            f"---\nname: {name}\ndescription: Authoring guide.\n---\n\n{body}\n",
            encoding="utf-8",
        )
        return folder

    def test_an_unmodified_old_folder_is_retired(self, skills_dir, monkeypatch):
        self._write(skills_dir / "old-name", "old-name")
        self._write(skills_dir / "new-name", "new-name")
        monkeypatch.setattr(init_module, "SKILL_RENAMES", {"old-name": "new-name"})

        retired = init_module._retire_renamed_skills()

        assert retired == ["old-name"]
        assert not (skills_dir / "old-name").exists()
        assert (skills_dir / "new-name" / "SKILL.md").is_file()

    def test_a_locally_modified_old_folder_is_kept_with_a_warning(
        self, skills_dir, monkeypatch, caplog
    ):
        """Deleting an operator's edits to tidy a catalog is the worse outcome."""
        self._write(skills_dir / "old-name", "old-name", body="I customized this.")
        self._write(skills_dir / "new-name", "new-name")
        monkeypatch.setattr(init_module, "SKILL_RENAMES", {"old-name": "new-name"})

        with caplog.at_level("WARNING"):
            retired = init_module._retire_renamed_skills()

        assert retired == []
        assert (skills_dir / "old-name").exists()
        assert "local modifications" in caplog.text

    def test_nothing_is_retired_before_the_replacement_exists(self, skills_dir, monkeypatch):
        self._write(skills_dir / "old-name", "old-name")
        monkeypatch.setattr(init_module, "SKILL_RENAMES", {"old-name": "new-name"})

        assert init_module._retire_renamed_skills() == []
        assert (skills_dir / "old-name").exists()

    def test_an_extra_file_counts_as_a_modification(self, skills_dir, monkeypatch):
        self._write(skills_dir / "old-name", "old-name")
        (skills_dir / "old-name" / "notes.md").write_text("mine", encoding="utf-8")
        self._write(skills_dir / "new-name", "new-name")
        monkeypatch.setattr(init_module, "SKILL_RENAMES", {"old-name": "new-name"})

        assert init_module._retire_renamed_skills() == []
        assert (skills_dir / "old-name").exists()

    def test_reference_files_are_compared_too(self, skills_dir, monkeypatch):
        old = self._write(skills_dir / "old-name", "old-name")
        new = self._write(skills_dir / "new-name", "new-name")
        (old / "references").mkdir()
        (new / "references").mkdir()
        (old / "references" / "guide.md").write_text("v1", encoding="utf-8")
        (new / "references" / "guide.md").write_text("v2", encoding="utf-8")
        monkeypatch.setattr(init_module, "SKILL_RENAMES", {"old-name": "new-name"})

        assert init_module._retire_renamed_skills() == []

    def test_the_frontmatter_name_line_is_not_treated_as_a_modification(
        self, skills_dir, monkeypatch
    ):
        """A rename necessarily changes it, so comparing it would retire nothing."""
        self._write(skills_dir / "old-name", "old-name")
        self._write(skills_dir / "new-name", "new-name")
        monkeypatch.setattr(init_module, "SKILL_RENAMES", {"old-name": "new-name"})

        assert init_module._retire_renamed_skills() == ["old-name"]

    def test_it_never_raises_on_an_unremovable_folder(self, skills_dir, monkeypatch):
        self._write(skills_dir / "old-name", "old-name")
        self._write(skills_dir / "new-name", "new-name")
        monkeypatch.setattr(init_module, "SKILL_RENAMES", {"old-name": "new-name"})

        def boom(*args, **kwargs):
            raise PermissionError("read-only filesystem")

        monkeypatch.setattr(init_module.shutil, "rmtree", boom)

        assert init_module._retire_renamed_skills() == []  # logged, not raised

    def test_an_empty_map_is_a_no_op(self, skills_dir):
        self._write(skills_dir / "cao-plugin", "cao-plugin")

        assert init_module._retire_renamed_skills() == []
        assert (skills_dir / "cao-plugin").exists()
