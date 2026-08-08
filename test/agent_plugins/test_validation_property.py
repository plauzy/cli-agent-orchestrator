"""Property-based tests for the validator and containment (W3).

Properties 1, 2, 3, and 7 from design.md. Each is a *correctness property*, not
a smoke test: the generators are deliberately adversarial, because the point of
a total validator is that it holds up against input nobody anticipated.

Filesystem-touching properties use ``deadline=None`` — materializing a directory
tree per example is legitimately slow and a per-example deadline would produce
flaky failures that say nothing about correctness.
"""

from __future__ import annotations

import itertools
import json
import os
import stat
from pathlib import Path
from typing import Any, Dict, List

import pytest
from hypothesis import HealthCheck, assume, given, settings
from hypothesis import strategies as st

from cli_agent_orchestrator.agent_plugins.containment import resolve_within_root
from cli_agent_orchestrator.agent_plugins.models import PluginValidationReport, Severity
from cli_agent_orchestrator.agent_plugins.validation import validate_plugin

from .conftest import SCHEMA_ID, make_manifest, make_plugin, write_skill

# Shared settings for properties that build real directory trees.
FS_SETTINGS = settings(
    max_examples=60,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow],
)

_counter = itertools.count()


def _fresh(base: Path) -> Path:
    """A unique subdirectory, so examples never collide inside one tmp_path."""
    target = base / f"case-{next(_counter)}"
    target.mkdir(parents=True)
    return target


# ---------------------------------------------------------------------------
# Property 1: Validation totality
# ---------------------------------------------------------------------------

# Names safe to use as filesystem entries while still being awkward.
_ENTRY_NAMES = st.sampled_from(
    [
        "skills",
        "mcp.json",
        "plugin.json",
        "SKILL.md",
        "a",
        ".hidden",
        "..dots",
        "-dash",
        "with space",
        "UPPER",
        "\u00e9\u00e8",
        "x" * 80,
    ]
)

_MANIFEST_BYTES = st.one_of(
    st.binary(max_size=400),
    st.text(max_size=200).map(lambda s: s.encode("utf-8", errors="ignore")),
    st.just(b""),
    st.just(b"\xff\xfe\x00binary"),
    st.just(b"{"),
    st.just(b"[]"),
    st.just(b"null"),
    st.just(b'{"$schema": 1}'),
    st.builds(
        lambda name: json.dumps({"$schema": SCHEMA_ID, "name": name}).encode("utf-8"),
        st.text(max_size=70),
    ),
    st.builds(
        lambda extra: json.dumps({**make_manifest("example"), "x": extra}).encode("utf-8"),
        st.recursive(
            st.none() | st.booleans() | st.integers() | st.text(max_size=20),
            lambda children: st.lists(children, max_size=3)
            | st.dictionaries(st.text(max_size=8), children, max_size=3),
            max_leaves=6,
        ),
    ),
)


@st.composite
def _hostile_tree(draw: Any) -> Dict[str, Any]:
    """A recipe for an adversarial candidate plugin directory."""
    return {
        "manifest_bytes": draw(st.one_of(st.none(), _MANIFEST_BYTES)),
        "manifest_is_dir": draw(st.booleans()),
        "skills_kind": draw(st.sampled_from(["absent", "dir", "file", "symlink-loop"])),
        "skill_dirs": draw(st.lists(_ENTRY_NAMES, max_size=4, unique=True)),
        "skill_md_kind": draw(st.sampled_from(["absent", "file", "dir", "empty", "binary"])),
        "mcp_kind": draw(st.sampled_from(["absent", "file", "dir", "empty"])),
        "nesting_depth": draw(st.integers(min_value=0, max_value=6)),
        "symlink_loop": draw(st.booleans()),
        "unreadable": draw(st.booleans()),
        "extra_entries": draw(st.lists(_ENTRY_NAMES, max_size=3, unique=True)),
    }


