"""CAO's own Agent Plugins packages (W9).

_Requirements: 1.1-1.6, 2.1-2.8, 3.1-3.5, 11.5, 23.2_

The build script's configuration is imported *from the script* rather than
restated here, following ``test/test_skill_packaging_parity.py``: a drift guard
that keeps its own copy of the thing it guards is guarding nothing.

Both packages are asserted **independently** throughout, because Requirement 3.5
is precisely that one package's failure must not mask the other's — and the
contributor package is the one that would quietly rot.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

import pytest

from cli_agent_orchestrator.agent_plugins import schema_registry
from cli_agent_orchestrator.agent_plugins.models import Severity
from cli_agent_orchestrator.agent_plugins.validation import validate_plugin

REPO_ROOT = Path(__file__).resolve().parents[2]
BUILD_SCRIPT = REPO_ROOT / "scripts" / "build_agent_plugin.py"


def _load_build_script() -> ModuleType:
    """Import the build script by path (single source of truth).

    The module must be registered in ``sys.modules`` *before* execution:
    ``@dataclass`` resolves annotations through
    ``sys.modules[cls.__module__].__dict__``, which is ``None`` for a module
    loaded by path alone.
    """
    spec = importlib.util.spec_from_file_location("_build_agent_plugin", BUILD_SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


BUILD = _load_build_script()
PACKAGE_IDS = [config.name for config in BUILD.PACKAGES]


def _config(name: str):
    return next(config for config in BUILD.PACKAGES if config.name == name)


OPERATOR = _config("cao")
CONTRIBUTOR = _config("cao-contributor")


class TestBothPackagesExist:
    """_Requirements: 2.2 — the contributor package is genuinely separate._"""

    def test_container_holds_exactly_the_configured_packages(self) -> None:
        present = {entry.name for entry in BUILD.PACKAGES_DIR.iterdir() if entry.is_dir()}

        assert present == set(PACKAGE_IDS)

    def test_container_is_not_itself_a_plugin_root(self) -> None:
        """``agent-plugin/`` is a container; the plugin roots are its children."""
        assert not (BUILD.PACKAGES_DIR / "plugin.json").exists()

    def test_container_is_not_named_plugins(self) -> None:
        """Decision D7: ``plugins/`` already means the event-plugin system."""
        assert BUILD.PACKAGES_DIR.name == "agent-plugin"
        assert not (REPO_ROOT / "plugins").exists()

    def test_the_two_packages_are_distinct_roots(self) -> None:
        assert OPERATOR.root != CONTRIBUTOR.root
        assert OPERATOR.root.is_dir() and CONTRIBUTOR.root.is_dir()


class TestValidatorLoadsBothPackages:
    """_Requirements: 1.6, 3.4, 23.2 — both load with zero FATAL findings._"""

    @pytest.mark.parametrize("name", PACKAGE_IDS)
    def test_package_is_loadable(self, name: str) -> None:
        report = validate_plugin(_config(name).root)

        assert report.loadable is True, [f.message for f in report.findings]

    @pytest.mark.parametrize("name", PACKAGE_IDS)
    def test_package_has_no_fatal_findings(self, name: str) -> None:
        report = validate_plugin(_config(name).root)

        assert report.findings_with(Severity.FATAL) == ()

    @pytest.mark.parametrize("name", PACKAGE_IDS)
    def test_every_allowlisted_skill_is_discovered(self, name: str) -> None:
        config = _config(name)

        report = validate_plugin(config.root)

        for skill in config.skills:
            assert skill in report.skill_names

    def test_operator_package_discovers_session_management(self) -> None:
        """_Requirements: 1.6 — named explicitly by the requirement._"""
        report = validate_plugin(OPERATOR.root)

        assert "cao-session-management" in report.skill_names

    @pytest.mark.parametrize("name", PACKAGE_IDS)
    def test_package_reports_no_mcp(self, name: str) -> None:
        """_Requirements: 2.5, 11.5 — no mcp.json in Increment 1._"""
        report = validate_plugin(_config(name).root)

        assert report.mcp_present is False


class TestOperatorPackageContent:
    """_Requirements: 1.1-1.5_"""

    def test_manifest_declares_the_pinned_schema(self) -> None:
        manifest = json.loads((OPERATOR.root / "plugin.json").read_text(encoding="utf-8"))

        assert manifest["$schema"] == schema_registry.PLUGIN_SCHEMA_ID

    def test_name_is_cao(self) -> None:
        manifest = json.loads((OPERATOR.root / "plugin.json").read_text(encoding="utf-8"))

        assert manifest["name"] == "cao"

    def test_name_is_distinct_from_event_plugin_identifiers(self) -> None:
        """_Requirements: 1.1 — distinct from the event-plugin system._"""
        pyproject = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
        section = pyproject.split('[project.entry-points."cao.plugins"]', 1)
        assert len(section) == 2, "event-plugin entry-point section not found"
        entry_points = section[1].split("[", 1)[0]

        declared = {
            line.split("=", 1)[0].strip()
            for line in entry_points.splitlines()
            if "=" in line and not line.strip().startswith("#")
        }

        for name in PACKAGE_IDS:
            assert name not in declared, f"package name {name!r} collides with an event plugin"

    def test_includes_the_two_required_skills(self) -> None:
        """_Requirements: 1.2_"""
        packaged = {entry.name for entry in (OPERATOR.root / "skills").iterdir()}

        assert {"cao-session-management", "cao-agent-routing"} <= packaged

    def test_includes_the_protocol_skills_under_the_current_default(self) -> None:
        """_Requirements: 1.3 — maintainer-tunable, defaulting to inclusion._"""
        packaged = {entry.name for entry in (OPERATOR.root / "skills").iterdir()}

        assert {"cao-supervisor-protocols", "cao-worker-protocols"} <= packaged

    @pytest.mark.parametrize("excluded", ["cao-provider", "cao-plugin", "cao-event-plugin"])
    def test_excludes_contributor_facing_skills(self, excluded: str) -> None:
        """_Requirements: 1.4_"""
        assert not (OPERATOR.root / "skills" / excluded).exists()

    def test_excludes_vendored_ext_apps(self) -> None:
        """_Requirements: 1.4 — vendored content carries its own attribution._"""
        packaged = {entry.name for entry in (OPERATOR.root / "skills").iterdir()}

        assert "vendor" not in packaged
        for vendored in (
            "create-mcp-app",
            "add-app-to-server",
            "migrate-oai-app",
            "convert-web-app",
        ):
            assert vendored not in packaged

    def test_description_states_all_three_prerequisites(self) -> None:
        """_Requirements: 1.5 — uv on PATH, local API server, localhost-only._"""
        manifest = json.loads((OPERATOR.root / "plugin.json").read_text(encoding="utf-8"))
        description = manifest["description"]

        assert "uv" in description
        assert "PATH" in description
        assert "127.0.0.1:9889" in description
        assert "localhost-only" in description

    def test_declared_port_matches_the_real_default(self) -> None:
        """The stated prerequisite must be a fact, not a guess."""
        from cli_agent_orchestrator.constants import SERVER_HOST, SERVER_PORT

        manifest = json.loads((OPERATOR.root / "plugin.json").read_text(encoding="utf-8"))

        assert f"{SERVER_HOST}:{SERVER_PORT}" in manifest["description"]

    def test_ships_no_mcp_json_in_increment_1(self) -> None:
        """_Requirements: 11.5_"""
        assert not (OPERATOR.root / "mcp.json").exists()


class TestContributorPackageContent:
    """_Requirements: 2.1, 2.3-2.6, 2.8_"""

    def test_manifest_declares_the_pinned_schema(self) -> None:
        manifest = json.loads((CONTRIBUTOR.root / "plugin.json").read_text(encoding="utf-8"))

        assert manifest["$schema"] == schema_registry.PLUGIN_SCHEMA_ID

    def test_name_is_cao_contributor(self) -> None:
        """_Requirements: 2.8 — provisional pending M4, asserted as-is._"""
        manifest = json.loads((CONTRIBUTOR.root / "plugin.json").read_text(encoding="utf-8"))

        assert manifest["name"] == "cao-contributor"

    def test_includes_the_authoring_skills(self) -> None:
        """_Requirements: 2.3_"""
        packaged = {entry.name for entry in (CONTRIBUTOR.root / "skills").iterdir()}

        assert "cao-provider" in packaged
        assert BUILD.EVENT_PLUGIN_AUTHORING_SKILL in packaged

    @pytest.mark.parametrize(
        "operator_skill",
        [
            "cao-session-management",
            "cao-agent-routing",
            "cao-supervisor-protocols",
            "cao-worker-protocols",
        ],
    )
    def test_excludes_operator_facing_skills(self, operator_skill: str) -> None:
        """_Requirements: 2.4_"""
        assert not (CONTRIBUTOR.root / "skills" / operator_skill).exists()

    def test_ships_no_mcp_json_in_either_increment(self) -> None:
        """_Requirements: 2.5 — authoring skills need no CAO runtime._"""
        assert not (CONTRIBUTOR.root / "mcp.json").exists()

    def test_absence_of_cao_contributing_is_not_a_failure(self) -> None:
        """_Requirements: 2.6 — PR #448 is open and draft, so it is absent._"""
        assert "cao-contributing" not in CONTRIBUTOR.skills
        assert not (CONTRIBUTOR.root / "skills" / "cao-contributing").exists()

        # And the package still validates cleanly despite the omission.
        report = validate_plugin(CONTRIBUTOR.root)
        assert report.loadable is True
        assert report.findings_with(Severity.FATAL) == ()

    def test_the_skill_does_not_exist_upstream_yet(self) -> None:
        """Guards the claim above: if #448 lands, this fails and prompts the edit."""
        assert not (BUILD.CANONICAL_SKILLS_DIR / "cao-contributing").exists(), (
            "skills/cao-contributing now exists — PR #448 appears to have landed; "
            "add it to CONTRIBUTOR_PACKAGE.skills and rebuild (Requirement 2.7)"
        )

    def test_allowlist_is_plain_data_so_adding_a_skill_is_one_edit(self) -> None:
        """_Requirements: 2.7 — no structural change when #448 merges._"""
        assert isinstance(CONTRIBUTOR.skills, list)
        assert all(isinstance(entry, str) for entry in CONTRIBUTOR.skills)


