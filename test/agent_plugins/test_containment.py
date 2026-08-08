"""Unit tests for §4.1 path containment (W3).

_Requirements: 7.1, 7.2, 7.3, 7.4_
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from cli_agent_orchestrator.agent_plugins.containment import (
    is_within,
    realpath,
    resolve_relative_within_root,
    resolve_within_root,
)


@pytest.fixture
def root(tmp_path: Path) -> Path:
    """A plugin root with a small tree inside it."""
    root = tmp_path / "plugin"
    (root / "skills" / "alpha").mkdir(parents=True)
    (root / "skills" / "alpha" / "SKILL.md").write_text("x", encoding="utf-8")
    return root


@pytest.fixture
def outside(tmp_path: Path) -> Path:
    """A directory deliberately outside the plugin root."""
    target = tmp_path / "outside"
    target.mkdir()
    (target / "secret.txt").write_text("secret", encoding="utf-8")
    return target


class TestRealpath:
    def test_canonicalizes_an_existing_path(self, root: Path) -> None:
        assert realpath(root) == root.resolve()

    def test_canonicalizes_a_nonexistent_path(self, root: Path) -> None:
        """A path that does not exist still has a canonical location."""
        assert realpath(root / "absent") == (root / "absent").resolve()

    def test_collapses_dot_segments(self, root: Path) -> None:
        assert realpath(root / "skills" / ".." / "skills") == (root / "skills").resolve()

    def test_returns_none_for_a_nul_byte(self) -> None:
        assert realpath("/tmp/bad\x00path") is None

    def test_does_not_raise_on_a_symlink_loop(self, tmp_path: Path) -> None:
        """A loop must degrade to a value, never an exception."""
        first = tmp_path / "loop-a"
        second = tmp_path / "loop-b"
        first.symlink_to(second)
        second.symlink_to(first)

        realpath(first)  # must not raise


class TestIsWithin:
    def test_root_is_within_itself(self, tmp_path: Path) -> None:
        assert is_within(tmp_path, tmp_path)

    def test_child_is_within(self, tmp_path: Path) -> None:
        assert is_within(tmp_path, tmp_path / "child")

    def test_sibling_with_a_shared_prefix_is_not_within(self, tmp_path: Path) -> None:
        """``/plugins/ev`` must not contain ``/plugins/evil``."""
        base = tmp_path / "ev"
        sibling = tmp_path / "evil"

        assert not is_within(base, sibling)

    def test_parent_is_not_within(self, tmp_path: Path) -> None:
        assert not is_within(tmp_path / "child", tmp_path)


class TestResolveWithinRoot:
    """_Requirements: 7.1 — realpath canonicalization, not lexical inspection._"""

    def test_accepts_the_root_itself(self, root: Path) -> None:
        assert resolve_within_root(root, root) == root.resolve()

    def test_accepts_a_contained_path(self, root: Path) -> None:
        target = root / "skills" / "alpha"

        assert resolve_within_root(root, target) == target.resolve()

    def test_accepts_a_contained_path_reached_via_dot_dot(self, root: Path) -> None:
        """Lexical ``..`` is fine when it resolves back inside."""
        target = root / "skills" / ".." / "skills" / "alpha"

        assert resolve_within_root(root, target) == (root / "skills" / "alpha").resolve()

    def test_rejects_a_parent_escape(self, root: Path) -> None:
        assert resolve_within_root(root, root / ".." / "elsewhere") is None

    def test_rejects_an_absolute_path_outside(self, root: Path, outside: Path) -> None:
        assert resolve_within_root(root, outside) is None

    def test_rejects_a_sibling_sharing_a_name_prefix(self, tmp_path: Path) -> None:
        base = tmp_path / "plug"
        base.mkdir()
        sibling = tmp_path / "plugin-evil"
        sibling.mkdir()

        assert resolve_within_root(base, sibling) is None

    def test_returns_none_when_the_root_cannot_be_canonicalized(self) -> None:
        assert resolve_within_root("/bad\x00root", "/tmp") is None

    def test_never_raises_for_hostile_input(self, root: Path) -> None:
        for candidate in ["", "\x00", "../" * 200, "/" * 100, "~", "a" * 5000]:
            resolve_within_root(root, candidate)  # must not raise


class TestSymlinkContainment:
    """_Requirements: 7.3, 7.4 — links are judged by where they resolve._"""

    def test_accepts_a_symlink_resolving_inside(self, root: Path) -> None:
        link = root / "inside-link"
        link.symlink_to(root / "skills" / "alpha", target_is_directory=True)

        resolved = resolve_within_root(root, link)

        assert resolved == (root / "skills" / "alpha").resolve()

    def test_rejects_a_symlink_resolving_outside(self, root: Path, outside: Path) -> None:
        link = root / "escape-link"
        link.symlink_to(outside, target_is_directory=True)

        assert resolve_within_root(root, link) is None

    def test_rejects_a_file_symlink_resolving_outside(self, root: Path, outside: Path) -> None:
        link = root / "escape-file"
        link.symlink_to(outside / "secret.txt")

        assert resolve_within_root(root, link) is None

    def test_rejects_a_path_traversing_an_escaping_symlink(self, root: Path, outside: Path) -> None:
        """_Requirements: 7.4 — containment applies to paths introduced by links._

        The lexical path looks contained; only realpath reveals the escape.
        """
        link = root / "escape-dir"
        link.symlink_to(outside, target_is_directory=True)

        assert resolve_within_root(root, link / "secret.txt") is None

    def test_accepts_a_relative_symlink_resolving_inside(self, root: Path) -> None:
        link = root / "skills" / "beta"
        link.symlink_to("alpha")

        assert resolve_within_root(root, link) == (root / "skills" / "alpha").resolve()

    def test_rejects_a_relative_symlink_climbing_out(self, root: Path) -> None:
        link = root / "skills" / "climb"
        link.symlink_to(os.path.join("..", "..", ".."))

        assert resolve_within_root(root, link) is None

    def test_rejects_a_symlink_to_an_absolute_system_path(self, root: Path) -> None:
        link = root / "etc-link"
        link.symlink_to("/etc")

        assert resolve_within_root(root, link) is None


class TestResolveRelativeWithinRoot:
    """§4.1 rule 4: plugin-relative config values."""

    def test_resolves_a_dot_slash_value(self, root: Path) -> None:
        assert (
            resolve_relative_within_root(root, "./skills/alpha")
            == (root / "skills" / "alpha").resolve()
        )

    def test_resolves_a_bare_relative_value(self, root: Path) -> None:
        """Containment is enforced regardless of the ``./`` prefix."""
        assert (
            resolve_relative_within_root(root, "skills/alpha")
            == (root / "skills" / "alpha").resolve()
        )

    def test_collapses_dot_dot_that_stays_inside(self, root: Path) -> None:
        assert (
            resolve_relative_within_root(root, "./skills/../skills") == (root / "skills").resolve()
        )

    def test_rejects_an_escaping_relative_value(self, root: Path) -> None:
        assert resolve_relative_within_root(root, "./../escape") is None

    def test_rejects_an_absolute_value(self, root: Path) -> None:
        """Treating an absolute path as relative would silently change meaning."""
        assert resolve_relative_within_root(root, "/etc/passwd") is None

    @pytest.mark.parametrize("value", ["", None, 0, [], {}])
    def test_rejects_non_string_or_empty_values(self, root: Path, value: object) -> None:
        assert resolve_relative_within_root(root, value) is None  # type: ignore[arg-type]

    def test_rejects_a_value_traversing_an_escaping_symlink(
        self, root: Path, outside: Path
    ) -> None:
        (root / "escape-dir").symlink_to(outside, target_is_directory=True)

        assert resolve_relative_within_root(root, "./escape-dir/secret.txt") is None


class TestSiblingOfExistingHelper:
    """containment is a sibling of path_validation, not a replacement."""

    def test_path_validation_helper_still_exists_and_is_unmodified_in_shape(self) -> None:
        from cli_agent_orchestrator.utils.path_validation import safe_join_under_base

        # Still component-based and still str-in/str-out.
        result = safe_join_under_base("/tmp", "a", "b", description="test")
        assert isinstance(result, str)
