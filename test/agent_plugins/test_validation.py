"""Unit tests and the conformance corpus for the total validator (W3).

_Requirements: 5.1, 5.2, 5.3, 6.1, 6.2, 6.3, 6.4, 11.1, 11.2, 12.1, 12.2,
12.3, 12.4, 23.3, 23.4_

The corpus in ``TestConformanceCorpus`` is the artifact that makes conformance
*reviewable* rather than asserted: one case per row of design.md's
failure-isolation table, each pinning the exact finding code and the
specification clause it cites.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional, Tuple

import pytest

from cli_agent_orchestrator.agent_plugins.models import Severity
from cli_agent_orchestrator.agent_plugins.validation import validate_plugin

from .conftest import SCHEMA_ID, make_manifest, make_plugin, write_skill

# The upstream canonical example package, vendored into the workspace as a
# sibling checkout. Used as the known-good positive fixture (Requirement 23.4).
CANONICAL_EXAMPLE = Path("/projects/sandbox/agent-plugins-example")


def codes(report) -> list:
    """Finding codes in report order, for concise assertions."""
    return [finding.code for finding in report.findings]


def find(report, code: str):
    """The first finding with ``code``, or ``None``."""
    return next((f for f in report.findings if f.code == code), None)


class TestValidPlugin:
    """The happy path, and Requirement 11.1's skills-only conformance."""

    def test_minimal_valid_plugin_is_loadable(self, plugin_factory) -> None:
        report = validate_plugin(plugin_factory("example"))

        assert report.loadable is True
        assert report.manifest is not None
        assert report.manifest.name == "example"
        assert report.skill_names == ("example-skill",)
        assert report.mcp_present is False
        assert report.findings == ()

    def test_all_metadata_fields_round_trip(self, tmp_path: Path) -> None:
        manifest = make_manifest(
            "example",
            description="A plugin.",
            author={"name": "A", "email": "a@example.test", "url": "https://example.test"},
            homepage="https://example.test",
            repository="https://example.test/repo",
            license="MIT",
            keywords=["one", "two"],
        )
        root = make_plugin(tmp_path / "p", "example", manifest=manifest)

        report = validate_plugin(root)

        assert report.loadable is True
        assert report.manifest is not None
        assert report.manifest.description == "A plugin."
        assert report.manifest.author is not None
        assert report.manifest.author.email == "a@example.test"
        assert report.manifest.license == "MIT"
        assert report.manifest.keywords == ("one", "two")

    def test_plugin_with_no_components_is_still_loadable(self, tmp_path: Path) -> None:
        """§6.2: absent fixed locations are not errors."""
        root = make_plugin(tmp_path / "p", "example", skills=())

        report = validate_plugin(root)

        assert report.loadable is True
        assert report.skills == ()
        assert report.findings == ()

    def test_multiple_skills_all_discovered(self, tmp_path: Path) -> None:
        root = make_plugin(tmp_path / "p", "example", skills=("alpha", "beta", "gamma"))

        report = validate_plugin(root)

        assert sorted(report.skill_names) == ["alpha", "beta", "gamma"]

    def test_extra_package_files_are_ignored(self, tmp_path: Path) -> None:
        """LICENSE, CHANGELOG, extension dirs: none of CAO's business."""
        root = make_plugin(tmp_path / "p", "example")
        (root / "LICENSE").write_text("MIT", encoding="utf-8")
        (root / "CHANGELOG.md").write_text("# Changes", encoding="utf-8")
        (root / "com.example.client").mkdir()

        report = validate_plugin(root)

        assert report.loadable is True
        assert report.findings == ()