class TestAllowlistsAreEnforcedIndependently:
    """_Requirements: 3.1, 3.5_"""

    @pytest.mark.parametrize("name", PACKAGE_IDS)
    def test_packaged_skills_equal_the_allowlist_exactly(self, name: str) -> None:
        config = _config(name)

        packaged = {entry.name for entry in (config.root / "skills").iterdir() if entry.is_dir()}

        assert packaged == set(config.skills)

    def test_the_two_allowlists_are_disjoint(self) -> None:
        """Each package's skills all serve one user story."""
        assert set(OPERATOR.skills).isdisjoint(set(CONTRIBUTOR.skills))

    def test_each_package_has_its_own_configuration(self) -> None:
        """_Requirements: 3.1 — name, manifest fields, and allowlist per package._"""
        assert OPERATOR.name != CONTRIBUTOR.name
        assert OPERATOR.description != CONTRIBUTOR.description
        assert OPERATOR.keywords != CONTRIBUTOR.keywords
        assert OPERATOR.skills != CONTRIBUTOR.skills

    def test_check_reports_a_failure_in_each_package_independently(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """The core of Requirement 3.5, exercised on a throwaway copy.

        Both packages are broken at once; the report must name both.
        """
        import shutil

        sandbox = tmp_path / "agent-plugin"
        shutil.copytree(BUILD.PACKAGES_DIR, sandbox, symlinks=True)
        # PackageConfig.root reads the module-level PACKAGES_DIR at call time,
        # so rebinding the module global is enough to relocate both packages.
        monkeypatch.setattr(BUILD, "PACKAGES_DIR", sandbox)
        assert OPERATOR.root == sandbox / "cao"

        # Break each package in a different way.
        (sandbox / "cao" / "skills" / "cao-agent-routing" / "SKILL.md").write_text(
            "tampered", encoding="utf-8"
        )
        shutil.rmtree(sandbox / "cao-contributor" / "skills" / "cao-provider")

        version = BUILD.cao_version()
        operator_problems = BUILD.check_package(OPERATOR, version)
        contributor_problems = BUILD.check_package(CONTRIBUTOR, version)

        assert operator_problems, "operator package drift not reported"
        assert contributor_problems, "contributor package drift not reported"


class TestVersionSync:
    """_Requirements: 3.2_"""

    @pytest.mark.parametrize("name", PACKAGE_IDS)
    def test_package_version_matches_cao_package_metadata(self, name: str) -> None:
        manifest = json.loads((_config(name).root / "plugin.json").read_text(encoding="utf-8"))

        assert manifest["version"] == BUILD.cao_version()

    def test_version_source_is_pyproject(self) -> None:
        pyproject = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")

        assert f'version = "{BUILD.cao_version()}"' in pyproject

    def test_both_packages_share_one_version(self) -> None:
        versions = {
            json.loads((_config(name).root / "plugin.json").read_text(encoding="utf-8"))["version"]
            for name in PACKAGE_IDS
        }

        assert len(versions) == 1


class TestDriftGuard:
    """_Requirements: 3.3, 3.4, 23.2 — the committed tree matches its source._"""

    def test_check_passes_on_the_committed_tree(self) -> None:
        assert BUILD.main(["--check"]) == 0

    @pytest.mark.parametrize("name", PACKAGE_IDS)
    def test_no_problems_reported_for_a_clean_package(self, name: str) -> None:
        assert BUILD.check_package(_config(name), BUILD.cao_version()) == []

    def test_packaged_skills_are_byte_identical_to_canonical(self) -> None:
        import filecmp

        for config in BUILD.PACKAGES:
            for skill in config.skills:
                source = BUILD.CANONICAL_SKILLS_DIR / skill
                packaged = config.root / "skills" / skill
                match, mismatch, errors = filecmp.cmpfiles(
                    source,
                    packaged,
                    [str(p.relative_to(source)) for p in source.rglob("*") if p.is_file()],
                    shallow=False,
                )
                assert mismatch == [], f"{config.name}/{skill}: {mismatch}"
                assert errors == [], f"{config.name}/{skill}: {errors}"

    def test_skills_are_copied_not_symlinked(self) -> None:
        """§4.1: a symlink into ../../skills/ escapes the root and must be rejected."""
        for config in BUILD.PACKAGES:
            for skill in config.skills:
                packaged = config.root / "skills" / skill
                assert not packaged.is_symlink(), f"{config.name}/{skill} is a symlink"
                assert not (packaged / "SKILL.md").is_symlink()

    def test_every_package_carries_a_license(self) -> None:
        for config in BUILD.PACKAGES:
            assert (config.root / "LICENSE").is_file()


class TestBuildScriptConstantsAgreeWithThePackage:
    """The script and the runtime must not disagree about the schema."""

    def test_schema_id_matches_the_registry(self) -> None:
        assert BUILD.PLUGIN_SCHEMA_ID == schema_registry.PLUGIN_SCHEMA_ID

    def test_canonical_skills_dir_is_the_repo_skills_tree(self) -> None:
        assert BUILD.CANONICAL_SKILLS_DIR == REPO_ROOT / "skills"

    def test_every_allowlisted_skill_exists_canonically(self) -> None:
        for config in BUILD.PACKAGES:
            for skill in config.skills:
                assert (
                    BUILD.CANONICAL_SKILLS_DIR / skill / "SKILL.md"
                ).is_file(), f"{config.name}: allowlist references missing skill {skill!r}"


class TestPackagesAreInstallable:
    """End to end: CAO can install its own packages from the working tree."""

    @pytest.mark.parametrize("name", PACKAGE_IDS)
    def test_package_installs_and_projects_its_skills(self, name: str, tmp_path: Path) -> None:
        from cli_agent_orchestrator.agent_plugins import installer
        from cli_agent_orchestrator.agent_plugins.models import PluginSource
        from cli_agent_orchestrator.agent_plugins.store import InstalledPluginStore

        config = _config(name)
        store = InstalledPluginStore(
            plugins_dir=tmp_path / "agent-plugins", data_dir=tmp_path / "data"
        )
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()

        outcome = installer.install(
            PluginSource(kind="path", location=str(config.root)),
            store=store,
            skills_dir=skills_dir,
            refresh_agents=False,
        )

        assert outcome.installed is True
        assert outcome.record is not None
        assert outcome.record.name == config.name
        assert sorted(outcome.projected_skill_names) == sorted(config.skills)

    def test_both_packages_can_be_installed_side_by_side(self, tmp_path: Path) -> None:
        """Disjoint allowlists mean no collision between CAO's own packages."""
        from cli_agent_orchestrator.agent_plugins import installer
        from cli_agent_orchestrator.agent_plugins.models import PluginSource
        from cli_agent_orchestrator.agent_plugins.store import InstalledPluginStore

        store = InstalledPluginStore(
            plugins_dir=tmp_path / "agent-plugins", data_dir=tmp_path / "data"
        )
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()

        for config in BUILD.PACKAGES:
            outcome = installer.install(
                PluginSource(kind="path", location=str(config.root)),
                store=store,
                skills_dir=skills_dir,
                refresh_agents=False,
            )
            assert outcome.installed is True
            assert not any(f.code == "projection.plugin_collision" for f in outcome.findings)

        expected = set(OPERATOR.skills) | set(CONTRIBUTOR.skills)
        assert {entry.name for entry in skills_dir.iterdir()} == expected

    def test_subdir_addressing_works_for_a_package(self, tmp_path: Path) -> None:
        """How a foreign client installs from a monorepo subdirectory."""
        from cli_agent_orchestrator.agent_plugins import installer
        from cli_agent_orchestrator.agent_plugins.models import PluginSource
        from cli_agent_orchestrator.agent_plugins.store import InstalledPluginStore

        store = InstalledPluginStore(
            plugins_dir=tmp_path / "agent-plugins", data_dir=tmp_path / "data"
        )
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()

        outcome = installer.install(
            PluginSource(kind="path", location=str(REPO_ROOT), subdir="agent-plugin/cao"),
            store=store,
            skills_dir=skills_dir,
            refresh_agents=False,
        )

        assert outcome.installed is True
        assert outcome.record is not None
        assert outcome.record.name == "cao"
