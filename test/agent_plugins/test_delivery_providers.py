"""W6 — cross-provider skill delivery verification.

**This is not optional test scaffolding.** design.md names W6 "the integration
gate for Increment 1": the whole point of projecting into ``SKILLS_DIR`` rather
than registering a new search directory is that *every* provider picks plugin
skills up through the pathway it already uses. If that claim is wrong for even
one provider, the central design decision is wrong, and only a test against each
provider's **real delivery artifact** can tell us.

The seven providers split three ways:

* **Runtime catalog** (Claude Code, Codex, Kimi, Antigravity) — the catalog text
  ``terminal_service`` builds at launch.
* **Baked catalog** (Copilot) — the ``.agent.md`` body written at install time.
* **Filesystem-direct** (Kiro CLI, OpenCode) — the ``skill://`` resource glob and
  the ``OPENCODE_CONFIG_DIR/skills`` symlink, neither of which goes anywhere near
  ``list_skills()``. These two are the reason the "extra search directory"
  alternative was rejected.
"""

from __future__ import annotations

import glob
from pathlib import Path

import pytest

from cli_agent_orchestrator.agent_plugins.installer import install
from cli_agent_orchestrator.agent_plugins.models import PluginSource
from cli_agent_orchestrator.models.provider import ProviderType
from cli_agent_orchestrator.services.terminal_service import RUNTIME_SKILL_PROMPT_PROVIDERS

from .conftest import build_plugin, write_skill

PROJECTED_SKILL = "plugin-provided-skill"
PROJECTED_DESCRIPTION = "Delivered to every provider through the existing pathway."


@pytest.fixture
def delivered(store, skills_dir, tmp_path, monkeypatch):
    """Install a plugin and point the skill machinery at the isolated store.

    ``utils/skills.py`` reads the module-level ``SKILLS_DIR``, so the patch has
    to land there — that module is what every one of the three delivery
    mechanisms ultimately consults (directly, or by reading the same path).
    """
    source = build_plugin(tmp_path / "src", "delivery-demo", skills=[PROJECTED_SKILL])
    write_skill(source / "skills" / PROJECTED_SKILL, PROJECTED_SKILL, PROJECTED_DESCRIPTION)

    outcome = install(
        PluginSource(kind="path", location=str(source)),
        store=store,
        skills_dir=skills_dir,
        refresh_agents=False,
    )
    assert outcome.installed

    monkeypatch.setattr("cli_agent_orchestrator.utils.skills.SKILLS_DIR", skills_dir)
    return skills_dir


class TestRuntimeCatalogProviders:
    """Claude Code, Codex, Kimi, Antigravity — Requirement 13.2, Task 7.1."""

    @pytest.mark.parametrize(
        "provider",
        [
            ProviderType.CLAUDE_CODE.value,
            ProviderType.CODEX.value,
            ProviderType.KIMI_CLI.value,
            ProviderType.ANTIGRAVITY_CLI.value,
        ],
    )
    def test_projected_skill_appears_in_the_runtime_catalog(self, delivered, provider):
        from cli_agent_orchestrator.utils.skills import build_skill_catalog

        assert provider in RUNTIME_SKILL_PROMPT_PROVIDERS

        catalog = build_skill_catalog()

        assert PROJECTED_SKILL in catalog
        assert PROJECTED_DESCRIPTION in catalog

    def test_a_profile_skill_filter_still_applies_to_projected_skills(self, delivered):
        """Projection adds skills to the catalog; it does not bypass its scoping."""
        from cli_agent_orchestrator.utils.skills import build_skill_catalog

        assert PROJECTED_SKILL in build_skill_catalog([PROJECTED_SKILL])
        assert PROJECTED_SKILL not in build_skill_catalog(["something-else"])

    def test_the_skill_is_loadable_by_name_through_the_normal_resolver(self, delivered):
        """The ``load_skill`` MCP tool's path, unmodified."""
        from cli_agent_orchestrator.utils.skills import load_skill_content, load_skill_metadata

        assert load_skill_metadata(PROJECTED_SKILL).description == PROJECTED_DESCRIPTION
        assert load_skill_content(PROJECTED_SKILL)


class TestCopilotBakedCatalog:
    """Copilot — Requirement 13.2, Task 7.2."""

    def test_projected_skill_appears_in_the_baked_agent_prompt(self, delivered):
        from cli_agent_orchestrator.models.agent_profile import AgentProfile
        from cli_agent_orchestrator.utils.skill_injection import compose_agent_prompt

        profile = AgentProfile(name="worker", description="d", prompt="Base prompt.")
        composed = compose_agent_prompt(profile)

        assert composed is not None
        assert PROJECTED_SKILL in composed
        assert "Base prompt." in composed

    def test_install_time_refresh_is_what_keeps_the_baked_catalog_current(
        self, store, skills_dir, tmp_path, monkeypatch
    ):
        """Requirement 13.1 / design step 6 — the one path baked at install time.

        Skipping the refresh call would leave Copilot ``.agent.md`` catalogs
        stale, which is exactly why the installer makes it.
        """
        calls = []
        monkeypatch.setattr(
            "cli_agent_orchestrator.utils.skill_injection.refresh_all_cao_managed_agents",
            lambda: calls.append(True) or [],
        )

        source = build_plugin(tmp_path / "src", "refresh-demo", skills=["alpha"])
        install(
            PluginSource(kind="path", location=str(source)),
            store=store,
            skills_dir=skills_dir,
            refresh_agents=True,
        )

        assert calls, "installer must refresh baked provider artifacts"