class TestManifestFatality:
    """_Requirements: 6.4 — any non-excepted violation is fatal, zero components._"""

    def test_missing_manifest_is_fatal(self, tmp_path: Path) -> None:
        root = tmp_path / "p"
        write_skill(root / "skills" / "alpha")

        report = validate_plugin(root)

        assert report.loadable is False
        assert find(report, "manifest.missing") is not None
        assert report.skills == ()  # zero components discovered

    def test_invalid_json_is_fatal(self, tmp_path: Path) -> None:
        root = make_plugin(tmp_path / "p", "example", raw_manifest="{not json")

        report = validate_plugin(root)

        assert report.loadable is False
        assert find(report, "manifest.invalid_json") is not None
        assert report.skills == ()

    @pytest.mark.parametrize("body", ["[]", '"a string"', "42", "null", "true"])
    def test_non_object_manifest_is_fatal(self, tmp_path: Path, body: str) -> None:
        root = make_plugin(tmp_path / "p", "example", raw_manifest=body)

        report = validate_plugin(root)

        assert report.loadable is False
        assert find(report, "manifest.not_an_object") is not None

    def test_empty_file_is_fatal(self, tmp_path: Path) -> None:
        root = make_plugin(tmp_path / "p", "example", raw_manifest="")

        report = validate_plugin(root)

        assert report.loadable is False
        assert find(report, "manifest.invalid_json") is not None

    def test_missing_schema_is_fatal(self, tmp_path: Path) -> None:
        root = make_plugin(tmp_path / "p", "example", manifest={"name": "example"})

        report = validate_plugin(root)

        assert report.loadable is False
        assert find(report, "manifest.unsupported_schema") is not None

    def test_unrecognized_schema_is_fatal(self, tmp_path: Path) -> None:
        """_Requirements: 4.5 — an unknown $schema is rejected, never fetched._"""
        root = make_plugin(
            tmp_path / "p",
            "example",
            manifest={
                "$schema": "https://agent-plugins.org/schemas/9.9.9/plugin.schema.json",
                "name": "example",
            },
        )

        report = validate_plugin(root)

        assert report.loadable is False
        finding = find(report, "manifest.unsupported_schema")
        assert finding is not None
        assert finding.spec_ref == "§5.2"
        assert "9.9.9" in finding.message

    def test_missing_name_is_fatal(self, tmp_path: Path) -> None:
        root = make_plugin(tmp_path / "p", "example", manifest={"$schema": SCHEMA_ID})

        report = validate_plugin(root)

        assert report.loadable is False
        assert find(report, "manifest.schema_violation") is not None
        assert report.skills == ()

    @pytest.mark.parametrize(
        "name",
        [
            "UPPERCASE",
            "has space",
            "under_score",
            "-leading-dash",
            "trailing-dash-",
            "double--dash",
            "dot..dot",
            ".leading-dot",
            "trailing-dot.",
            "",
            "a" * 65,
            "emoji-\U0001f600",
        ],
    )
    def test_name_violating_5_5_constraints_is_fatal(self, tmp_path: Path, name: str) -> None:
        """§5.5 name constraints, enforced by the pinned schema's pattern."""
        root = make_plugin(tmp_path / "p", "example", manifest={"$schema": SCHEMA_ID, "name": name})

        report = validate_plugin(root)

        assert report.loadable is False, f"expected {name!r} to be rejected"
        assert find(report, "manifest.schema_violation") is not None

    @pytest.mark.parametrize("name", ["a", "ab", "a-b", "a.b", "a1", "1a", "a" * 64, "x-y.z-9"])
    def test_names_satisfying_5_5_are_accepted(self, tmp_path: Path, name: str) -> None:
        root = make_plugin(
            tmp_path / "p", "example", manifest={"$schema": SCHEMA_ID, "name": name}, skills=()
        )

        report = validate_plugin(root)

        assert report.loadable is True, f"expected {name!r} to be accepted"

    @pytest.mark.parametrize(
        "field,value",
        [
            ("version", 1),
            ("description", []),
            ("license", {}),
            ("keywords", "not-a-list"),
            ("keywords", [1, 2]),
            ("author", "not-an-object"),
            ("homepage", 5),
        ],
    )
    def test_wrong_field_type_is_fatal(self, tmp_path: Path, field: str, value: object) -> None:
        root = make_plugin(
            tmp_path / "p", "example", manifest=make_manifest("example", **{field: value})
        )

        report = validate_plugin(root)

        assert report.loadable is False
        assert find(report, "manifest.schema_violation") is not None

    def test_unknown_author_member_is_fatal(self, tmp_path: Path) -> None:
        """``author`` is closed by the schema (§5.4)."""
        root = make_plugin(
            tmp_path / "p",
            "example",
            manifest=make_manifest("example", author={"name": "A", "twitter": "@a"}),
        )

        report = validate_plugin(root)

        assert report.loadable is False

    def test_oversized_manifest_is_fatal_not_a_hang(self, tmp_path: Path) -> None:
        padding = "x" * (2 * 1024 * 1024)
        root = make_plugin(tmp_path / "p", "example", raw_manifest=json.dumps({"pad": padding}))

        report = validate_plugin(root)

        assert report.loadable is False
        assert find(report, "manifest.too_large") is not None

    def test_non_utf8_manifest_is_fatal(self, tmp_path: Path) -> None:
        root = tmp_path / "p"
        root.mkdir()
        (root / "plugin.json").write_bytes(b"\xff\xfe not utf-8 at all")

        report = validate_plugin(root)

        assert report.loadable is False
        assert find(report, "manifest.not_utf8") is not None

    def test_manifest_as_a_directory_is_fatal(self, tmp_path: Path) -> None:
        root = tmp_path / "p"
        (root / "plugin.json").mkdir(parents=True)

        report = validate_plugin(root)

        assert report.loadable is False
        assert find(report, "manifest.missing") is not None

    def test_nonexistent_root_is_fatal(self, tmp_path: Path) -> None:
        report = validate_plugin(tmp_path / "absent")

        assert report.loadable is False
        assert find(report, "plugin.root_not_a_directory") is not None

    def test_file_as_root_is_fatal(self, tmp_path: Path) -> None:
        target = tmp_path / "afile"
        target.write_text("x", encoding="utf-8")

        report = validate_plugin(target)

        assert report.loadable is False
        assert find(report, "plugin.root_not_a_directory") is not None


