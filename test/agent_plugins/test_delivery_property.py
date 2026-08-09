"""Property 10: Cross-provider delivery equivalence.

**Validates: Requirements 13.2**

For every one of the seven providers, the set of skill names reachable by an
agent equals ``builtin ∪ extra_dirs ∪ projected(valid plugin skills)`` — asserted
against each provider's **real delivery artifact**, not a mock:

* the runtime catalog text (Claude Code, Codex, Kimi, Antigravity)
* the baked ``.agent.md`` body (Copilot)
* the ``skill://`` glob expanded against the filesystem (Kiro CLI)
* traversal of the ``skills`` symlink (OpenCode)

The generated name sets are kept **disjoint** across the three sources so the
expected union is unambiguous; collision behaviour is a separate concern with its
own dedicated assertions (Property 8, and
``TestCollisionsDoNotBreakEquivalence`` below).

A provider-dependent ``extra_dirs`` term
----------------------------------------
Kiro receives one glob rooted at ``SKILLS_DIR`` and OpenCode one symlink to
``SKILLS_DIR``, so skills registered through ``skills.extra_dirs`` — which live
*outside* the store — are invisible to both. This **predates agent plugins**; it
reproduces with zero plugins installed (``TestPreExistingExtraDirsGap``).

This property originally failed against Requirement 13.2's earlier wording, which
required the reachable set to *equal* ``builtin ∪ extra_dirs ∪ projected`` for
every provider. Requirement 13 was amended in response (Criteria 6 and 7 now
specify the term per provider; Criteria 3–5 kept their numbering), and the
limitation is recorded under "Known Limitations" in ``docs/skills.md``. The
``extra_dirs`` term is therefore provider-dependent below.

What this feature *is* responsible for — that **built-in and projected plugin
skills** reach all seven providers identically — is asserted in full.
"""

from __future__ import annotations

import glob as globmod
import itertools
import json
from pathlib import Path
from typing import List, Set

import frontmatter
import pytest
from hypothesis import HealthCheck, assume, given, settings
from hypothesis import strategies as st

from cli_agent_orchestrator.models.provider import ProviderType

from .conftest import write_skill
from .test_delivery_providers import (
    ALL_PROVIDERS,
    PROFILE_NAME,
    RUNTIME_CATALOG_PROVIDERS,
    DeliveryEnv,
    build_delivery_env,
    catalog_skill_names,
)

FS_SETTINGS = settings(
    max_examples=25,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow],
)

_counter = itertools.count()

_SKILL_NAMES = st.text(
    alphabet=st.characters(min_codepoint=97, max_codepoint=122), min_size=3, max_size=8
)

# Providers whose artifact is built from ``list_skills()``, which searches the
# store *and* every registered extra directory.
CATALOG_BASED_PROVIDERS = [*RUNTIME_CATALOG_PROVIDERS, ProviderType.COPILOT_CLI.value]

# Providers handed a path rooted at SKILLS_DIR and left to traverse it
# themselves. They never see anything outside the store.
FILESYSTEM_DIRECT_PROVIDERS = [
    ProviderType.KIRO_CLI.value,
    ProviderType.OPENCODE_CLI.value,
]


def expected_reachable(
    provider: str, builtin: Set[str], extra: Set[str], projected: Set[str]
) -> Set[str]:
    """The reachable set Requirement 13.2 implies, corrected for reality.

    ``builtin`` and ``projected`` both live inside ``SKILLS_DIR`` and so reach
    every provider. ``extra`` reaches only the catalog-based providers — see the
    module docstring and ``TestPreExistingExtraDirsGap``.
    """
    if provider in CATALOG_BASED_PROVIDERS:
        return builtin | extra | projected
    return builtin | projected