def _materialize(root: Path, recipe: Dict[str, Any]) -> None:
    """Build the tree described by ``recipe``. Best-effort by design."""
    # plugin.json
    if recipe["manifest_is_dir"]:
        (root / "plugin.json").mkdir(exist_ok=True)
    elif recipe["manifest_bytes"] is not None:
        (root / "plugin.json").write_bytes(recipe["manifest_bytes"])

    # skills/
    skills = root / "skills"
    kind = recipe["skills_kind"]
    if kind == "dir":
        skills.mkdir(exist_ok=True)
    elif kind == "file":
        skills.write_text("not a dir", encoding="utf-8")
    elif kind == "symlink-loop":
        try:
            skills.symlink_to(skills)
        except OSError:
            pass

    if skills.is_dir() and not skills.is_symlink():
        for name in recipe["skill_dirs"]:
            try:
                child = skills / name
                child.mkdir(exist_ok=True)
            except OSError:
                continue
            md = child / "SKILL.md"
            md_kind = recipe["skill_md_kind"]
            try:
                if md_kind == "file":
                    md.write_text(f"---\nname: {name}\ndescription: d\n---\n", encoding="utf-8")
                elif md_kind == "dir":
                    md.mkdir(exist_ok=True)
                elif md_kind == "empty":
                    md.write_bytes(b"")
                elif md_kind == "binary":
                    md.write_bytes(b"\xff\xfe\x00")
            except OSError:
                continue

    # mcp.json
    mcp = root / "mcp.json"
    mcp_kind = recipe["mcp_kind"]
    try:
        if mcp_kind == "file":
            mcp.write_text(json.dumps({"mcpServers": {}}), encoding="utf-8")
        elif mcp_kind == "dir":
            mcp.mkdir(exist_ok=True)
        elif mcp_kind == "empty":
            mcp.write_bytes(b"")
    except OSError:
        pass

    # arbitrary nesting
    deep = root
    for level in range(recipe["nesting_depth"]):
        deep = deep / f"level{level}"
        try:
            deep.mkdir(exist_ok=True)
        except OSError:
            break

    # a symlink loop somewhere in the tree
    if recipe["symlink_loop"]:
        try:
            first = root / "loop-a"
            second = root / "loop-b"
            first.symlink_to(second)
            second.symlink_to(first)
        except OSError:
            pass

    for name in recipe["extra_entries"]:
        try:
            (root / f"extra-{name}").write_bytes(b"")
        except OSError:
            continue

    # unreadable mode, applied last so it cannot block the rest of the build
    if recipe["unreadable"] and skills.is_dir() and not skills.is_symlink():
        try:
            os.chmod(skills, 0o000)
        except OSError:
            pass


class TestValidationTotality:
    """Property 1: Validation totality.

    **Validates: Requirements 5.1, 5.2, 5.3, 5.4**
    """

    @FS_SETTINGS
    @given(recipe=_hostile_tree())
    def test_never_raises_and_loadable_is_derived(
        self, tmp_path: Path, recipe: Dict[str, Any]
    ) -> None:
        root = _fresh(tmp_path)
        try:
            _materialize(root, recipe)

            report = validate_plugin(root)

            assert isinstance(report, PluginValidationReport)
            assert report.loadable == (
                not any(f.severity is Severity.FATAL for f in report.findings)
            )
        finally:
            # Restore permissions so pytest can clean up the tmp tree.
            for path in (root / "skills",):
                try:
                    if path.exists():
                        os.chmod(path, stat.S_IRWXU)
                except OSError:
                    pass

    @FS_SETTINGS
    @given(payload=_MANIFEST_BYTES)
    def test_arbitrary_manifest_bytes_never_raise(self, tmp_path: Path, payload: bytes) -> None:
        root = _fresh(tmp_path)
        (root / "plugin.json").write_bytes(payload)

        report = validate_plugin(root)

        assert isinstance(report, PluginValidationReport)

    @FS_SETTINGS
    @given(name=st.text(max_size=100))
    def test_arbitrary_plugin_names_never_raise(self, tmp_path: Path, name: str) -> None:
        root = _fresh(tmp_path)
        (root / "plugin.json").write_text(
            json.dumps({"$schema": SCHEMA_ID, "name": name}), encoding="utf-8"
        )

        report = validate_plugin(root)

        assert isinstance(report, PluginValidationReport)
        # A report is always internally consistent.
        assert report.loadable == (report.findings_with(Severity.FATAL) == ())

    @FS_SETTINGS
    @given(depth=st.integers(min_value=1, max_value=40))
    def test_deep_nesting_terminates(self, tmp_path: Path, depth: int) -> None:
        """_Requirements: 5.2 — bounded time; no recursive descent to exploit._"""
        root = _fresh(tmp_path)
        make_plugin(root, "example", skills=("alpha",))
        deep = root / "skills" / "alpha"
        for level in range(depth):
            deep = deep / f"d{level}"
        deep.mkdir(parents=True, exist_ok=True)
        write_skill(deep / "buried")

        report = validate_plugin(root)

        # Only the immediate child is a skill, regardless of depth (§7.1).
        assert report.skill_names == ("alpha",)

    def test_symlink_loop_at_the_root_does_not_hang(self, tmp_path: Path) -> None:
        root = _fresh(tmp_path)
        make_plugin(root, "example", skills=())
        (root / "skills").symlink_to(root / "skills")

        report = validate_plugin(root)

        assert isinstance(report, PluginValidationReport)

    def test_unreadable_skills_dir_is_reported_not_raised(self, tmp_path: Path) -> None:
        root = _fresh(tmp_path)
        make_plugin(root, "example", skills=("alpha",))
        skills = root / "skills"
        os.chmod(skills, 0o000)
        try:
            report = validate_plugin(root)

            assert isinstance(report, PluginValidationReport)
            # Either it read nothing or reported unreadable; never raised.
            assert report.loadable is True
        finally:
            os.chmod(skills, stat.S_IRWXU)