class TestNonFatalExceptions:
    """The only two tolerated manifest problems (§5.2, §8.1)."""

    def test_unknown_top_level_field_is_a_warning(self, tmp_path: Path) -> None:
        """_Requirements: 6.1 — report, ignore, keep loading._"""
        root = make_plugin(
            tmp_path / "p", "example", manifest=make_manifest("example", surprise="value")
        )

        report = validate_plugin(root)

        assert report.loadable is True
        finding = find(report, "manifest.unknown_field")
        assert finding is not None
        assert finding.severity is Severity.WARNING
        assert finding.spec_ref == "§5.2"
        assert "surprise" in finding.message
        # The plugin still loads its components.
        assert report.skill_names == ("example-skill",)

    def test_multiple_unknown_fields_each_reported(self, tmp_path: Path) -> None:
        root = make_plugin(
            tmp_path / "p",
            "example",
            manifest=make_manifest("example", alpha=1, beta=2, gamma=3),
        )

        report = validate_plugin(root)

        assert report.loadable is True
        unknown = [f for f in report.findings if f.code == "manifest.unknown_field"]
        assert len(unknown) == 3

    @pytest.mark.parametrize("value", ["a string", 5, [], True, None])
    def test_non_object_extensions_is_a_warning(self, tmp_path: Path, value: object) -> None:
        """_Requirements: 6.2 — report, ignore, keep loading._"""
        root = make_plugin(
            tmp_path / "p", "example", manifest=make_manifest("example", extensions=value)
        )

        report = validate_plugin(root)

        assert report.loadable is True
        finding = find(report, "manifest.extensions_not_object")
        assert finding is not None
        assert finding.severity is Severity.WARNING
        assert finding.spec_ref == "§8.1"
        assert report.skill_names == ("example-skill",)

    def test_unimplemented_extension_namespace_produces_no_finding(self, tmp_path: Path) -> None:
        """_Requirements: 6.3 — ignored entirely, contents never validated._"""
        root = make_plugin(
            tmp_path / "p",
            "example",
            manifest=make_manifest("example", extensions={"com.example.client": {"setting": True}}),
        )

        report = validate_plugin(root)

        assert report.loadable is True
        assert report.findings == ()  # not even an informational finding

    def test_extension_namespace_contents_are_not_validated(self, tmp_path: Path) -> None:
        """§8.1 forbids validating the contents of an unimplemented namespace.

        The pinned schema constrains namespace values to objects, so a
        non-object value here would be a schema violation if ``extensions``
        were passed through to the validator. It must not be.
        """
        root = make_plugin(
            tmp_path / "p",
            "example",
            manifest=make_manifest(
                "example",
                extensions={"com.example.client": "not an object at all"},
            ),
        )

        report = validate_plugin(root)

        assert report.loadable is True
        assert report.findings == ()

    def test_deeply_nested_extension_contents_are_not_validated(self, tmp_path: Path) -> None:
        root = make_plugin(
            tmp_path / "p",
            "example",
            manifest=make_manifest(
                "example",
                extensions={"com.example.client": {"deep": {"nested": [1, 2, {"x": None}]}}},
            ),
        )

        report = validate_plugin(root)

        assert report.loadable is True
        assert report.findings == ()

    def test_manifest_view_does_not_expose_extensions(self, tmp_path: Path) -> None:
        """Not modelling it is what stops it being validated later."""
        root = make_plugin(
            tmp_path / "p",
            "example",
            manifest=make_manifest("example", extensions={"com.example.client": {}}),
        )

        report = validate_plugin(root)

        assert report.manifest is not None
        assert not hasattr(report.manifest, "extensions")


