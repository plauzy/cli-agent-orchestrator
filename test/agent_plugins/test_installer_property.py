"""Property-based tests for the installer and projection (W5).

Properties 4, 5, 6, and 8 from design.md.

The generators for P8 are deliberately **adversarial for iteration order**:
names differing only in their final character, and name sets whose creation
order is the reverse of their sort order. A collision rule accidentally keyed on
``installed_at`` or ``os.scandir`` order must fail the permutation clause rather
than pass by luck.
"""

from __future__ import annotations

import itertools
import os
from pathlib import Path
from typing import Dict, List, Tuple

import pytest
from hypothesis import HealthCheck, assume, given, settings
from hypothesis import strategies as st

from cli_agent_orchestrator.agent_plugins import installer, provenance
from cli_agent_orchestrator.agent_plugins.models import PluginSource, Severity
from cli_agent_orchestrator.agent_plugins.store import InstalledPluginStore

from .conftest import ProjectionEnv, make_manifest, make_plugin, write_skill

FS_SETTINGS = settings(
    max_examples=40,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow],
)

_counter = itertools.count()

# §5.5-legal plugin names.
_PLUGIN_NAMES = st.text(
    alphabet=st.characters(min_codepoint=97, max_codepoint=122), min_size=3, max_size=8
)
_SKILL_NAMES = st.text(
    alphabet=st.characters(min_codepoint=97, max_codepoint=122), min_size=3, max_size=8
)


def _make_env(base: Path) -> ProjectionEnv:
    """A fresh, isolated environment for one hypothesis example."""
    root = base / f"env-{next(_counter)}"
    skills = root / "skills"
    skills.mkdir(parents=True)
    return ProjectionEnv(
        store=InstalledPluginStore(
            plugins_dir=root / "agent-plugins", data_dir=root / "agent-plugin-data"
        ),
        skills_dir=skills,
        sources=root / "sources",
    )


def _snapshot(env: ProjectionEnv, *, include_records: bool = True) -> Dict[str, object]:
    """A comparable picture of everything the installer may touch.

    Symlinks are recorded by their target rather than followed, so a projection
    silently repointed at a different plugin registers as a change.

    An absent directory and an existing-but-empty one are deliberately treated
    as identical. The property is about the *installed set and projection*, and
    a failed install that merely brought an empty ``agent-plugins/`` into
    existence has changed nothing an operator can observe.

    ``include_records=False`` omits ``.state/*.json``, for the idempotence
    property where an install record's ``installed_at`` legitimately differs
    between a single install and a reinstall.
    """
    picture: Dict[str, object] = {}

    for label, base in (("plugins", env.store.plugins_dir), ("skills", env.skills_dir)):
        entries: Dict[str, object] = {}
        if base.is_dir():
            for path in sorted(base.rglob("*")):
                relative = path.relative_to(base)
                if not include_records and relative.parts[:1] == (".state",):
                    continue
                key = f"{label}:{relative}"
                if path.is_symlink():
                    entries[key] = f"link->{os.readlink(path)}"
                elif path.is_dir():
                    entries[key] = "dir"
                else:
                    try:
                        entries[key] = path.read_bytes()
                    except OSError:
                        entries[key] = "unreadable"
        picture[label] = entries
    return picture


# ---------------------------------------------------------------------------
# Property 4: Isolation
# ---------------------------------------------------------------------------

_BROKEN_MANIFESTS = st.sampled_from(
    [
        "{ broken",
        "",
        "[]",
        "null",
        '{"name": "no-schema"}',
        '{"$schema": "https://example.test/x.json", "name": "wrong-schema"}',
        '{"$schema": "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json"}',
        '{"$schema": "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json",'
        ' "name": "Bad Name"}',
        '{"$schema": "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json",'
        ' "name": "double--dash"}',
        '{"$schema": "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json",'
        ' "name": "ok", "version": 5}',
    ]
)