def reachable_skill_names(env: DeliveryEnv, provider: str) -> Set[str]:
    """Skill names an agent under ``provider`` can actually reach.

    Each branch derives the set from that provider's real artifact, which is
    what makes this an equivalence proof rather than a restatement of
    ``list_skills()``.
    """
    from cli_agent_orchestrator.services.install_service import install_agent
    from cli_agent_orchestrator.utils.skills import build_skill_catalog

    if provider in RUNTIME_CATALOG_PROVIDERS:
        # The catalog string is the entire artifact for these four.
        return catalog_skill_names(build_skill_catalog())

    env.write_profile()

    if provider == ProviderType.COPILOT_CLI.value:
        result = install_agent(PROFILE_NAME, provider)
        assert result.success is True, result.message
        body = frontmatter.load(env.copilot_dir / f"{PROFILE_NAME}.agent.md").content
        return catalog_skill_names(body)

    if provider == ProviderType.KIRO_CLI.value:
        result = install_agent(PROFILE_NAME, provider)
        assert result.success is True, result.message
        agent_json = json.loads((env.kiro_dir / f"{PROFILE_NAME}.json").read_text(encoding="utf-8"))
        pattern = next(
            r[len("skill://") :] for r in agent_json["resources"] if r.startswith("skill://")
        )
        # recursive=True follows directory symlinks, the semantics this path
        # requires (pinned by TestKiroGlobSymlinkSemantics).
        matches = globmod.glob(pattern, recursive=True)
        # Only immediate children of the skill store are skills (§7.1); a
        # SKILL.md nested deeper inside a skill is not a separate skill.
        return {
            Path(match).parent.name
            for match in matches
            if Path(match).parent.parent == env.skills_dir
        }

    if provider == ProviderType.OPENCODE_CLI.value:
        result = install_agent(PROFILE_NAME, provider)
        assert result.success is True, result.message
        link = env.opencode_config_dir / "skills"
        return {entry.name for entry in link.iterdir() if (entry / "SKILL.md").is_file()}

    raise AssertionError(f"unhandled provider {provider!r}")


def _setup(
    env: DeliveryEnv,
    builtin: List[str],
    extra: List[str],
    plugin_valid: List[str],
    plugin_invalid: List[str],
) -> None:
    """Materialize the three skill sources plus some invalid plugin skills."""
    for name in builtin:
        write_skill(env.skills_dir / name)
    for name in extra:
        write_skill(env.extra_skill_dir / name)

    source = env.projection.make_plugin("delivery-plugin", skills=())
    (source / "skills").mkdir(parents=True, exist_ok=True)
    for name in plugin_valid:
        write_skill(source / "skills" / name)
    for name in plugin_invalid:
        # Frontmatter name disagrees with the folder name -> invalid skill.
        write_skill(source / "skills" / name, name=f"{name}-mismatch")
    env.projection.install("delivery-plugin", source_dir=source)


