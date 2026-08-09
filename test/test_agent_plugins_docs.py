"""Guard tests for the agent-plugin documentation (W10).

_Requirements: 1.5, 13.1, 21.4, 22.1, 22.7_

These assert the properties the requirements make checkable — the warning being
early enough to be seen, the prerequisites being stated, and the two systems
being named apart — rather than trying to review prose.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
AGENT_PLUGINS_DOC = REPO_ROOT / "docs" / "agent-plugins.md"
EVENT_PLUGINS_DOC = REPO_ROOT / "docs" / "plugins.md"
SKILLS_DOC = REPO_ROOT / "docs" / "skills.md"

# "Stated in the first screenful" made concrete. A reader should not have to
# scroll to learn they are about to run untrusted code.
FIRST_SCREENFUL_LINES = 40


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


class TestUntrustedContentWarning:
    """_Requirements: 22.1 — stated at or before the point of install._"""

    def test_the_doc_exists(self) -> None:
        assert AGENT_PLUGINS_DOC.is_file()

    def test_warning_is_in_the_first_screenful(self) -> None:
        head = "\n".join(_text(AGENT_PLUGINS_DOC).splitlines()[:FIRST_SCREENFUL_LINES])

        assert "untrusted code and content" in head

    def test_warning_does_not_imply_a_trust_model_cao_lacks(self) -> None:
        """CAO implements no signing or provenance verification; say so."""
        head = "\n".join(_text(AGENT_PLUGINS_DOC).splitlines()[:FIRST_SCREENFUL_LINES])

        assert "no signing" in head
        assert "no provenance" in head


class TestPrerequisitesAndPosture:
    """_Requirements: 1.5, 22.7_"""

    def test_states_the_uv_prerequisite(self) -> None:
        assert "`uv`" in _text(AGENT_PLUGINS_DOC)

    def test_states_the_local_api_server_prerequisite(self) -> None:
        text = _text(AGENT_PLUGINS_DOC)

        assert "127.0.0.1:9889" in text
        assert "cao-server" in text

    def test_the_documented_endpoint_matches_the_real_default(self) -> None:
        """A stated prerequisite must be a fact, not a guess."""
        from cli_agent_orchestrator.constants import SERVER_HOST, SERVER_PORT

        assert f"{SERVER_HOST}:{SERVER_PORT}" in _text(AGENT_PLUGINS_DOC)

    def test_states_the_localhost_only_posture(self) -> None:
        """_Requirements: 22.7_"""
        text = _text(AGENT_PLUGINS_DOC).lower()

        assert "localhost-only" in text
        # And that overriding it is the user's decision, not a silent change.
        assert "cao_api_host" in text

    def test_documents_the_two_package_split(self) -> None:
        """_Requirements: 1.5 — which package an operator wants vs a contributor._"""
        text = _text(AGENT_PLUGINS_DOC)

        assert "agent-plugin/cao" in text
        assert "agent-plugin/cao-contributor" in text
        assert "Drive a CAO fleet" in text
        assert "Extend CAO itself" in text

    def test_package_skill_lists_match_the_build_configuration(self) -> None:
        """The doc must not drift from what the packages actually ship."""
        import importlib.util
        import sys

        spec = importlib.util.spec_from_file_location(
            "_build_agent_plugin_docs", REPO_ROOT / "scripts" / "build_agent_plugin.py"
        )
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)

        text = _text(AGENT_PLUGINS_DOC)
        for config in module.PACKAGES:
            for skill in config.skills:
                assert skill in text, f"{config.name}: doc does not mention {skill!r}"


class TestEventPluginDisambiguation:
    """_Requirements: 21.4 — the two systems are always named apart._"""

    def test_event_plugin_page_is_retitled(self) -> None:
        first_heading = _text(EVENT_PLUGINS_DOC).splitlines()[0]

        assert first_heading == "# Event Plugins"

    def test_event_plugin_page_carries_a_disambiguation_banner(self) -> None:
        head = "\n".join(_text(EVENT_PLUGINS_DOC).splitlines()[:FIRST_SCREENFUL_LINES])

        assert "agent plugin" in head.lower()
        assert "agent-plugins.md" in head

    def test_agent_plugin_page_disambiguates_in_the_other_direction(self) -> None:
        text = _text(AGENT_PLUGINS_DOC)

        assert "event plugin" in text.lower()
        assert "plugins.md" in text

    def test_the_event_plugin_page_keeps_its_path(self) -> None:
        """Retitling must not break inbound links."""
        assert EVENT_PLUGINS_DOC.is_file()

    @pytest.mark.parametrize(
        "source,label",
        [
            ("README.md", "[Event Plugins](docs/plugins.md)"),
            ("CODEBASE.md", "[Event Plugins](docs/plugins.md)"),
            ("docs/control-planes.md", "[Event Plugins](plugins.md)"),
        ],
    )
    def test_inbound_links_use_the_qualified_name(self, source: str, label: str) -> None:
        """A bare "Plugins" label outside a page that scopes it is ambiguous."""
        assert label in _text(REPO_ROOT / source)

    def test_no_bare_plugins_link_label_remains(self) -> None:
        """No maintained page still links to the event-plugin page as "Plugins"."""
        offenders = []
        for source in ("README.md", "CODEBASE.md", "docs/control-planes.md"):
            text = _text(REPO_ROOT / source)
            if re.search(r"\[Plugins?\]\((?:docs/)?plugins\.md\)", text):
                offenders.append(source)

        assert offenders == []


class TestSkillsDocCoversProjection:
    """_Requirements: 13.1_"""

    def test_has_a_plugin_provided_skills_section(self) -> None:
        assert "## Plugin-provided skills" in _text(SKILLS_DOC)

    def test_explains_the_projection_and_the_collision_rules(self) -> None:
        text = _text(SKILLS_DOC)

        assert "projected" in text
        # The two rules an operator actually hits.
        assert "always wins" in text
        assert "sorts first" in text

    def test_documents_the_copy_mode_fallback(self) -> None:
        assert "projection_mode" in _text(SKILLS_DOC)

    def test_agent_plugins_doc_links_to_this_section(self) -> None:
        assert "skills.md#plugin-provided-skills" in _text(AGENT_PLUGINS_DOC)

    def test_the_extra_dirs_limitation_is_recorded(self) -> None:
        """The W6 finding, per the Requirement 13 amendment (Criterion 7)."""
        text = _text(SKILLS_DOC)

        assert "extra_skill_dirs" in text
        assert "Known Limitations" in text
        assert "Kiro CLI or OpenCode CLI" in text


class TestProvisionalPendingDecisions:
    """The M1-M4 gate is recorded in the docs, not just in the commit message."""

    def test_agent_plugins_doc_marks_itself_provisional(self) -> None:
        head = "\n".join(_text(AGENT_PLUGINS_DOC).splitlines()[:FIRST_SCREENFUL_LINES])

        assert "PROVISIONAL PENDING M1-M4" in head

    def test_event_plugin_retitle_is_marked_provisional_pending_m3(self) -> None:
        """Requirement 21.4 leaves the exact retitle and banner to M3."""
        head = "\n".join(_text(EVENT_PLUGINS_DOC).splitlines()[:FIRST_SCREENFUL_LINES])

        assert "PROVISIONAL PENDING M3" in head