class TestIsolation:
    """Property 4: Isolation.

    **Validates: Requirements 9.2, 9.3, 9.4**
    """

    @FS_SETTINGS
    @given(
        preinstalled=st.lists(_PLUGIN_NAMES, max_size=3, unique=True),
        broken=_BROKEN_MANIFESTS,
    )
    def test_failed_install_changes_nothing(
        self, tmp_path: Path, preinstalled: List[str], broken: str
    ) -> None:
        env = _make_env(tmp_path)
        for index, name in enumerate(preinstalled):
            env.install(name, skills=(f"skill{index}",))

        before = _snapshot(env)

        source = make_plugin(env.sources / "broken-one", "broken", raw_manifest=broken)
        outcome = installer.install(
            PluginSource(kind="path", location=str(source)),
            store=env.store,
            skills_dir=env.skills_dir,
            refresh_agents=False,
        )

        assert outcome.installed is False
        assert _snapshot(env) == before

    @FS_SETTINGS
    @given(preinstalled=st.lists(_PLUGIN_NAMES, max_size=3, unique=True))
    def test_unreachable_source_changes_nothing(
        self, tmp_path: Path, preinstalled: List[str]
    ) -> None:
        from cli_agent_orchestrator.agent_plugins.resolver import PluginResolutionError

        env = _make_env(tmp_path)
        for index, name in enumerate(preinstalled):
            env.install(name, skills=(f"skill{index}",))

        before = _snapshot(env)

        with pytest.raises(PluginResolutionError):
            installer.install(
                PluginSource(kind="path", location=str(env.sources / "does-not-exist")),
                store=env.store,
                skills_dir=env.skills_dir,
                refresh_agents=False,
            )

        assert _snapshot(env) == before

    @FS_SETTINGS
    @given(name=_PLUGIN_NAMES, skills=st.lists(_SKILL_NAMES, max_size=3, unique=True))
    def test_dry_run_changes_nothing(self, tmp_path: Path, name: str, skills: List[str]) -> None:
        env = _make_env(tmp_path)
        before = _snapshot(env)

        source = env.make_plugin(name, skills=tuple(skills))
        installer.install(
            PluginSource(kind="path", location=str(source)),
            dry_run=True,
            store=env.store,
            skills_dir=env.skills_dir,
            refresh_agents=False,
        )

        assert _snapshot(env) == before


# ---------------------------------------------------------------------------
# Property 5: Idempotence
# ---------------------------------------------------------------------------