class TestSkillDiscovery:
    """§7.1 / §6.2 discovery rules."""

    def test_missing_skills_dir_is_not_an_error(self, tmp_path: Path) -> None:
        """_Requirements: 12.4_"""
        root = make_plugin(tmp_path / "p", "example", skills=())

        report = validate_plugin(root)

        assert report.loadable is True
        assert report.skills == ()
        assert report.findings == ()

    def test_skills_as_a_file_invalidates_only_skills(self, tmp_path: Path) -> None:
        """_Requirements: 12.3 — MCP discovery is unaffected._"""
        root = make_plugin(tmp_path / "p", "example", skills=(), mcp={"mcpServers": {}})
        (root / "skills").write_text("not a directory", encoding="utf-8")

        report = validate_plugin(root)

        assert report.loadable is True
        finding = find(report, "skills.not_a_directory")
        assert finding is not None
        assert finding.severity is Severity.SKIPPED
        assert finding.spec_ref == "§6.2"
        # MCP was still discovered.
        assert report.mcp_present is True

    def test_no_recursive_descent(self, tmp_path: Path) -> None:
        """§7.1: clients MUST NOT search deeper descendants."""
        root = make_plugin(tmp_path / "p", "example", skills=("alpha",))
        write_skill(root / "skills" / "alpha" / "nested" / "deep-skill")

        report = validate_plugin(root)

        assert report.skill_names == ("alpha",)

    def test_grandchild_skill_is_not_discovered(self, tmp_path: Path) -> None:
        root = make_plugin(tmp_path / "p", "example", skills=())
        write_skill(root / "skills" / "group" / "inner")

        report = validate_plugin(root)

        # ``group`` has no SKILL.md of its own, so it is not a skill, and
        # ``inner`` is a grandchild, so it is not discovered either.
        assert report.skills == ()

    def test_directory_without_skill_md_is_silently_skipped(self, tmp_path: Path) -> None:
        """Not a candidate, so not an error either."""
        root = make_plugin(tmp_path / "p", "example", skills=("alpha",))
        (root / "skills" / "assets").mkdir()

        report = validate_plugin(root)

        assert report.skill_names == ("alpha",)
        assert report.findings == ()

    def test_file_inside_skills_is_silently_skipped(self, tmp_path: Path) -> None:
        root = make_plugin(tmp_path / "p", "example", skills=("alpha",))
        (root / "skills" / "README.md").write_text("notes", encoding="utf-8")

        report = validate_plugin(root)

        assert report.skill_names == ("alpha",)
        assert report.findings == ()

    def test_skill_md_as_a_directory_is_not_a_skill(self, tmp_path: Path) -> None:
        """§7.1 requires SKILL.md resolve to a regular file."""
        root = make_plugin(tmp_path / "p", "example", skills=("alpha",))
        (root / "skills" / "broken" / "SKILL.md").mkdir(parents=True)

        report = validate_plugin(root)

        assert report.skill_names == ("alpha",)

    def test_skill_with_mismatched_frontmatter_name_is_skipped(self, tmp_path: Path) -> None:
        """Agent Skills requires folder name == frontmatter name."""
        root = make_plugin(tmp_path / "p", "example", skills=("alpha",))
        write_skill(root / "skills" / "beta", name="something-else")

        report = validate_plugin(root)

        assert report.loadable is True
        assert report.skill_names == ("alpha",)
        finding = find(report, "skill.invalid")
        assert finding is not None
        assert finding.severity is Severity.SKIPPED
        assert finding.spec_ref == "§7.1"
        assert "beta" in finding.message

    def test_skill_with_malformed_frontmatter_is_skipped(self, tmp_path: Path) -> None:
        root = make_plugin(tmp_path / "p", "example", skills=("alpha",))
        broken = root / "skills" / "broken"
        broken.mkdir(parents=True)
        (broken / "SKILL.md").write_text("no frontmatter here", encoding="utf-8")

        report = validate_plugin(root)

        assert report.skill_names == ("alpha",)
        assert find(report, "skill.invalid") is not None

    def test_skill_missing_description_is_skipped(self, tmp_path: Path) -> None:
        root = make_plugin(tmp_path / "p", "example", skills=("alpha",))
        broken = root / "skills" / "broken"
        broken.mkdir(parents=True)
        (broken / "SKILL.md").write_text("---\nname: broken\n---\n", encoding="utf-8")

        report = validate_plugin(root)

        assert report.skill_names == ("alpha",)
        assert find(report, "skill.invalid") is not None

    def test_sibling_independence(self, tmp_path: Path) -> None:
        """_Requirements: 12.1 — N skills, k invalid, N-k discovered._"""
        root = make_plugin(tmp_path / "p", "example", skills=("good-one", "good-two"))
        write_skill(root / "skills" / "bad-one", name="mismatch-a")
        write_skill(root / "skills" / "bad-two", name="mismatch-b")

        report = validate_plugin(root)

        assert sorted(report.skill_names) == ["good-one", "good-two"]
        assert len(report.findings_with(Severity.SKIPPED)) == 2
        assert report.loadable is True

    def test_skill_reached_through_an_internal_symlink_is_accepted(self, tmp_path: Path) -> None:
        """§4.1 permits links resolving inside the root."""
        root = make_plugin(tmp_path / "p", "example", skills=("alpha",))
        (root / "skills" / "linked").symlink_to("alpha")

        report = validate_plugin(root)

        # The link resolves to alpha's directory, whose frontmatter name is
        # "alpha", so the link's own name does not match and it is reported --
        # but crucially it is contained, not an escape.
        assert "alpha" in report.skill_names
        assert find(report, "skill.outside_root") is None


