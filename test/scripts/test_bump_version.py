"""Tests for scripts/bump_version.py.

The bumper is small but version-string parsing is exactly the kind of
code where regex edge cases bite later. We pin the PEP 440 grammar
behavior in tests so future commits can't silently regress.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

# Load the bump_version module by path so we don't depend on it being
# importable as `scripts.bump_version` (it's a top-level utility).
_SPEC = importlib.util.spec_from_file_location(
    "bump_version",
    Path(__file__).resolve().parents[2] / "scripts" / "bump_version.py",
)
assert _SPEC and _SPEC.loader
bump_version = importlib.util.module_from_spec(_SPEC)
sys.modules["bump_version"] = bump_version
_SPEC.loader.exec_module(bump_version)


class TestStableVersionBumps:
    """The classic semver bumps from a non-prerelease starting point."""

    def test_patch(self) -> None:
        assert bump_version.bump("patch", "2.5.0") == "2.5.1"

    def test_minor(self) -> None:
        assert bump_version.bump("minor", "2.5.7") == "2.6.0"

    def test_major(self) -> None:
        assert bump_version.bump("major", "2.5.7") == "3.0.0"


class TestPrereleaseFromStable:
    """Adding the first prerelease tag to a stable version."""

    def test_prerelease_appends_a1(self) -> None:
        assert bump_version.bump("prerelease", "2.5.0") == "2.5.0a1"

    def test_prerelease_appends_a1_to_patch_release(self) -> None:
        assert bump_version.bump("prerelease", "2.5.3") == "2.5.3a1"


class TestPrereleaseBumps:
    """Incrementing the prerelease integer within the same kind."""

    def test_alpha_increment(self) -> None:
        assert bump_version.bump("prerelease", "2.5.0a2") == "2.5.0a3"

    def test_alpha_increment_past_nine(self) -> None:
        # No leading-zero shenanigans; pure integer increment.
        assert bump_version.bump("prerelease", "2.5.0a9") == "2.5.0a10"

    def test_beta_increment(self) -> None:
        assert bump_version.bump("prerelease", "2.5.0b1") == "2.5.0b2"

    def test_rc_increment(self) -> None:
        assert bump_version.bump("prerelease", "2.5.0rc4") == "2.5.0rc5"


class TestGraduationFromPrereleaseToFinal:
    """Bumping patch/minor/major from a prerelease drops the suffix
    (PyPA convention — graduates the alpha to the final at that level).
    """

    def test_patch_from_alpha_graduates_to_final_at_same_triplet(self) -> None:
        # 2.5.0a2 → patch → 2.5.0 (NOT 2.5.1) — graduates the alpha
        # to the final release at the current triplet.
        assert bump_version.bump("patch", "2.5.0a2") == "2.5.0"

    def test_minor_from_alpha_drops_suffix_and_bumps_minor(self) -> None:
        # 2.5.0a2 → minor → 2.6.0
        assert bump_version.bump("minor", "2.5.0a2") == "2.6.0"

    def test_major_from_alpha_drops_suffix_and_bumps_major(self) -> None:
        # 2.5.0a2 → major → 3.0.0
        assert bump_version.bump("major", "2.5.0a2") == "3.0.0"

    def test_patch_from_rc_graduates(self) -> None:
        assert bump_version.bump("patch", "2.5.7rc3") == "2.5.7"


class TestErrorPaths:
    def test_unknown_bump_mode_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown bump mode"):
            bump_version.bump("frobnicate", "2.5.0")

    def test_unparseable_version_raises(self) -> None:
        with pytest.raises(ValueError, match="Unrecognized version"):
            bump_version.bump("patch", "not-a-version")

    def test_dev_build_metadata_rejected(self) -> None:
        # We intentionally don't support .devN / +localN — keeps the
        # bumper aligned with the simple case CAO actually ships.
        with pytest.raises(ValueError, match="Unrecognized version"):
            bump_version.bump("prerelease", "2.5.0a2.dev1")


class TestBumpModes:
    def test_bump_modes_includes_prerelease(self) -> None:
        assert "prerelease" in bump_version.BUMP_MODES
        # Existing modes preserved.
        for mode in ("major", "minor", "patch"):
            assert mode in bump_version.BUMP_MODES


class TestUpdatePyproject:
    """Pin the substitution to the project's `version` line only.

    Earlier versions used `re.sub(r'version = "[^"]+"', ...)` without
    a line anchor, which also matched `python_version = "..."` under
    [tool.mypy] and corrupted it (e.g. produced "2.1.1" / "2.5.0a4"
    in the mypy section). The fix anchors to start-of-line.
    """

    def test_does_not_rewrite_mypy_python_version(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(
            "[project]\n"
            'name = "cli-agent-orchestrator"\n'
            'version = "2.5.0a3"\n'
            "\n"
            "[tool.mypy]\n"
            'python_version = "3.10"\n'
            "strict = true\n"
        )
        monkeypatch.setattr(bump_version, "PYPROJECT", pyproject)

        bump_version.update_pyproject("2.5.0a4")

        result = pyproject.read_text()
        assert 'version = "2.5.0a4"' in result
        assert 'python_version = "3.10"' in result
        assert 'python_version = "2.5.0a4"' not in result