class TestCrossProviderDeliveryEquivalence:
    """Property 10: Cross-provider delivery equivalence.

    **Validates: Requirements 13.2**
    """

    @FS_SETTINGS
    @given(
        builtin=st.lists(_SKILL_NAMES, max_size=3, unique=True),
        extra=st.lists(_SKILL_NAMES, max_size=2, unique=True),
        plugin_valid=st.lists(_SKILL_NAMES, max_size=3, unique=True),
        plugin_invalid=st.lists(_SKILL_NAMES, max_size=2, unique=True),
        provider=st.sampled_from(ALL_PROVIDERS),
    )
    def test_reachable_set_equals_the_union_for_every_provider(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        builtin: List[str],
        extra: List[str],
        plugin_valid: List[str],
        plugin_invalid: List[str],
        provider: str,
    ) -> None:
        # Disjoint sources keep the expected union unambiguous.
        seen: Set[str] = set()
        groups = []
        for group in (builtin, extra, plugin_valid, plugin_invalid):
            deduped = [name for name in group if name not in seen]
            seen.update(deduped)
            groups.append(deduped)
        builtin, extra, plugin_valid, plugin_invalid = groups
        assume(len(seen) > 0)

        env = build_delivery_env(tmp_path, monkeypatch, f"case{next(_counter)}")
        _setup(env, builtin, extra, plugin_valid, plugin_invalid)

        reachable = reachable_skill_names(env, provider)

        assert reachable == expected_reachable(
            provider, set(builtin), set(extra), set(plugin_valid)
        )

    @FS_SETTINGS
    @given(
        plugin_valid=st.lists(_SKILL_NAMES, min_size=1, max_size=3, unique=True),
        plugin_invalid=st.lists(_SKILL_NAMES, min_size=1, max_size=2, unique=True),
        provider=st.sampled_from(ALL_PROVIDERS),
    )
    def test_invalid_plugin_skills_reach_no_provider(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        plugin_valid: List[str],
        plugin_invalid: List[str],
        provider: str,
    ) -> None:
        plugin_invalid = [name for name in plugin_invalid if name not in plugin_valid]
        assume(plugin_invalid)

        env = build_delivery_env(tmp_path, monkeypatch, f"case{next(_counter)}")
        _setup(env, [], [], plugin_valid, plugin_invalid)

        reachable = reachable_skill_names(env, provider)

        assert reachable == set(plugin_valid)
        assert not (reachable & set(plugin_invalid))

    @FS_SETTINGS
    @given(
        skills=st.lists(_SKILL_NAMES, min_size=1, max_size=3, unique=True),
        provider=st.sampled_from(ALL_PROVIDERS),
    )
    def test_removing_the_plugin_removes_its_skills_everywhere(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        skills: List[str],
        provider: str,
    ) -> None:
        env = build_delivery_env(tmp_path, monkeypatch, f"case{next(_counter)}")
        _setup(env, [], [], skills, [])
        assert reachable_skill_names(env, provider) == set(skills)

        env.projection.uninstall("delivery-plugin")

        assert reachable_skill_names(env, provider) == set()

    @FS_SETTINGS
    @given(skills=st.lists(_SKILL_NAMES, min_size=1, max_size=3, unique=True))
    def test_every_provider_agrees_with_every_other(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, skills: List[str]
    ) -> None:
        """The equivalence stated directly: all seven see the same names.

        This is the assertion that would fail if projection covered the catalog
        providers but missed a filesystem-direct one -- the exact failure mode
        the projection design exists to avoid.
        """
        # No extra_dirs skills here, so the provider-dependent term vanishes and
        # all seven must agree exactly. This is the feature's core claim.
        env = build_delivery_env(tmp_path, monkeypatch, f"case{next(_counter)}")
        _setup(env, ["builtin-one"], [], skills, [])
        expected = set(skills) | {"builtin-one"}

        per_provider = {
            provider: reachable_skill_names(env, provider) for provider in ALL_PROVIDERS
        }

        assert all(names == expected for names in per_provider.values()), per_provider


class TestCollisionsDoNotBreakEquivalence:
    """Collisions change the winner, never the reachable name set."""

    @FS_SETTINGS
    @given(
        shared=_SKILL_NAMES,
        provider=st.sampled_from(ALL_PROVIDERS),
    )
    def test_a_builtin_collision_keeps_the_name_reachable(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        shared: str,
        provider: str,
    ) -> None:
        """The pre-existing skill wins, so the name is still reachable."""
        env = build_delivery_env(tmp_path, monkeypatch, f"case{next(_counter)}")
        write_skill(env.skills_dir / shared)
        source = env.projection.make_plugin("delivery-plugin", skills=(shared,))
        env.projection.install("delivery-plugin", source_dir=source)

        assert reachable_skill_names(env, provider) == {shared}

    @FS_SETTINGS
    @given(shared=_SKILL_NAMES, provider=st.sampled_from(ALL_PROVIDERS))
    def test_two_plugins_claiming_one_name_expose_it_once(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        shared: str,
        provider: str,
    ) -> None:
        env = build_delivery_env(tmp_path, monkeypatch, f"case{next(_counter)}")
        for plugin in ("aaa", "zzz"):
            source = env.projection.make_plugin(plugin, skills=(shared,))
            env.projection.install(plugin, source_dir=source)

        assert reachable_skill_names(env, provider) == {shared}