class TestContainmentLadder:
    """§4.1's narrowest-applicable-failure-boundary ladder."""

    def test_manifest_symlinked_outside_rejects_the_plugin(self, tmp_path: Path) -> None:
        """Ladder rule 1: reject the whole plugin."""
        outside = tmp_path / "outside"
        outside.mkdir()
        (outside / "manifest.json").write_text(
            json.dumps(make_manifest("example")), encoding="utf-8"
        )
        root = tmp_path / "p"
        write_skill(root / "skills" / "alpha")
        (root / "plugin.json").symlink_to(outside / "manifest.json")

        report = validate_plugin(root)

        assert report.loadable is False
        finding = find(report, "manifest.outside_root")
        assert finding is not None
        assert finding.spec_ref == "§4.1"
        assert report.skills == ()

    def test_skills_symlinked_outside_invalidates_only_skills(self, tmp_path: Path) -> None:
        """Ladder rule 2: that component TYPE is invalid."""
        outside = tmp_path / "outside-skills"
        write_skill(outside / "sneaky")
        root = make_plugin(tmp_path / "p", "example", skills=(), mcp={"mcpServers": {}})
        (root / "skills").symlink_to(outside, target_is_directory=True)

        report = validate_plugin(root)

        assert report.loadable is True  # the plugin is not rejected
        finding = find(report, "skills.outside_root")
        assert finding is not None
        assert finding.spec_ref == "§4.1"
        assert report.skills == ()
        assert report.mcp_present is True  # MCP type unaffected

    def test_skill_dir_symlinked_outside_skips_only_that_skill(self, tmp_path: Path) -> None:
        """Ladder rule 3: skip that SKILL."""
        outside = tmp_path / "outside"
        write_skill(outside / "sneaky")
        root = make_plugin(tmp_path / "p", "example", skills=("alpha",))
        (root / "skills" / "sneaky").symlink_to(outside / "sneaky", target_is_directory=True)

        report = validate_plugin(root)

        assert report.loadable is True
        assert report.skill_names == ("alpha",)
        finding = find(report, "skill.outside_root")
        assert finding is not None
        assert finding.spec_ref == "§4.1"

    def test_skill_md_symlinked_outside_skips_only_that_skill(self, tmp_path: Path) -> None:
        outside = tmp_path / "outside"
        outside.mkdir()
        (outside / "SKILL.md").write_text(
            "---\nname: sneaky\ndescription: x\n---\n", encoding="utf-8"
        )
        root = make_plugin(tmp_path / "p", "example", skills=("alpha",))
        sneaky = root / "skills" / "sneaky"
        sneaky.mkdir(parents=True)
        (sneaky / "SKILL.md").symlink_to(outside / "SKILL.md")

        report = validate_plugin(root)

        assert report.loadable is True
        assert report.skill_names == ("alpha",)
        assert find(report, "skill.outside_root") is not None

    def test_mcp_symlinked_outside_invalidates_only_mcp(self, tmp_path: Path) -> None:
        outside = tmp_path / "outside"
        outside.mkdir()
        (outside / "mcp.json").write_text("{}", encoding="utf-8")
        root = make_plugin(tmp_path / "p", "example", skills=("alpha",))
        (root / "mcp.json").symlink_to(outside / "mcp.json")

        report = validate_plugin(root)

        assert report.loadable is True
        assert report.skill_names == ("alpha",)  # skills unaffected
        assert report.mcp_present is False
        assert find(report, "mcp.outside_root") is not None