# ---------------------------------------------------------------------------
# Property 2: Fatality classification
# ---------------------------------------------------------------------------

_UNKNOWN_FIELD_NAMES = st.text(
    alphabet=st.characters(min_codepoint=97, max_codepoint=122), min_size=1, max_size=12
).filter(
    lambda name: name
    not in {
        "$schema",
        "name",
        "version",
        "description",
        "author",
        "homepage",
        "repository",
        "license",
        "keywords",
        "extensions",
    }
)

_NON_OBJECT_VALUES = st.one_of(
    st.text(max_size=10),
    st.integers(),
    st.booleans(),
    st.none(),
    st.lists(st.integers(), max_size=3),
)


class TestFatalityClassification:
    """Property 2: Fatality classification.

    **Validates: Requirements 6.1, 6.2, 6.3, 6.4**
    """

    @FS_SETTINGS
    @given(field=_UNKNOWN_FIELD_NAMES, value=_NON_OBJECT_VALUES)
    def test_unknown_top_level_field_is_non_fatal(
        self, tmp_path: Path, field: str, value: Any
    ) -> None:
        root = _fresh(tmp_path)
        make_plugin(root, "example", manifest=make_manifest("example", **{field: value}))

        report = validate_plugin(root)

        assert report.loadable is True
        assert any(f.code == "manifest.unknown_field" for f in report.findings)
        # Components still load.
        assert report.skill_names == ("example-skill",)

    @FS_SETTINGS
    @given(value=_NON_OBJECT_VALUES)
    def test_non_object_extensions_is_non_fatal(self, tmp_path: Path, value: Any) -> None:
        root = _fresh(tmp_path)
        make_plugin(root, "example", manifest=make_manifest("example", extensions=value))

        report = validate_plugin(root)

        assert report.loadable is True
        assert any(f.code == "manifest.extensions_not_object" for f in report.findings)
        assert report.skill_names == ("example-skill",)

    @FS_SETTINGS
    @given(
        namespace=st.text(
            alphabet=st.characters(min_codepoint=97, max_codepoint=122), min_size=1, max_size=10
        ),
        contents=st.recursive(
            st.none() | st.booleans() | st.integers() | st.text(max_size=10),
            lambda children: st.lists(children, max_size=3)
            | st.dictionaries(st.text(max_size=6), children, max_size=3),
            max_leaves=8,
        ),
    )
    def test_unimplemented_namespace_contents_are_never_validated(
        self, tmp_path: Path, namespace: str, contents: Any
    ) -> None:
        """_Requirements: 6.3 — ignored entirely, and no finding at all._"""
        root = _fresh(tmp_path)
        make_plugin(
            root,
            "example",
            manifest=make_manifest("example", extensions={f"com.{namespace}.client": contents}),
        )

        report = validate_plugin(root)

        assert report.loadable is True
        assert report.findings == ()

    @FS_SETTINGS
    @given(
        violation=st.sampled_from(
            [
                {"name": "example"},  # missing $schema
                {"$schema": SCHEMA_ID},  # missing name
                {"$schema": SCHEMA_ID, "name": "Bad Name"},
                {"$schema": SCHEMA_ID, "name": "double--dash"},
                {"$schema": SCHEMA_ID, "name": "dots..here"},
                {"$schema": SCHEMA_ID, "name": ""},
                {"$schema": SCHEMA_ID, "name": "x" * 65},
                {"$schema": "https://example.test/nope.json", "name": "example"},
                {"$schema": SCHEMA_ID, "name": "example", "version": 3},
                {"$schema": SCHEMA_ID, "name": "example", "keywords": "no"},
                {"$schema": SCHEMA_ID, "name": "example", "author": {"x": "y"}},
            ]
        )
    )
    def test_any_other_violation_is_fatal_with_zero_components(
        self, tmp_path: Path, violation: Dict[str, Any]
    ) -> None:
        root = _fresh(tmp_path)
        make_plugin(root, "example", manifest=violation, mcp={"mcpServers": {}})

        report = validate_plugin(root)

        assert report.loadable is False
        assert report.skills == ()
        assert report.mcp_servers == ()
        assert report.manifest is None

    @FS_SETTINGS
    @given(field=_UNKNOWN_FIELD_NAMES)
    def test_a_non_fatal_and_a_fatal_together_stay_fatal(self, tmp_path: Path, field: str) -> None:
        """The exceptions are exceptions, not a general amnesty."""
        root = _fresh(tmp_path)
        make_plugin(
            root,
            "example",
            manifest={"$schema": SCHEMA_ID, "name": "Bad Name", field: "v", "extensions": 5},
        )

        report = validate_plugin(root)

        assert report.loadable is False
        assert report.skills == ()