class TestIdempotence:
    """Property 5: Idempotence.

    **Validates: Requirements 10.1, 10.2, 10.3, 10.4**
    """

    @FS_SETTINGS
    @given(name=_PLUGIN_NAMES, skills=st.lists(_SKILL_NAMES, min_size=1, max_size=3, unique=True))
    def test_add_then_force_add_equals_a_single_add(
        self, tmp_path: Path, name: str, skills: List[str]
    ) -> None:
        """A reinstall converges on the state a single install would produce.

        Compared within one environment so absolute paths match. Install records
        are excluded because ``installed_at`` legitimately advances on a
        reinstall; the record fields that must *not* change are asserted
        separately below.
        """
        env = _make_env(tmp_path)
        source = env.make_plugin(name, skills=tuple(skills))

        env.install(name, source_dir=source)
        after_single = _snapshot(env, include_records=False)
        record_single = env.store.get(name)

        env.install(name, source_dir=source, force=True)
        after_force = _snapshot(env, include_records=False)
        record_force = env.store.get(name)

        assert after_force == after_single
        assert record_single is not None and record_force is not None
        assert record_force.name == record_single.name
        assert record_force.version == record_single.version
        assert record_force.skill_names == record_single.skill_names
        assert record_force.projected_skill_names == record_single.projected_skill_names

    @FS_SETTINGS
    @given(name=_PLUGIN_NAMES, skills=st.lists(_SKILL_NAMES, min_size=1, max_size=3, unique=True))
    def test_add_then_remove_restores_the_prior_state(
        self, tmp_path: Path, name: str, skills: List[str]
    ) -> None:
        env = _make_env(tmp_path)
        before = _snapshot(env)

        env.install(name, skills=tuple(skills))
        env.uninstall(name)

        after = _snapshot(env)
        # The store's .state/ ledger legitimately exists afterwards; compare the
        # things the property is actually about.
        assert _plugin_dirs(env) == []
        assert env.skill_names() == []
        assert env.store.read_projection() == {}
        assert after["skills"] == before["skills"]

    @FS_SETTINGS
    @given(name=_PLUGIN_NAMES)
    def test_plugin_data_persists_across_remove_without_purge(
        self, tmp_path: Path, name: str
    ) -> None:
        env = _make_env(tmp_path)
        env.install(name)
        data = env.store.plugin_data_dir(name, create=True)
        (data / "state").write_text("kept", encoding="utf-8")

        env.uninstall(name)

        assert (data / "state").read_text(encoding="utf-8") == "kept"

    @FS_SETTINGS
    @given(name=_PLUGIN_NAMES)
    def test_plugin_data_is_deleted_with_purge(self, tmp_path: Path, name: str) -> None:
        env = _make_env(tmp_path)
        env.install(name)
        data = env.store.plugin_data_dir(name, create=True)
        (data / "state").write_text("doomed", encoding="utf-8")

        env.uninstall(name, purge_data=True)

        assert not data.exists()

    @FS_SETTINGS
    @given(name=_PLUGIN_NAMES, times=st.integers(min_value=2, max_value=4))
    def test_repeated_removal_is_idempotent(self, tmp_path: Path, name: str, times: int) -> None:
        env = _make_env(tmp_path)
        env.install(name, skills=("alpha",))

        for _ in range(times):
            env.uninstall(name)

        assert _plugin_dirs(env) == []
        assert env.skill_names() == []


def _plugin_dirs(env: ProjectionEnv) -> List[str]:
    """Installed plugin directory names (excluding CAO-owned state)."""
    if not env.store.plugins_dir.is_dir():
        return []
    return sorted(
        entry.name for entry in env.store.plugins_dir.iterdir() if not entry.name.startswith(".")
    )


# ---------------------------------------------------------------------------
# Property 6: Skills-only conformance
# ---------------------------------------------------------------------------


class TestSkillsOnlyConformance:
    """Property 6: Skills-only conformance.

    **Validates: Requirements 11.1, 11.5**
    """

    @FS_SETTINGS
    @given(
        name=_PLUGIN_NAMES,
        skills=st.lists(_SKILL_NAMES, min_size=1, max_size=4, unique=True),
    )
    def test_valid_skills_only_plugin_fully_loads_and_projects(
        self, tmp_path: Path, name: str, skills: List[str]
    ) -> None:
        env = _make_env(tmp_path)

        outcome = env.install(name, skills=tuple(skills))

        assert outcome.report.loadable is True
        assert outcome.report.mcp_present is False
        assert outcome.report.findings_with(Severity.FATAL) == ()
        assert sorted(outcome.report.skill_names) == sorted(skills)
        # Every skill is projected and reachable through the skill store.
        assert sorted(env.skill_names()) == sorted(skills)
        for skill in skills:
            assert (env.skills_dir / skill / "SKILL.md").is_file()

    @FS_SETTINGS
    @given(name=_PLUGIN_NAMES, skills=st.lists(_SKILL_NAMES, min_size=1, max_size=3, unique=True))
    def test_no_subprocess_is_ever_launched_for_a_plugin(
        self, tmp_path: Path, name: str, skills: List[str]
    ) -> None:
        """_Requirements: 11.3, 11.4 — Increment 1 launches nothing.

        ``git`` is legitimately invoked for a ``git`` source, so this uses a
        ``path`` source: for that kind, the install pipeline must run without
        spawning any process at all.
        """
        import subprocess

        env = _make_env(tmp_path)
        source = env.make_plugin(name, skills=tuple(skills))

        launched = []
        real_popen = subprocess.Popen

        class _Recorder(real_popen):  # type: ignore[misc,valid-type]
            def __init__(self, args, *rest, **kwargs):
                launched.append(args)
                super().__init__(args, *rest, **kwargs)

        subprocess.Popen = _Recorder  # type: ignore[misc]
        try:
            installer.install(
                PluginSource(kind="path", location=str(source)),
                store=env.store,
                skills_dir=env.skills_dir,
                refresh_agents=False,
            )
        finally:
            subprocess.Popen = real_popen  # type: ignore[misc]

        assert launched == []

    @FS_SETTINGS
    @given(name=_PLUGIN_NAMES, skills=st.lists(_SKILL_NAMES, min_size=1, max_size=3, unique=True))
    def test_mcp_json_does_not_prevent_skill_delivery(
        self, tmp_path: Path, name: str, skills: List[str]
    ) -> None:
        """_Requirements: 11.2 — reported as unsupported, skills unaffected._"""
        env = _make_env(tmp_path)
        source = make_plugin(
            env.sources / name,
            name,
            skills=tuple(skills),
            mcp={"mcpServers": {"s": {"type": "stdio", "command": "x"}}},
        )

        outcome = env.install(name, source_dir=source)

        assert outcome.report.loadable is True
        assert outcome.report.mcp_present is True
        assert outcome.report.mcp_servers == ()
        assert sorted(env.skill_names()) == sorted(skills)