class TestMcpDetection:
    """_Requirements: 11.2 — detect and report, never load (Increment 1)._"""

    def test_absent_mcp_json_reports_nothing(self, plugin_factory) -> None:
        report = validate_plugin(plugin_factory("example"))

        assert report.mcp_present is False
        assert find(report, "mcp.unsupported") is None

    def test_present_mcp_json_is_reported_as_unsupported(self, tmp_path: Path) -> None:
        root = make_plugin(
            tmp_path / "p",
            "example",
            mcp={"$schema": "x", "mcpServers": {"s": {"type": "stdio", "command": "x"}}},
        )

        report = validate_plugin(root)

        assert report.loadable is True
        assert report.mcp_present is True
        finding = find(report, "mcp.unsupported")
        assert finding is not None
        assert finding.severity is Severity.WARNING
        assert "not supported" in finding.message
        # Skills still deliver.
        assert report.skill_names == ("example-skill",)

    def test_no_mcp_servers_are_mapped(self, tmp_path: Path) -> None:
        """Increment 1 records presence and nothing more."""
        root = make_plugin(
            tmp_path / "p",
            "example",
            mcp={"mcpServers": {"s": {"type": "stdio", "command": "x"}}},
        )

        report = validate_plugin(root)

        assert report.mcp_servers == ()

    def test_malformed_mcp_json_is_not_even_parsed(self, tmp_path: Path) -> None:
        """Requirement 11.3 reserves mcp.json validation for Increment 2.

        A syntactically broken mcp.json must therefore produce the same
        "unsupported" outcome as a valid one, not a parse error.
        """
        root = make_plugin(tmp_path / "p", "example")
        (root / "mcp.json").write_text("{ this is not json", encoding="utf-8")

        report = validate_plugin(root)

        assert report.loadable is True
        assert report.mcp_present is True
        assert find(report, "mcp.unsupported") is not None
        assert [f for f in report.findings if "json" in f.code] == []

    def test_mcp_json_as_a_directory_invalidates_only_mcp(self, tmp_path: Path) -> None:
        root = make_plugin(tmp_path / "p", "example")
        (root / "mcp.json").mkdir()

        report = validate_plugin(root)

        assert report.loadable is True
        assert report.mcp_present is False
        finding = find(report, "mcp.not_a_file")
        assert finding is not None
        assert finding.spec_ref == "§6.2"
        assert report.skill_names == ("example-skill",)


class TestLoadableIsDerived:
    """_Requirements: 5.3, 5.4 — loadable is computed, never settable._"""

    def test_loadable_is_a_read_only_property(self) -> None:
        from cli_agent_orchestrator.agent_plugins.models import PluginValidationReport

        assert isinstance(PluginValidationReport.loadable, property)
        assert PluginValidationReport.loadable.fset is None
        assert "loadable" not in PluginValidationReport.__dataclass_fields__

    def test_loadable_equals_absence_of_fatal(self, tmp_path: Path, plugin_factory) -> None:
        valid = validate_plugin(plugin_factory("example"))
        invalid = validate_plugin(make_plugin(tmp_path / "bad", "x", raw_manifest="{"))

        for report in (valid, invalid):
            expected = not any(f.severity is Severity.FATAL for f in report.findings)
            assert report.loadable == expected

    def test_non_fatal_findings_do_not_make_a_plugin_unloadable(self, tmp_path: Path) -> None:
        root = make_plugin(
            tmp_path / "p",
            "example",
            manifest=make_manifest("example", surprise=1, extensions="bad"),
            mcp={"mcpServers": {}},
        )
        write_skill(root / "skills" / "mismatch", name="other")

        report = validate_plugin(root)

        assert report.loadable is True
        assert len(report.findings) >= 4
        assert report.findings_with(Severity.FATAL) == ()