# ---------------------------------------------------------------------------
# Property 3: Containment
# ---------------------------------------------------------------------------


class TestContainment:
    """Property 3: Containment.

    **Validates: Requirements 7.1, 7.2, 7.3, 7.4**
    """

    @FS_SETTINGS
    @given(
        segments=st.lists(
            st.sampled_from(["..", ".", "a", "b", "skills", "x" * 20]), min_size=1, max_size=8
        )
    )
    def test_resolved_paths_are_always_inside_or_rejected(
        self, tmp_path: Path, segments: List[str]
    ) -> None:
        root = _fresh(tmp_path)
        (root / "a" / "b").mkdir(parents=True)
        candidate = root.joinpath(*segments)

        resolved = resolve_within_root(root, candidate)

        if resolved is not None:
            real_root = os.path.realpath(root)
            real = os.path.realpath(resolved)
            assert real == real_root or real.startswith(real_root + os.sep)

    @FS_SETTINGS
    @given(depth=st.integers(min_value=1, max_value=12))
    def test_dot_dot_escapes_are_rejected(self, tmp_path: Path, depth: int) -> None:
        root = _fresh(tmp_path)
        candidate = root.joinpath(*([".."] * depth), "escaped")

        assert resolve_within_root(root, candidate) is None

    @FS_SETTINGS
    @given(absolute=st.sampled_from(["/etc", "/etc/passwd", "/", "/tmp", "/usr/bin"]))
    def test_absolute_paths_outside_are_rejected(self, tmp_path: Path, absolute: str) -> None:
        root = _fresh(tmp_path)

        assert resolve_within_root(root, absolute) is None

    @FS_SETTINGS
    @given(link_name=st.sampled_from(["l1", "l2", "inner-link", "deep.link"]))
    def test_symlink_pointing_inside_is_accepted(self, tmp_path: Path, link_name: str) -> None:
        """§4.1 explicitly permits these."""
        root = _fresh(tmp_path)
        target = root / "real"
        target.mkdir()
        link = root / link_name
        link.symlink_to(target, target_is_directory=True)

        assert resolve_within_root(root, link) == target.resolve()

    @FS_SETTINGS
    @given(link_name=st.sampled_from(["out1", "out2", "escape", "sneaky.link"]))
    def test_symlink_pointing_outside_is_rejected(self, tmp_path: Path, link_name: str) -> None:
        root = _fresh(tmp_path)
        outside = root.parent / f"outside-{link_name}"
        outside.mkdir(exist_ok=True)
        link = root / link_name
        link.symlink_to(outside, target_is_directory=True)

        assert resolve_within_root(root, link) is None

    @FS_SETTINGS
    @given(escaping=st.booleans(), extra=st.sampled_from(["", "child", "a/b"]))
    def test_discovered_skill_directories_are_always_contained(
        self, tmp_path: Path, escaping: bool, extra: str
    ) -> None:
        """Every DiscoveredSkill.directory satisfies containment, always."""
        root = _fresh(tmp_path)
        make_plugin(root, "example", skills=("alpha",))

        if escaping:
            outside = root.parent / f"outside-{root.name}"
            write_skill(outside / "sneaky")
            (root / "skills" / "sneaky").symlink_to(outside / "sneaky", target_is_directory=True)

        report = validate_plugin(root)

        real_root = os.path.realpath(report.root)
        for skill in report.skills:
            real = os.path.realpath(skill.directory)
            assert real == real_root or real.startswith(real_root + os.sep)
        if escaping:
            assert "sneaky" not in report.skill_names