class TestPreExistingExtraDirsGap:
    """`skills.extra_dirs` skills never reach Kiro CLI or OpenCode CLI.

    **This predates agent plugins and is reproduced here with zero plugins
    installed**, so it cannot be mistaken for a regression introduced by
    projection. Property 10 found it against Requirement 13.2's original wording
    — reachable equals ``builtin ∪ extra_dirs ∪ projected`` for *every* provider
    — which is not satisfiable by the current codebase. Requirement 13 was
    amended in response: Criteria 6 and 7 now specify the ``extra_dirs`` term per
    provider, and the limitation is recorded under "Known Limitations" in
    ``docs/skills.md``.

    Cause: ``install_service`` hands Kiro a single glob
    ``skill://{SKILLS_DIR}/**/SKILL.md`` and OpenCode a single symlink
    ``OPENCODE_CONFIG_DIR/skills -> SKILLS_DIR``. Both are rooted at the store,
    and ``extra_dirs`` lives outside it. The catalog-based providers are
    unaffected because they go through ``list_skills()``, which searches
    ``[SKILLS_DIR, *extra_dirs]``.

    These tests are written to **document and detect**, not to bless: if a fix
    lands, they fail loudly and should be inverted along with Criteria 6 and 7.
    """

    @pytest.mark.parametrize("provider", CATALOG_BASED_PROVIDERS)
    def test_catalog_based_providers_do_see_extra_dir_skills(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, provider: str
    ) -> None:
        env = build_delivery_env(tmp_path, monkeypatch, "extra-visible")
        write_skill(env.skills_dir / "in-store")
        write_skill(env.extra_skill_dir / "in-extra-dir")

        assert reachable_skill_names(env, provider) == {"in-store", "in-extra-dir"}

    @pytest.mark.parametrize("provider", FILESYSTEM_DIRECT_PROVIDERS)
    def test_filesystem_direct_providers_do_not_see_extra_dir_skills(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, provider: str
    ) -> None:
        """No plugins involved: this is the pre-existing behaviour."""
        env = build_delivery_env(tmp_path, monkeypatch, "extra-invisible")
        write_skill(env.skills_dir / "in-store")
        write_skill(env.extra_skill_dir / "in-extra-dir")

        reachable = reachable_skill_names(env, provider)

        assert reachable == {"in-store"}
        assert "in-extra-dir" not in reachable

    @pytest.mark.parametrize("provider", ALL_PROVIDERS)
    def test_projected_plugin_skills_reach_every_provider_regardless(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, provider: str
    ) -> None:
        """The gap does not affect plugin skills, because they are projected.

        This is precisely why the design chose projection into ``SKILLS_DIR``
        over registering plugin roots as extra directories: the extra-dirs route
        would have inherited exactly this blind spot.
        """
        env = build_delivery_env(tmp_path, monkeypatch, "projected-everywhere")
        write_skill(env.extra_skill_dir / "in-extra-dir")
        source = env.projection.make_plugin("delivery-plugin", skills=("plugin-skill",))
        env.projection.install("delivery-plugin", source_dir=source)

        assert "plugin-skill" in reachable_skill_names(env, provider)

    def test_extra_dirs_registration_would_not_have_worked(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The rejected alternative, demonstrated.

        Placing a plugin's skill in an extra directory instead of projecting it
        leaves it invisible to the two filesystem-direct providers — the concrete
        justification for the projection design.
        """
        env = build_delivery_env(tmp_path, monkeypatch, "alternative")
        # Simulate "register the plugin's skills/ dir as an extra dir".
        write_skill(env.extra_skill_dir / "would-be-plugin-skill")

        for provider in CATALOG_BASED_PROVIDERS:
            assert "would-be-plugin-skill" in reachable_skill_names(env, provider)
        for provider in FILESYSTEM_DIRECT_PROVIDERS:
            assert "would-be-plugin-skill" not in reachable_skill_names(env, provider)