# ---------------------------------------------------------------------------
# Property 8: Projection non-shadowing and deterministic collision winner
# ---------------------------------------------------------------------------

# Adversarial for scan/install order: names that differ only in the final
# character, so any rule keyed on something other than the name itself is likely
# to elect inconsistently.
_ADVERSARIAL_NAMES = st.one_of(
    st.lists(
        st.sampled_from(["plugin-a", "plugin-b", "plugin-c", "plugin-d"]),
        min_size=2,
        max_size=4,
        unique=True,
    ),
    st.lists(st.sampled_from(["aaa", "aab", "aac", "aad"]), min_size=2, max_size=4, unique=True),
    st.lists(_PLUGIN_NAMES, min_size=2, max_size=4, unique=True),
)


class TestProjectionNonShadowingAndDeterminism:
    """Property 8: Projection non-shadowing and deterministic collision winner.

    **Validates: Requirements 14.1, 14.2, 14.3, 14.4, 14.5**
    """

    @FS_SETTINGS
    @given(plugin=_PLUGIN_NAMES, skill=_SKILL_NAMES)
    def test_pre_existing_skill_is_never_shadowed(
        self, tmp_path: Path, plugin: str, skill: str
    ) -> None:
        env = _make_env(tmp_path)
        write_skill(env.skills_dir / skill, description="THE ORIGINAL")

        env.install(plugin, skills=(skill,))

        content = (env.skills_dir / skill / "SKILL.md").read_text(encoding="utf-8")
        assert "THE ORIGINAL" in content
        assert not (env.skills_dir / skill).is_symlink()
        assert provenance.owning_plugin(skill, env.store) is None

    @FS_SETTINGS
    @given(plugin=_PLUGIN_NAMES, skill=_SKILL_NAMES)
    def test_shadowing_attempt_is_reported(self, tmp_path: Path, plugin: str, skill: str) -> None:
        env = _make_env(tmp_path)
        write_skill(env.skills_dir / skill)

        outcome = env.install(plugin, skills=(skill,))

        assert any(f.code == "projection.preexisting_skill" for f in outcome.findings)

    @FS_SETTINGS
    @given(names=_ADVERSARIAL_NAMES, skill=_SKILL_NAMES)
    def test_lexicographically_smallest_plugin_wins(
        self, tmp_path: Path, names: List[str], skill: str
    ) -> None:
        env = _make_env(tmp_path)
        for name in names:
            env.install(name, skills=(skill,))

        assert provenance.owning_plugin(skill, env.store) == min(names)

    @FS_SETTINGS
    @given(names=_ADVERSARIAL_NAMES, skill=_SKILL_NAMES)
    def test_exactly_k_minus_one_losers_are_reported(
        self, tmp_path: Path, names: List[str], skill: str
    ) -> None:
        env = _make_env(tmp_path)
        for name in names:
            env.install(name, skills=(skill,))

        outcome = env.rebuild()

        collisions = [f for f in outcome.findings if f.code == "projection.plugin_collision"]
        assert len(collisions) == len(names) - 1

    @FS_SETTINGS
    @given(names=_ADVERSARIAL_NAMES, skill=_SKILL_NAMES)
    def test_winner_is_stable_across_repeated_rebuilds(
        self, tmp_path: Path, names: List[str], skill: str
    ) -> None:
        """_Requirements: 14.3_"""
        env = _make_env(tmp_path)
        for name in names:
            env.install(name, skills=(skill,))

        first = env.rebuild()
        second = env.rebuild()
        third = env.rebuild()

        assert first.projected == second.projected == third.projected
        assert provenance.owning_plugin(skill, env.store) == min(names)

    @FS_SETTINGS
    @given(names=_ADVERSARIAL_NAMES, skill=_SKILL_NAMES)
    def test_winner_is_invariant_under_install_order_permutation(
        self, tmp_path: Path, names: List[str], skill: str
    ) -> None:
        """_Requirements: 14.4 — the killer clause for an installed_at rule._"""
        expected = min(names)

        for order in itertools.permutations(names):
            env = _make_env(tmp_path)
            for name in order:
                env.install(name, skills=(skill,))

            assert (
                provenance.owning_plugin(skill, env.store) == expected
            ), f"install order {order} elected a different winner"

    @FS_SETTINGS
    @given(names=_ADVERSARIAL_NAMES, skill=_SKILL_NAMES)
    def test_creation_order_reverse_of_sort_order_still_elects_the_smallest(
        self, tmp_path: Path, names: List[str], skill: str
    ) -> None:
        env = _make_env(tmp_path)
        for name in sorted(names, reverse=True):
            env.install(name, skills=(skill,))

        assert provenance.owning_plugin(skill, env.store) == min(names)

    @FS_SETTINGS
    @given(names=_ADVERSARIAL_NAMES, skill=_SKILL_NAMES)
    def test_installing_an_earlier_claimant_warns_about_the_transition(
        self, tmp_path: Path, names: List[str], skill: str
    ) -> None:
        """The transition-warning clause of P8."""
        ordered = sorted(names)
        later, earlier = ordered[-1], ordered[0]
        assume(later != earlier)

        env = _make_env(tmp_path)
        env.install(later, skills=(skill,))
        before_winner = provenance.owning_plugin(skill, env.store)
        assert before_winner == later

        outcome = env.install(earlier, skills=(skill,))
        after_winner = provenance.owning_plugin(skill, env.store)

        assert after_winner == earlier
        transitions = [
            f
            for f in outcome.findings
            if f.severity is Severity.WARNING
            and f.code == "projection.winner_changed"
            and before_winner in f.message
            and after_winner in f.message
        ]
        assert transitions, "a changed content source must be announced"
        # And the loser still gets its own SKIPPED finding.
        assert any(f.code == "projection.plugin_collision" for f in outcome.findings)

    @FS_SETTINGS
    @given(names=_ADVERSARIAL_NAMES, skill=_SKILL_NAMES)
    def test_projection_is_a_function_of_the_installed_set_only(
        self, tmp_path: Path, names: List[str], skill: str
    ) -> None:
        """Two envs with the same installed set project identically."""
        first = _make_env(tmp_path)
        for name in names:
            first.install(name, skills=(skill,))

        second = _make_env(tmp_path)
        for name in reversed(names):
            second.install(name, skills=(skill,))

        assert first.store.read_projection() == second.store.read_projection()