class TestEverySpecRefIsCited:
    """Every finding cites a clause; the corpus depends on it."""

    def test_all_findings_carry_a_spec_ref_and_code(self, tmp_path: Path) -> None:
        root = make_plugin(
            tmp_path / "p",
            "example",
            manifest=make_manifest("example", surprise=1, extensions=5),
            mcp={"mcpServers": {}},
        )
        write_skill(root / "skills" / "mismatch", name="other")

        report = validate_plugin(root)

        assert report.findings
        for finding in report.findings:
            assert finding.code, "every finding needs a machine-readable code"
            assert finding.spec_ref.startswith("§"), f"{finding.code} cites no clause"
            assert finding.message


# ---------------------------------------------------------------------------
# Conformance corpus (Requirement 23.3)
# ---------------------------------------------------------------------------


def _corpus_missing_manifest(root: Path) -> None:
    root.mkdir(parents=True)
    write_skill(root / "skills" / "alpha")


def _corpus_invalid_json(root: Path) -> None:
    make_plugin(root, "example", raw_manifest="{ broken")


def _corpus_unrecognized_schema(root: Path) -> None:
    make_plugin(
        root,
        "example",
        manifest={"$schema": "https://example.test/other.json", "name": "example"},
    )


def _corpus_bad_name(root: Path) -> None:
    make_plugin(root, "example", manifest={"$schema": SCHEMA_ID, "name": "Bad--Name"})


def _corpus_unknown_field(root: Path) -> None:
    make_plugin(root, "example", manifest=make_manifest("example", surprise="v"))


def _corpus_extensions_not_object(root: Path) -> None:
    make_plugin(root, "example", manifest=make_manifest("example", extensions=[1, 2]))


def _corpus_unimplemented_namespace(root: Path) -> None:
    make_plugin(
        root, "example", manifest=make_manifest("example", extensions={"com.example.x": {"a": 1}})
    )


def _corpus_skills_not_a_directory(root: Path) -> None:
    make_plugin(root, "example", skills=(), mcp={"mcpServers": {}})
    (root / "skills").write_text("nope", encoding="utf-8")


def _corpus_one_invalid_sibling(root: Path) -> None:
    make_plugin(root, "example", skills=("alpha",))
    write_skill(root / "skills" / "beta", name="mismatched")


def _corpus_skill_escapes_root(root: Path) -> None:
    outside = root.parent / f"{root.name}-outside"
    write_skill(outside / "sneaky")
    make_plugin(root, "example", skills=("alpha",))
    (root / "skills" / "sneaky").symlink_to(outside / "sneaky", target_is_directory=True)


def _corpus_mcp_present(root: Path) -> None:
    make_plugin(root, "example", mcp={"mcpServers": {"s": {"type": "stdio", "command": "x"}}})


def _corpus_mcp_not_a_file(root: Path) -> None:
    make_plugin(root, "example")
    (root / "mcp.json").mkdir()


def _corpus_manifest_escapes_root(root: Path) -> None:
    outside = root.parent / f"{root.name}-outside"
    outside.mkdir(parents=True)
    (outside / "m.json").write_text(json.dumps(make_manifest("example")), encoding="utf-8")
    root.mkdir(parents=True)
    write_skill(root / "skills" / "alpha")
    (root / "plugin.json").symlink_to(outside / "m.json")