class TestKiroFilesystemGlob:
    """Kiro CLI — Requirement 13.2, Task 7.3."""

    def test_the_skill_resource_glob_traverses_the_projected_link(self, delivered):
        """Kiro receives exactly one ``skill://{SKILLS_DIR}/**/SKILL.md`` resource.

        No CAO code walks this glob — Kiro does, natively. So the assertion has
        to be that the glob *as written* expands through the projected symlink.
        """
        pattern = f"{delivered}/**/SKILL.md"
        matches = glob.glob(pattern, recursive=True)

        assert any(
            Path(match).parent.name == PROJECTED_SKILL for match in matches
        ), f"projected skill not reachable through {pattern}: {matches}"

    def test_the_installed_kiro_profile_carries_that_glob(self, monkeypatch, tmp_path):
        """The resource string itself is what ships; assert its exact shape."""
        skills_root = tmp_path / "skills"
        skills_root.mkdir()
        monkeypatch.setattr(
            "cli_agent_orchestrator.services.install_service.SKILLS_DIR", skills_root
        )
        from cli_agent_orchestrator.services import install_service

        source = Path(install_service.__file__).read_text(encoding="utf-8")
        assert 'f"skill://{SKILLS_DIR}/**/SKILL.md"' in source


class TestOpenCodeSymlink:
    """OpenCode — Requirement 13.2, Task 7.4."""

    def test_the_config_symlink_traversal_reaches_the_projected_skill(
        self, delivered, tmp_path, monkeypatch
    ):
        """OpenCode reads ``OPENCODE_CONFIG_DIR/skills`` → ``SKILLS_DIR``.

        Two links in a chain: OpenCode's own into the skill store, then CAO's
        projection into the plugin root. Both must traverse.
        """
        config_dir = tmp_path / "opencode"
        config_dir.mkdir()
        monkeypatch.setattr(
            "cli_agent_orchestrator.utils.opencode_config.OPENCODE_CONFIG_DIR", config_dir
        )
        monkeypatch.setattr("cli_agent_orchestrator.utils.opencode_config.SKILLS_DIR", delivered)

        from cli_agent_orchestrator.utils.opencode_config import ensure_skills_symlink

        ensure_skills_symlink()

        through_symlink = config_dir / "skills" / PROJECTED_SKILL / "SKILL.md"
        assert through_symlink.is_file()
        assert PROJECTED_DESCRIPTION in through_symlink.read_text(encoding="utf-8")


class TestNoNewLaunchTimeCost:
    """Requirement 13.5 — projection adds entries to a scan, not a new scan."""

    def test_search_dirs_are_unchanged_by_installing_a_plugin(
        self, store, skills_dir, tmp_path, monkeypatch
    ):
        monkeypatch.setattr("cli_agent_orchestrator.utils.skills.SKILLS_DIR", skills_dir)
        from cli_agent_orchestrator.utils.skills import _skill_search_dirs

        before = list(_skill_search_dirs())

        source = build_plugin(tmp_path / "src", "demo", skills=["alpha"])
        install(
            PluginSource(kind="path", location=str(source)),
            store=store,
            skills_dir=skills_dir,
            refresh_agents=False,
        )

        assert list(_skill_search_dirs()) == before


class TestEventPluginSystemUntouched:
    """Decision D7 regression guard — the *other* plugin system stays put."""

    def test_event_plugin_registry_still_imports_from_its_own_package(self):
        from cli_agent_orchestrator.plugins.registry import PluginRegistry

        assert PluginRegistry.__module__ == "cli_agent_orchestrator.plugins.registry"

    def test_entry_point_group_is_unchanged(self):
        import tomllib

        pyproject = Path(__file__).resolve().parents[2] / "pyproject.toml"
        data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
        assert "cao.plugins" in data["project"]["entry-points"]

    def test_no_symbol_in_agent_plugins_shadows_one_in_plugins(self):
        """The two packages are siblings; a shared public name would defeat that."""
        import cli_agent_orchestrator.agent_plugins as agent_plugins
        import cli_agent_orchestrator.plugins as event_plugins

        agent_names = {n for n in dir(agent_plugins) if not n.startswith("_")}
        event_names = {n for n in dir(event_plugins) if not n.startswith("_")}

        assert not (agent_names & event_names)

    def test_agent_plugins_is_not_nested_under_plugins(self):
        import cli_agent_orchestrator.agent_plugins as agent_plugins

        assert agent_plugins.__name__ == "cli_agent_orchestrator.agent_plugins"
        assert not agent_plugins.__name__.startswith("cli_agent_orchestrator.plugins.")

    def test_agent_plugins_imports_nothing_from_the_event_plugin_package(self):
        """A stated non-dependency, asserted rather than assumed.

        Parsed rather than grepped: the package docstrings discuss the
        event-plugin import path by name, and a substring match would flag the
        prose that exists precisely to keep the two systems distinct.
        """
        import ast

        package_dir = (
            Path(__file__).resolve().parents[2] / "src" / "cli_agent_orchestrator" / "agent_plugins"
        )
        event_package = "cli_agent_orchestrator.plugins"

        for module in sorted(package_dir.glob("*.py")):
            tree = ast.parse(module.read_text(encoding="utf-8"), filename=str(module))
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.module:
                    assert not node.module.startswith(
                        event_package
                    ), f"{module.name}: {node.module}"
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        assert not alias.name.startswith(
                            event_package
                        ), f"{module.name}: {alias.name}"
