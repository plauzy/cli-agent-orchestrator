"""Cross-provider skill delivery verification (W6) — the Increment 1 gate.

_Requirements: 13.2_

The projection design's entire claim is that materializing a plugin skill inside
``SKILLS_DIR`` makes it reachable by **every** provider with no provider-specific
code. That claim is only worth as much as the artifact it is checked against, so
each test here drives the provider's *real* delivery artifact rather than a mock:

===================  ==================================================
Provider(s)          Artifact asserted
===================  ==================================================
claude_code, codex,  ``build_skill_catalog()`` output, then
kimi_cli,            ``BaseProvider._apply_skill_prompt`` -- the exact
antigravity_cli      string appended to the system prompt at launch
copilot_cli          the baked ``.agent.md`` body on disk, including
                     after an install-time refresh
kiro_cli             the ``skill://`` glob in the agent JSON, expanded
                     against the real filesystem
opencode_cli         traversal through the ``skills`` symlink
===================  ==================================================

One finding is recorded explicitly in ``TestKiroGlobSymlinkSemantics`` below: the
Kiro path depends on the glob implementation following directory symlinks, which
is **not** universal. See that class for the detail.
"""

from __future__ import annotations

import glob as globmod
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Set

import frontmatter
import pytest

from cli_agent_orchestrator.agent_plugins.store import InstalledPluginStore
from cli_agent_orchestrator.models.provider import ProviderType

from .conftest import ProjectionEnv, write_skill

# The seven providers Requirement 13.2 enumerates.
ALL_PROVIDERS = [
    ProviderType.CLAUDE_CODE.value,
    ProviderType.CODEX.value,
    ProviderType.KIMI_CLI.value,
    ProviderType.ANTIGRAVITY_CLI.value,
    ProviderType.COPILOT_CLI.value,
    ProviderType.KIRO_CLI.value,
    ProviderType.OPENCODE_CLI.value,
]

# Providers that consume a catalog string built at launch.
RUNTIME_CATALOG_PROVIDERS = [
    ProviderType.CLAUDE_CODE.value,
    ProviderType.CODEX.value,
    ProviderType.KIMI_CLI.value,
    ProviderType.ANTIGRAVITY_CLI.value,
]

PROFILE_NAME = "delivery-agent"


@dataclass
class DeliveryEnv:
    """A fully isolated environment covering every provider's delivery path."""

    projection: ProjectionEnv
    skills_dir: Path
    agent_store: Path
    context_dir: Path
    kiro_dir: Path
    copilot_dir: Path
    opencode_config_dir: Path
    opencode_agents_dir: Path
    extra_skill_dir: Path

    def write_profile(self, name: str = PROFILE_NAME) -> Path:
        """Write a source agent profile the install path can read."""
        path = self.agent_store / f"{name}.md"
        path.write_text(
            f"---\nname: {name}\ndescription: Delivery test agent\n---\n"
            f"You are the delivery test agent.\n",
            encoding="utf-8",
        )
        return path

    def install_plugin(self, name: str = "delivery-plugin", **kwargs) -> object:
        """Install a plugin, projecting its skills into this env's SKILLS_DIR."""
        return self.projection.install(name, **kwargs)