# ---------------------------------------------------------------------------
# Property 7: Sibling independence
# ---------------------------------------------------------------------------

_SKILL_NAMES = st.text(
    alphabet=st.characters(min_codepoint=97, max_codepoint=122), min_size=3, max_size=10
)


class TestSiblingIndependence:
    """Property 7: Sibling independence.

    **Validates: Requirements 12.1, 12.2**
    """

    @FS_SETTINGS
    @given(
        valid=st.lists(_SKILL_NAMES, min_size=0, max_size=5, unique=True),
        invalid=st.lists(_SKILL_NAMES, min_size=0, max_size=5, unique=True),
    )
    def test_exactly_n_minus_k_discovered_and_k_skipped(
        self, tmp_path: Path, valid: List[str], invalid: List[str]
    ) -> None:
        # Disjoint names, or a "valid" and "invalid" would collide on one dir.
        invalid = [name for name in invalid if name not in valid]
        assume(len(valid) + len(invalid) > 0)

        root = _fresh(tmp_path)
        make_plugin(root, "example", skills=())
        (root / "skills").mkdir(exist_ok=True)
        for name in valid:
            write_skill(root / "skills" / name)
        for name in invalid:
            # Frontmatter name deliberately disagrees with the folder name.
            write_skill(root / "skills" / name, name=f"{name}-mismatch")

        report = validate_plugin(root)

        assert sorted(report.skill_names) == sorted(valid)
        skipped = [f for f in report.findings if f.code == "skill.invalid"]
        assert len(skipped) == len(invalid)
        assert report.loadable is True

    @FS_SETTINGS
    @given(names=st.lists(_SKILL_NAMES, min_size=2, max_size=6, unique=True))
    def test_discovered_set_is_independent_of_creation_order(
        self, tmp_path: Path, names: List[str]
    ) -> None:
        """_Requirements: 12.2 — independent of on-disk enumeration order._

        Two trees with the same skills created in opposite orders must yield
        the same discovered set. Creation order is what drives raw
        ``os.scandir`` order on many filesystems, so this is the observable
        proxy for "not dependent on iteration order".
        """
        forward = _fresh(tmp_path)
        make_plugin(forward, "example", skills=())
        (forward / "skills").mkdir(exist_ok=True)
        for name in names:
            write_skill(forward / "skills" / name)

        backward = _fresh(tmp_path)
        make_plugin(backward, "example", skills=())
        (backward / "skills").mkdir(exist_ok=True)
        for name in reversed(names):
            write_skill(backward / "skills" / name)

        first = validate_plugin(forward)
        second = validate_plugin(backward)

        assert sorted(first.skill_names) == sorted(second.skill_names)
        # Sorted discovery additionally makes the ORDER reproducible.
        assert first.skill_names == second.skill_names

    @FS_SETTINGS
    @given(count=st.integers(min_value=1, max_value=6))
    def test_one_invalid_skill_never_affects_its_siblings(self, tmp_path: Path, count: int) -> None:
        root = _fresh(tmp_path)
        expected = [f"good{index}" for index in range(count)]
        make_plugin(root, "example", skills=tuple(expected))
        write_skill(root / "skills" / "poison", name="not-poison")

        report = validate_plugin(root)

        assert sorted(report.skill_names) == sorted(expected)

    @FS_SETTINGS
    @given(names=st.lists(_SKILL_NAMES, min_size=1, max_size=4, unique=True))
    def test_repeated_validation_is_stable(self, tmp_path: Path, names: List[str]) -> None:
        """Validation is a pure function of the tree."""
        root = _fresh(tmp_path)
        make_plugin(root, "example", skills=tuple(names))

        first = validate_plugin(root)
        second = validate_plugin(root)

        assert first.skill_names == second.skill_names
        assert [f.code for f in first.findings] == [f.code for f in second.findings]