# One row per failure-isolation behavior:
#   (case id, builder, expected loadable, expected code or None, expected
#    spec_ref or None, expected discovered skill count)
CORPUS = [
    ("manifest-missing", _corpus_missing_manifest, False, "manifest.missing", "§5.1", 0),
    ("manifest-invalid-json", _corpus_invalid_json, False, "manifest.invalid_json", "§5.1", 0),
    (
        "manifest-unrecognized-schema",
        _corpus_unrecognized_schema,
        False,
        "manifest.unsupported_schema",
        "§5.2",
        0,
    ),
    ("manifest-bad-name", _corpus_bad_name, False, "manifest.schema_violation", "§5.2", 0),
    (
        "manifest-escapes-root",
        _corpus_manifest_escapes_root,
        False,
        "manifest.outside_root",
        "§4.1",
        0,
    ),
    ("manifest-unknown-field", _corpus_unknown_field, True, "manifest.unknown_field", "§5.2", 1),
    (
        "manifest-extensions-not-object",
        _corpus_extensions_not_object,
        True,
        "manifest.extensions_not_object",
        "§8.1",
        1,
    ),
    ("manifest-unimplemented-namespace", _corpus_unimplemented_namespace, True, None, None, 1),
    (
        "skills-not-a-directory",
        _corpus_skills_not_a_directory,
        True,
        "skills.not_a_directory",
        "§6.2",
        0,
    ),
    ("skills-one-invalid-sibling", _corpus_one_invalid_sibling, True, "skill.invalid", "§7.1", 1),
    ("skill-escapes-root", _corpus_skill_escapes_root, True, "skill.outside_root", "§4.1", 1),
    ("mcp-present-unsupported", _corpus_mcp_present, True, "mcp.unsupported", "§11.3", 1),
    ("mcp-not-a-file", _corpus_mcp_not_a_file, True, "mcp.not_a_file", "§6.2", 1),
]


class TestConformanceCorpus:
    """_Requirements: 23.3 — one case per failure-isolation row, exact codes._"""

    @pytest.mark.parametrize(
        "case_id,builder,expected_loadable,expected_code,expected_ref,expected_skills",
        CORPUS,
        ids=[row[0] for row in CORPUS],
    )
    def test_case(
        self,
        tmp_path: Path,
        case_id: str,
        builder,
        expected_loadable: bool,
        expected_code: Optional[str],
        expected_ref: Optional[str],
        expected_skills: int,
    ) -> None:
        root = tmp_path / case_id
        builder(root)

        report = validate_plugin(root)

        assert report.loadable is expected_loadable, f"{case_id}: loadable mismatch"
        assert len(report.skills) == expected_skills, f"{case_id}: skill count mismatch"

        if expected_code is None:
            assert report.findings == (), f"{case_id}: expected no findings"
        else:
            finding = find(report, expected_code)
            assert finding is not None, f"{case_id}: missing {expected_code}; got {codes(report)}"
            assert finding.spec_ref == expected_ref, f"{case_id}: wrong spec_ref"

    def test_every_case_id_is_unique(self) -> None:
        ids = [row[0] for row in CORPUS]
        assert len(ids) == len(set(ids))

    def test_fatal_cases_discover_zero_components(self, tmp_path: Path) -> None:
        """_Requirements: 6.4 — a fatal violation discovers nothing._"""
        for case_id, builder, loadable, _code, _ref, _skills in CORPUS:
            if loadable:
                continue
            root = tmp_path / f"fatal-{case_id}"
            builder(root)

            report = validate_plugin(root)

            assert report.skills == (), f"{case_id} discovered components despite being fatal"
            assert report.mcp_servers == ()


@pytest.mark.skipif(
    not (CANONICAL_EXAMPLE / "plugin.json").is_file(),
    reason="canonical agent-plugins-example checkout not present",
)
class TestCanonicalExample:
    """_Requirements: 23.4 — the upstream example is a known-good fixture._"""

    def test_validates_cleanly(self) -> None:
        report = validate_plugin(CANONICAL_EXAMPLE)

        assert report.loadable is True
        assert report.findings_with(Severity.FATAL) == ()

    def test_declares_the_pinned_schema(self) -> None:
        report = validate_plugin(CANONICAL_EXAMPLE)

        assert report.manifest is not None
        assert report.manifest.schema_id == SCHEMA_ID
        assert report.manifest.name == "agent-plugins-example"

    def test_its_skill_is_discovered(self) -> None:
        report = validate_plugin(CANONICAL_EXAMPLE)

        assert "migrate-agent-plugin" in report.skill_names

    def test_ships_no_mcp_json(self) -> None:
        report = validate_plugin(CANONICAL_EXAMPLE)

        assert report.mcp_present is False