def build_delivery_env(
    base: Path, monkeypatch: pytest.MonkeyPatch, tag: str = "env"
) -> DeliveryEnv:
    """Redirect every provider's delivery path under ``base/<tag>``.

    All of these constants are module-level bindings resolved at import, and all
    of them point at the developer's real ``$HOME`` by default, so each one must
    be patched on the *consuming module* rather than on ``constants``.

    Exposed as a function, not just a fixture, so a property test can build a
    **fresh** environment per generated example — a function-scoped fixture is
    created once per test and would let state leak between examples.
    """
    tmp_path = base / tag
    tmp_path.mkdir(parents=True, exist_ok=True)

    skills_dir = tmp_path / "skills"
    agent_store = tmp_path / "agent-store"
    context_dir = tmp_path / "agent-context"
    kiro_dir = tmp_path / "kiro-agents"
    copilot_dir = tmp_path / "copilot-agents"
    opencode_config_dir = tmp_path / "opencode"
    opencode_agents_dir = opencode_config_dir / "agents"
    extra_skill_dir = tmp_path / "extra-skills"

    for directory in (
        skills_dir,
        agent_store,
        context_dir,
        kiro_dir,
        copilot_dir,
        extra_skill_dir,
    ):
        directory.mkdir(parents=True, exist_ok=True)

    targets = {
        "cli_agent_orchestrator.services.install_service.SKILLS_DIR": skills_dir,
        "cli_agent_orchestrator.services.install_service.AGENT_CONTEXT_DIR": context_dir,
        "cli_agent_orchestrator.services.install_service.KIRO_AGENTS_DIR": kiro_dir,
        "cli_agent_orchestrator.services.install_service.COPILOT_AGENTS_DIR": copilot_dir,
        "cli_agent_orchestrator.services.install_service.OPENCODE_AGENTS_DIR": opencode_agents_dir,
        "cli_agent_orchestrator.utils.skills.SKILLS_DIR": skills_dir,
        "cli_agent_orchestrator.utils.opencode_config.SKILLS_DIR": skills_dir,
        "cli_agent_orchestrator.utils.opencode_config.OPENCODE_CONFIG_DIR": opencode_config_dir,
        "cli_agent_orchestrator.utils.opencode_config.OPENCODE_CONFIG_FILE": (
            opencode_config_dir / "opencode.json"
        ),
        "cli_agent_orchestrator.utils.skill_injection.COPILOT_AGENTS_DIR": copilot_dir,
        "cli_agent_orchestrator.utils.skill_injection.AGENT_CONTEXT_DIR": context_dir,
        "cli_agent_orchestrator.services.profile_store.LOCAL_AGENT_STORE_DIR": agent_store,
        "cli_agent_orchestrator.utils.agent_profiles.LOCAL_AGENT_STORE_DIR": agent_store,
    }
    for target, value in targets.items():
        monkeypatch.setattr(target, value)

    # Keep profile and skill resolution from reaching the developer's real dirs,
    # while still exercising the extra-dirs union that Requirement 13.2 names.
    monkeypatch.setattr(
        "cli_agent_orchestrator.services.settings_service.get_agent_dirs", lambda: {}
    )
    monkeypatch.setattr(
        "cli_agent_orchestrator.services.settings_service.get_extra_agent_dirs", lambda: []
    )
    monkeypatch.setattr(
        "cli_agent_orchestrator.services.settings_service.get_extra_skill_dirs",
        lambda: [str(extra_skill_dir)],
    )

    projection = ProjectionEnv(
        store=InstalledPluginStore(
            plugins_dir=tmp_path / "agent-plugins", data_dir=tmp_path / "agent-plugin-data"
        ),
        skills_dir=skills_dir,
        sources=tmp_path / "sources",
    )

    return DeliveryEnv(
        projection=projection,
        skills_dir=skills_dir,
        agent_store=agent_store,
        context_dir=context_dir,
        kiro_dir=kiro_dir,
        copilot_dir=copilot_dir,
        opencode_config_dir=opencode_config_dir,
        opencode_agents_dir=opencode_agents_dir,
        extra_skill_dir=extra_skill_dir,
    )


@pytest.fixture
def delivery(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> DeliveryEnv:
    """An isolated environment covering every provider's delivery path."""
    return build_delivery_env(tmp_path, monkeypatch)


def catalog_skill_names(catalog: str) -> Set[str]:
    """Parse skill names out of a rendered catalog block.

    The catalog's per-skill line is ``- **<name>**: <description>``.
    """
    names = set()
    for line in catalog.splitlines():
        stripped = line.strip()
        if stripped.startswith("- **") and "**:" in stripped:
            names.add(stripped[len("- **") : stripped.index("**:")])
    return names


# ---------------------------------------------------------------------------
# 7.1 Runtime-catalog providers
# ---------------------------------------------------------------------------


class TestRuntimeCatalogProviders:
    """_Requirements: 13.2 — Claude Code, Codex, Kimi, Antigravity._

    ``build_skill_catalog`` is the whole artifact for these four: everything
    downstream is a mechanical append performed by
    ``BaseProvider._apply_skill_prompt``, which is asserted too.
    """

    def test_projected_skill_appears_in_the_runtime_catalog(self, delivery: DeliveryEnv) -> None:
        from cli_agent_orchestrator.utils.skills import build_skill_catalog

        delivery.install_plugin(skills=("plugin-skill",))

        catalog = build_skill_catalog()

        assert "plugin-skill" in catalog_skill_names(catalog)

    def test_catalog_line_is_fully_rendered_from_the_projected_skill(
        self, delivery: DeliveryEnv
    ) -> None:
        """The description comes from the plugin's own SKILL.md frontmatter."""
        from cli_agent_orchestrator.utils.skills import build_skill_catalog

        source = delivery.projection.make_plugin("delivery-plugin", skills=())
        write_skill(source / "skills" / "plugin-skill", description="Provided by a plugin.")
        delivery.projection.install("delivery-plugin", source_dir=source)

        catalog = build_skill_catalog()

        assert "- **plugin-skill**: Provided by a plugin." in catalog

    @pytest.mark.parametrize("provider", RUNTIME_CATALOG_PROVIDERS)
    def test_provider_is_registered_as_a_runtime_catalog_consumer(self, provider: str) -> None:
        from cli_agent_orchestrator.services.terminal_service import (
            RUNTIME_SKILL_PROMPT_PROVIDERS,
        )

        assert provider in RUNTIME_SKILL_PROMPT_PROVIDERS

    def test_runtime_provider_set_is_exactly_the_four_expected(self) -> None:
        """Pins the split so a new provider cannot silently change delivery."""
        from cli_agent_orchestrator.services.terminal_service import (
            RUNTIME_SKILL_PROMPT_PROVIDERS,
        )

        assert set(RUNTIME_SKILL_PROMPT_PROVIDERS) == set(RUNTIME_CATALOG_PROVIDERS)

    @pytest.mark.parametrize("provider", RUNTIME_CATALOG_PROVIDERS)
    def test_catalog_reaches_the_provider_system_prompt(
        self, delivery: DeliveryEnv, provider: str
    ) -> None:
        """Drive the real append that every runtime provider performs."""
        from cli_agent_orchestrator.providers.base import BaseProvider
        from cli_agent_orchestrator.utils.skills import build_skill_catalog

        delivery.install_plugin(skills=("plugin-skill",))
        catalog = build_skill_catalog()

        # _apply_skill_prompt is defined on BaseProvider and shared by all four.
        applied = BaseProvider._apply_skill_prompt(_StubProvider(catalog), "You are an agent.")

        assert "You are an agent." in applied
        assert "plugin-skill" in catalog_skill_names(applied)

    def test_profile_skill_filter_still_scopes_a_projected_skill(
        self, delivery: DeliveryEnv
    ) -> None:
        """Projection does not bypass per-agent scoping."""
        from cli_agent_orchestrator.utils.skills import build_skill_catalog

        delivery.install_plugin(skills=("ads-report", "other-skill"))

        scoped = build_skill_catalog(["ads-*"])

        assert catalog_skill_names(scoped) == {"ads-report"}

    def test_removing_the_plugin_removes_it_from_the_catalog(self, delivery: DeliveryEnv) -> None:
        from cli_agent_orchestrator.utils.skills import build_skill_catalog

        delivery.install_plugin(skills=("plugin-skill",))
        assert "plugin-skill" in catalog_skill_names(build_skill_catalog())

        delivery.projection.uninstall("delivery-plugin")

        assert "plugin-skill" not in catalog_skill_names(build_skill_catalog())


class _StubProvider:
    """Minimal stand-in carrying only what ``_apply_skill_prompt`` reads."""

    def __init__(self, skill_prompt: str) -> None:
        self._skill_prompt = skill_prompt


# ---------------------------------------------------------------------------
# 7.2 Copilot — baked catalog
# ---------------------------------------------------------------------------


class TestCopilotBakedCatalog:
    """_Requirements: 13.2 — the baked ``.agent.md`` body._"""

    def test_projected_skill_is_baked_at_install_time(self, delivery: DeliveryEnv) -> None:
        from cli_agent_orchestrator.services.install_service import install_agent

        delivery.install_plugin(skills=("plugin-skill",))
        delivery.write_profile()

        result = install_agent(PROFILE_NAME, ProviderType.COPILOT_CLI.value)

        assert result.success is True, result.message
        agent_file = delivery.copilot_dir / f"{PROFILE_NAME}.agent.md"
        body = frontmatter.load(agent_file).content
        assert "plugin-skill" in catalog_skill_names(body)

    def test_installing_a_plugin_refreshes_an_already_installed_agent(
        self, delivery: DeliveryEnv
    ) -> None:
        """The install-time ``refresh_all_cao_managed_agents()`` call.

        This is the one delivery path baked at install time rather than read at
        launch, so without the refresh the Copilot catalog would silently go
        stale the moment a plugin is added.
        """
        from cli_agent_orchestrator.services.install_service import install_agent

        delivery.write_profile()
        result = install_agent(PROFILE_NAME, ProviderType.COPILOT_CLI.value)
        assert result.success is True, result.message

        agent_file = delivery.copilot_dir / f"{PROFILE_NAME}.agent.md"
        assert "later-skill" not in frontmatter.load(agent_file).content

        # refresh_agents=True: exercise the real install-time refresh.
        from cli_agent_orchestrator.agent_plugins import installer
        from cli_agent_orchestrator.agent_plugins.models import PluginSource

        source = delivery.projection.make_plugin("later-plugin", skills=("later-skill",))
        outcome = installer.install(
            PluginSource(kind="path", location=str(source)),
            store=delivery.projection.store,
            skills_dir=delivery.skills_dir,
            refresh_agents=True,
        )

        assert outcome.installed is True
        assert outcome.refreshed_agents == 1
        body = frontmatter.load(agent_file).content
        assert "later-skill" in catalog_skill_names(body)

    def test_removing_a_plugin_refreshes_the_baked_catalog(self, delivery: DeliveryEnv) -> None:
        from cli_agent_orchestrator.agent_plugins import installer
        from cli_agent_orchestrator.services.install_service import install_agent

        delivery.install_plugin(skills=("plugin-skill",))
        delivery.write_profile()
        assert install_agent(PROFILE_NAME, ProviderType.COPILOT_CLI.value).success is True

        agent_file = delivery.copilot_dir / f"{PROFILE_NAME}.agent.md"
        assert "plugin-skill" in frontmatter.load(agent_file).content

        installer.uninstall(
            "delivery-plugin",
            store=delivery.projection.store,
            skills_dir=delivery.skills_dir,
            refresh_agents=True,
        )

        assert "plugin-skill" not in catalog_skill_names(frontmatter.load(agent_file).content)

    def test_frontmatter_is_preserved_by_the_refresh(self, delivery: DeliveryEnv) -> None:
        from cli_agent_orchestrator.agent_plugins import installer
        from cli_agent_orchestrator.agent_plugins.models import PluginSource
        from cli_agent_orchestrator.services.install_service import install_agent

        delivery.write_profile()
        install_agent(PROFILE_NAME, ProviderType.COPILOT_CLI.value)
        agent_file = delivery.copilot_dir / f"{PROFILE_NAME}.agent.md"
        before = frontmatter.load(agent_file).metadata

        source = delivery.projection.make_plugin("p", skills=("s",))
        installer.install(
            PluginSource(kind="path", location=str(source)),
            store=delivery.projection.store,
            skills_dir=delivery.skills_dir,
            refresh_agents=True,
        )

        assert frontmatter.load(agent_file).metadata == before


# ---------------------------------------------------------------------------
# 7.3 Kiro CLI — skill:// glob
# ---------------------------------------------------------------------------


class TestKiroSkillGlob:
    """_Requirements: 13.2 — the ``skill://`` resource glob._"""

    @staticmethod
    def _skill_resources(agent_json: Dict) -> List[str]:
        return [r for r in agent_json["resources"] if r.startswith("skill://")]

    def _install(self, delivery: DeliveryEnv) -> Dict:
        from cli_agent_orchestrator.services.install_service import install_agent

        delivery.write_profile()
        result = install_agent(PROFILE_NAME, ProviderType.KIRO_CLI.value)
        assert result.success is True, result.message
        return json.loads((delivery.kiro_dir / f"{PROFILE_NAME}.json").read_text(encoding="utf-8"))

    def test_agent_json_carries_a_single_skill_glob_rooted_at_the_skill_store(
        self, delivery: DeliveryEnv
    ) -> None:
        delivery.install_plugin(skills=("plugin-skill",))

        resources = self._skill_resources(self._install(delivery))

        assert resources == [f"skill://{delivery.skills_dir}/**/SKILL.md"]

    def test_the_glob_is_unchanged_by_installing_a_plugin(self, delivery: DeliveryEnv) -> None:
        """Zero provider changes: the glob never has to be rewritten."""
        before = self._skill_resources(self._install(delivery))

        delivery.install_plugin(skills=("plugin-skill",))
        after = self._skill_resources(self._install(delivery))

        assert before == after

    def test_the_glob_expands_to_the_projected_skill_on_disk(self, delivery: DeliveryEnv) -> None:
        """Expand the real pattern with symlink-following semantics.

        ``glob.glob(..., recursive=True)`` follows directory symlinks, which is
        the semantics this delivery path requires. See
        ``TestKiroGlobSymlinkSemantics`` for why that is called out explicitly.
        """
        delivery.install_plugin(skills=("plugin-skill",))
        pattern = self._skill_resources(self._install(delivery))[0][len("skill://") :]

        matches = globmod.glob(pattern, recursive=True)

        assert any(Path(m).parent.name == "plugin-skill" for m in matches), matches

    def test_the_glob_expands_to_builtin_and_projected_skills_together(
        self, delivery: DeliveryEnv
    ) -> None:
        write_skill(delivery.skills_dir / "builtin-skill")
        delivery.install_plugin(skills=("plugin-skill",))
        pattern = self._skill_resources(self._install(delivery))[0][len("skill://") :]

        found = {Path(m).parent.name for m in globmod.glob(pattern, recursive=True)}

        assert {"builtin-skill", "plugin-skill"} <= found

    def test_projected_skill_content_is_readable_through_the_link(
        self, delivery: DeliveryEnv
    ) -> None:
        """Progressive loading reads the file; the link must resolve to content."""
        source = delivery.projection.make_plugin("delivery-plugin", skills=())
        write_skill(source / "skills" / "plugin-skill", description="Readable through the link.")
        delivery.projection.install("delivery-plugin", source_dir=source)

        text = (delivery.skills_dir / "plugin-skill" / "SKILL.md").read_text(encoding="utf-8")

        assert "Readable through the link." in text


class TestKiroGlobSymlinkSemantics:
    """Pin the symlink-traversal dependency the Kiro path rests on.

    **This is a real, recorded risk, not a curiosity.** CAO writes the *string*
    ``skill://<SKILLS_DIR>/**/SKILL.md``; Kiro CLI expands it. Whether a
    projected skill is visible therefore depends on whether Kiro's glob follows
    **directory symlinks**, and implementations genuinely disagree:

    * follows: ``glob.glob(recursive=True)``, ``os.walk(followlinks=True)``
    * does **not** follow: ``pathlib.Path.glob('**/...')`` before Python 3.13,
      ``os.walk()`` by default

    A non-following implementation would make plugin skills invisible to Kiro
    while every other provider sees them. These tests document the dependency so
    the assumption is explicit and regression-guarded rather than tacit.

    Note the mitigation already latent in the design: a **single-level** pattern
    (``*/SKILL.md``) matches in *both* families, because the symlink is then the
    matched component rather than something to recurse into. Copy-mode
    projection (``skills.projection_mode: "copy"``) sidesteps the question
    entirely.
    """

    def test_symlink_following_glob_finds_the_projected_skill(self, delivery: DeliveryEnv) -> None:
        delivery.install_plugin(skills=("plugin-skill",))

        found = {
            Path(m).parent.name
            for m in globmod.glob(str(delivery.skills_dir / "**" / "SKILL.md"), recursive=True)
        }

        assert "plugin-skill" in found

    def test_pathlib_recursive_glob_does_not_follow_the_link(self, delivery: DeliveryEnv) -> None:
        """Recorded so the divergence is visible if this ever changes.

        If a future Python makes ``pathlib`` follow symlinks here, this test
        fails loudly and the risk note above can be retired.
        """
        delivery.install_plugin(skills=("plugin-skill",))

        found = {p.parent.name for p in delivery.skills_dir.glob("**/SKILL.md")}

        assert "plugin-skill" not in found

    def test_single_level_pattern_finds_it_under_both_families(self, delivery: DeliveryEnv) -> None:
        """The available mitigation, verified.

        A one-level pattern matches the projected skill in both the
        symlink-following and non-following implementations, because the symlink
        is the matched directory component.
        """
        delivery.install_plugin(skills=("plugin-skill",))

        stdlib = {
            Path(m).parent.name for m in globmod.glob(str(delivery.skills_dir / "*" / "SKILL.md"))
        }
        pathlib_found = {p.parent.name for p in delivery.skills_dir.glob("*/SKILL.md")}

        assert "plugin-skill" in stdlib
        assert "plugin-skill" in pathlib_found

    def test_copy_mode_projection_needs_no_symlink_traversal(self, delivery: DeliveryEnv) -> None:
        """The other mitigation: copy mode is visible to every implementation."""
        from cli_agent_orchestrator.agent_plugins.projection import PROJECTION_MODE_COPY

        delivery.install_plugin(skills=("plugin-skill",))
        delivery.projection.rebuild(mode=PROJECTION_MODE_COPY)

        found = {p.parent.name for p in delivery.skills_dir.glob("**/SKILL.md")}

        assert "plugin-skill" in found


# ---------------------------------------------------------------------------
# 7.4 OpenCode — skills symlink
# ---------------------------------------------------------------------------


class TestOpenCodeSkillsSymlink:
    """_Requirements: 13.2 — traversal through ``OPENCODE_CONFIG_DIR/skills``._"""

    def _install(self, delivery: DeliveryEnv) -> None:
        from cli_agent_orchestrator.services.install_service import install_agent

        delivery.write_profile()
        result = install_agent(PROFILE_NAME, ProviderType.OPENCODE_CLI.value)
        assert result.success is True, result.message

    def test_install_creates_the_skills_symlink_to_the_skill_store(
        self, delivery: DeliveryEnv
    ) -> None:
        delivery.install_plugin(skills=("plugin-skill",))

        self._install(delivery)

        link = delivery.opencode_config_dir / "skills"
        assert link.is_symlink()
        assert link.resolve() == delivery.skills_dir.resolve()

    def test_projected_skill_is_reachable_through_two_symlink_hops(
        self, delivery: DeliveryEnv
    ) -> None:
        """The real edge case: ``skills`` -> SKILLS_DIR -> plugin root.

        OpenCode traverses a symlink to the store, and the projected skill is
        itself a symlink out of that store, so this path is two hops deep.
        """
        delivery.install_plugin(skills=("plugin-skill",))
        self._install(delivery)

        skill_md = delivery.opencode_config_dir / "skills" / "plugin-skill" / "SKILL.md"

        assert skill_md.is_file()
        assert "plugin-skill" in skill_md.read_text(encoding="utf-8")

    def test_the_resolved_path_is_the_plugin_root(self, delivery: DeliveryEnv) -> None:
        delivery.install_plugin(skills=("plugin-skill",))
        self._install(delivery)

        resolved = (delivery.opencode_config_dir / "skills" / "plugin-skill").resolve()
        expected = (
            delivery.projection.store.plugin_root("delivery-plugin") / "skills" / "plugin-skill"
        )

        assert resolved == expected.resolve()

    def test_symlink_is_not_rewritten_when_a_plugin_is_installed_later(
        self, delivery: DeliveryEnv
    ) -> None:
        """Zero provider changes: nothing re-points the symlink."""
        self._install(delivery)
        link = delivery.opencode_config_dir / "skills"
        before = link.readlink()

        delivery.install_plugin(skills=("plugin-skill",))

        assert link.readlink() == before
        assert (link / "plugin-skill" / "SKILL.md").is_file()

    def test_enumeration_through_the_link_sees_builtin_and_projected(
        self, delivery: DeliveryEnv
    ) -> None:
        write_skill(delivery.skills_dir / "builtin-skill")
        delivery.install_plugin(skills=("plugin-skill",))
        self._install(delivery)

        link = delivery.opencode_config_dir / "skills"
        names = {entry.name for entry in link.iterdir() if (entry / "SKILL.md").is_file()}

        assert {"builtin-skill", "plugin-skill"} <= names


# ---------------------------------------------------------------------------
# Shared: the union Requirement 13.2 specifies
# ---------------------------------------------------------------------------


class TestExtraDirsUnion:
    """Projection composes with, rather than replaces, existing sources."""

    def test_catalog_is_the_union_of_builtin_extra_and_projected(
        self, delivery: DeliveryEnv
    ) -> None:
        from cli_agent_orchestrator.utils.skills import build_skill_catalog

        write_skill(delivery.skills_dir / "builtin-skill")
        write_skill(delivery.extra_skill_dir / "extra-skill")
        delivery.install_plugin(skills=("plugin-skill",))

        names = catalog_skill_names(build_skill_catalog())

        assert names == {"builtin-skill", "extra-skill", "plugin-skill"}

    def test_a_projected_skill_never_displaces_a_builtin_one(self, delivery: DeliveryEnv) -> None:
        """The content an agent actually loads is the pre-existing skill's.

        Asserted on the SKILL.md *body*, which is what ``load_skill_content``
        returns, so the two skills are genuinely distinguishable.
        """
        from cli_agent_orchestrator.utils.skills import load_skill_content

        builtin = delivery.skills_dir / "shared"
        builtin.mkdir(parents=True)
        (builtin / "SKILL.md").write_text(
            '---\nname: "shared"\ndescription: "The builtin one."\n---\n\nBUILTIN BODY\n',
            encoding="utf-8",
        )
        delivery.install_plugin(skills=("shared",))

        content = load_skill_content("shared")

        assert "BUILTIN BODY" in content


# ---------------------------------------------------------------------------
# Canonical example package, delivered end to end
# ---------------------------------------------------------------------------

CANONICAL_EXAMPLE = Path("/projects/sandbox/agent-plugins-example")


@pytest.mark.skipif(
    not (CANONICAL_EXAMPLE / "plugin.json").is_file(),
    reason="canonical agent-plugins-example checkout not present",
)
class TestCanonicalExampleIsDelivered:
    """_Requirements: 23.5 (delivery half) — the upstream example reaches a provider.

    Requirement 23.5 also asks that an intentionally invalid sibling skill be
    skipped with a report rather than rejecting the fixture. The upstream package
    currently ships **no** invalid sibling, so that clause is exercised against a
    locally-added invalid sibling below rather than asserted of upstream content
    CAO does not control.

    The "installed via the CLI" half of 23.5 belongs to W7 and is not claimed here.
    """

    def test_example_installs_and_projects_its_skill(self, delivery: DeliveryEnv) -> None:
        from cli_agent_orchestrator.agent_plugins import installer
        from cli_agent_orchestrator.agent_plugins.models import PluginSource

        outcome = installer.install(
            PluginSource(kind="path", location=str(CANONICAL_EXAMPLE)),
            store=delivery.projection.store,
            skills_dir=delivery.skills_dir,
            refresh_agents=False,
        )

        assert outcome.installed is True
        assert "migrate-agent-plugin" in outcome.projected_skill_names

    def test_example_skill_reaches_a_runtime_catalog_provider(self, delivery: DeliveryEnv) -> None:
        from cli_agent_orchestrator.agent_plugins import installer
        from cli_agent_orchestrator.agent_plugins.models import PluginSource
        from cli_agent_orchestrator.utils.skills import build_skill_catalog

        installer.install(
            PluginSource(kind="path", location=str(CANONICAL_EXAMPLE)),
            store=delivery.projection.store,
            skills_dir=delivery.skills_dir,
            refresh_agents=False,
        )

        assert "migrate-agent-plugin" in catalog_skill_names(build_skill_catalog())

    def test_example_skill_reaches_kiro_and_opencode(self, delivery: DeliveryEnv) -> None:
        from cli_agent_orchestrator.agent_plugins import installer
        from cli_agent_orchestrator.agent_plugins.models import PluginSource
        from cli_agent_orchestrator.services.install_service import install_agent

        installer.install(
            PluginSource(kind="path", location=str(CANONICAL_EXAMPLE)),
            store=delivery.projection.store,
            skills_dir=delivery.skills_dir,
            refresh_agents=False,
        )
        delivery.write_profile()

        assert install_agent(PROFILE_NAME, ProviderType.KIRO_CLI.value).success is True
        agent_json = json.loads(
            (delivery.kiro_dir / f"{PROFILE_NAME}.json").read_text(encoding="utf-8")
        )
        pattern = next(
            r[len("skill://") :] for r in agent_json["resources"] if r.startswith("skill://")
        )
        kiro_found = {Path(m).parent.name for m in globmod.glob(pattern, recursive=True)}
        assert "migrate-agent-plugin" in kiro_found

        assert install_agent(PROFILE_NAME, ProviderType.OPENCODE_CLI.value).success is True
        link = delivery.opencode_config_dir / "skills"
        assert (link / "migrate-agent-plugin" / "SKILL.md").is_file()

    def test_an_invalid_sibling_is_skipped_not_fatal(
        self, delivery: DeliveryEnv, tmp_path: Path
    ) -> None:
        """_Requirements: 23.5 — one bad sibling must not reject the package.

        Upstream ships no invalid skill, so a copy of the example is given one.
        """
        import shutil

        from cli_agent_orchestrator.agent_plugins import installer
        from cli_agent_orchestrator.agent_plugins.models import PluginSource
        from cli_agent_orchestrator.utils.skills import build_skill_catalog

        copied = tmp_path / "example-with-bad-sibling"
        shutil.copytree(CANONICAL_EXAMPLE, copied, symlinks=True)
        write_skill(copied / "skills" / "broken-sibling", name="does-not-match")

        outcome = installer.install(
            PluginSource(kind="path", location=str(copied)),
            store=delivery.projection.store,
            skills_dir=delivery.skills_dir,
            refresh_agents=False,
        )

        assert outcome.installed is True
        assert "migrate-agent-plugin" in outcome.projected_skill_names
        assert "broken-sibling" not in outcome.projected_skill_names
        assert any(f.code == "skill.invalid" for f in outcome.findings)
        # The good sibling still reaches a provider.
        assert "migrate-agent-plugin" in catalog_skill_names(build_skill_catalog())
