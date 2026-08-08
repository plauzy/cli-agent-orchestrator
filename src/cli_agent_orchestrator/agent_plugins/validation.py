"""The total plugin validator.

``validate_plugin(root)`` answers, for an *arbitrary* directory, whether it is a
loadable Agent Plugin and what components it contains — and it **never raises**
(Requirement 5.1). That is not defensive programming for its own sake: the CLI,
the HTTP API, the web panel, the installer, and CI all need the same structured
answer, and three of those five must render *partial* success. A total function
returning a report is the only shape that serves all five. Property P1 asserts
it directly against hostile inputs.

Two rules shape almost every decision here:

* **Fatality is narrow** (§11.3 rule 2). Exactly two manifest problems are
  non-fatal: an unknown top-level field, and a non-object ``extensions``. Every
  other schema violation rejects the plugin and discovers zero components.
* **Failures isolate to the narrowest boundary** (§4.1, §6.2, §7.1). A bad
  ``skills/`` does not disable ``mcp.json`` discovery; one malformed skill does
  not disable its siblings.

Increment 1 boundary
--------------------
This module detects ``mcp.json`` and reports it as unsupported (Requirement
11.2). It never validates against ``mcp.schema.json``, never expands
``${PLUGIN_ROOT}``/``${PLUGIN_DATA}``, and never launches a subprocess
(Requirement 11.3).
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from cli_agent_orchestrator.agent_plugins import schema_registry
from cli_agent_orchestrator.agent_plugins.containment import resolve_within_root
from cli_agent_orchestrator.agent_plugins.models import (
    Author,
    DiscoveredSkill,
    Finding,
    PluginManifest,
    PluginValidationReport,
    Severity,
)

logger = logging.getLogger(__name__)

# §5.1 / §6.1 fixed locations. A plugin cannot override these and cannot
# declare components inline, so they are constants rather than configuration.
MANIFEST_FILENAME = "plugin.json"
SKILLS_DIRNAME = "skills"
MCP_FILENAME = "mcp.json"
SKILL_FILENAME = "SKILL.md"

# Largest manifest CAO will read. §5 sets no limit, but an unbounded read is how
# a "validator" becomes a memory-exhaustion vector, and Requirement 5.2 asks for
# termination in time proportional to the candidate's size.
MAX_MANIFEST_BYTES = 1 * 1024 * 1024

# The manifest member that carries client extension data (§8.1).
EXTENSIONS_FIELD = "extensions"


def _finding(
    severity: Severity, code: str, spec_ref: str, message: str, path: Optional[str] = None
) -> Finding:
    """Construct a finding (a shorthand; every field is required by design)."""
    return Finding(severity=severity, code=code, spec_ref=spec_ref, message=message, path=path)


def validate_plugin(root: Path) -> PluginValidationReport:
    """Validate the directory at ``root`` as an Agent Plugin.

    Returns a report in every case. Callers decide what to do with it; this
    function neither raises nor mutates anything on disk.
    """
    try:
        return _validate(Path(root))
    except Exception as exc:  # pragma: no cover - the totality backstop
        # Requirement 5.1 is absolute, so an unanticipated failure still has to
        # come back as a report. Reaching here is a bug worth logging loudly,
        # but it must not become an exception in the caller.
        logger.exception("Unexpected error validating plugin at %s", root)
        return PluginValidationReport(
            root=Path(root),
            findings=(
                _finding(
                    Severity.FATAL,
                    "validator.internal_error",
                    "§11.3",
                    f"internal error while validating this plugin: {exc}",
                ),
            ),
        )


def _validate(root: Path) -> PluginValidationReport:
    """Validation body. Split out so ``validate_plugin`` can be a total wrapper."""
    findings: List[Finding] = []

    root_real = resolve_within_root(root, root)
    if root_real is None or not root_real.is_dir():
        findings.append(
            _finding(
                Severity.FATAL,
                "plugin.root_not_a_directory",
                "§4.1",
                f"plugin root is not a readable directory: {root}",
            )
        )
        return PluginValidationReport(root=root, findings=tuple(findings))

    # --- manifest -----------------------------------------------------------
    manifest, manifest_findings = _validate_manifest(root_real)
    findings.extend(manifest_findings)

    if manifest is None:
        # §11.3 rule 2 / Requirement 6.4: a fatal manifest violation rejects the
        # plugin and MUST NOT discover any of its components. Returning here is
        # what makes "zero components" structural rather than a later filter.
        return PluginValidationReport(root=root_real, findings=tuple(findings))

    # --- components ---------------------------------------------------------
    skills, skill_findings = _discover_skills(root_real)
    findings.extend(skill_findings)

    mcp_present, mcp_findings = _discover_mcp(root_real)
    findings.extend(mcp_findings)

    return PluginValidationReport(
        root=root_real,
        manifest=manifest,
        skills=tuple(skills),
        mcp_present=mcp_present,
        mcp_servers=(),  # Increment 1 never maps MCP servers (Requirement 11.3)
        findings=tuple(findings),
    )


# ---------------------------------------------------------------------------
# Manifest
# ---------------------------------------------------------------------------


def _validate_manifest(root_real: Path) -> Tuple[Optional[PluginManifest], List[Finding]]:
    """Validate ``plugin.json``.

    Returns ``(None, findings)`` when the manifest is fatally invalid, which is
    the signal to discover zero components.
    """
    findings: List[Finding] = []

    manifest_path = resolve_within_root(root_real, root_real / MANIFEST_FILENAME)
    if manifest_path is None:
        # §4.1 ladder rule 1: plugin.json outside the root rejects the plugin.
        findings.append(
            _finding(
                Severity.FATAL,
                "manifest.outside_root",
                "§4.1",
                f"{MANIFEST_FILENAME} resolves outside the plugin root",
                MANIFEST_FILENAME,
            )
        )
        return None, findings

    if not manifest_path.is_file():
        # §4.2 / §5.1: the manifest at the plugin root is the conformance floor.
        findings.append(
            _finding(
                Severity.FATAL,
                "manifest.missing",
                "§5.1",
                f"no {MANIFEST_FILENAME} at the plugin root",
                MANIFEST_FILENAME,
            )
        )
        return None, findings

    raw, read_finding = _read_manifest_bytes(manifest_path)
    if raw is None:
        findings.append(read_finding)  # type: ignore[arg-type]
        return None, findings

    try:
        document = json.loads(raw)
    except ValueError as exc:
        findings.append(
            _finding(
                Severity.FATAL,
                "manifest.invalid_json",
                "§5.1",
                f"{MANIFEST_FILENAME} is not valid JSON: {exc}",
                MANIFEST_FILENAME,
            )
        )
        return None, findings

    if not isinstance(document, dict):
        findings.append(
            _finding(
                Severity.FATAL,
                "manifest.not_an_object",
                "§5.2",
                f"{MANIFEST_FILENAME} must contain a JSON object, "
                f"found {type(document).__name__}",
                MANIFEST_FILENAME,
            )
        )
        return None, findings

    # §11.1 rule 2: select locally supported rules from $schema FIRST, then
    # validate. An unrecognized identifier is fatal and must never trigger a
    # fetch (§5.2).
    schema_id = document.get("$schema")
    if not schema_registry.is_recognized_plugin_schema(schema_id):
        findings.append(
            _finding(
                Severity.FATAL,
                "manifest.unsupported_schema",
                "§5.2",
                (
                    f"unrecognized $schema {schema_id!r}; this CAO version "
                    f"supports only "
                    f"{', '.join(sorted(schema_registry.RECOGNIZED_PLUGIN_SCHEMA_IDS))}"
                ),
                MANIFEST_FILENAME,
            )
        )
        return None, findings

    # The two non-fatal exceptions are handled by removing them from the
    # document before schema validation, rather than by pattern-matching
    # jsonschema's error output afterwards. That keeps the classification
    # driven by the spec's own wording instead of by error-message shapes that
    # a jsonschema upgrade could change.
    candidate = dict(document)
    findings.extend(_take_unknown_fields(candidate))
    findings.extend(_take_extensions(candidate))

    schema_findings = _validate_against_schema(candidate)
    if schema_findings:
        findings.extend(schema_findings)
        return None, findings

    return _build_manifest(candidate), findings


def _read_manifest_bytes(manifest_path: Path) -> Tuple[Optional[str], Optional[Finding]]:
    """Read the manifest as text, bounded and encoding-checked."""
    try:
        size = manifest_path.stat().st_size
    except OSError as exc:
        return None, _finding(
            Severity.FATAL,
            "manifest.unreadable",
            "§5.1",
            f"could not stat {MANIFEST_FILENAME}: {exc}",
            MANIFEST_FILENAME,
        )

    if size > MAX_MANIFEST_BYTES:
        return None, _finding(
            Severity.FATAL,
            "manifest.too_large",
            "§5.1",
            f"{MANIFEST_FILENAME} is {size} bytes, exceeding the "
            f"{MAX_MANIFEST_BYTES}-byte limit CAO will read",
            MANIFEST_FILENAME,
        )

    try:
        return manifest_path.read_text(encoding="utf-8"), None
    except UnicodeDecodeError as exc:
        return None, _finding(
            Severity.FATAL,
            "manifest.not_utf8",
            "§5.1",
            f"{MANIFEST_FILENAME} is not valid UTF-8: {exc}",
            MANIFEST_FILENAME,
        )
    except OSError as exc:
        return None, _finding(
            Severity.FATAL,
            "manifest.unreadable",
            "§5.1",
            f"could not read {MANIFEST_FILENAME}: {exc}",
            MANIFEST_FILENAME,
        )


def _known_manifest_fields() -> frozenset:
    """Top-level member names the pinned schema defines.

    Read out of the vendored schema rather than hardcoded, so the set cannot
    drift from the bytes CAO actually validates against.
    """
    schema = schema_registry.load_schema(schema_registry.PLUGIN_SCHEMA_FILENAME)
    properties = schema.get("properties")
    if not isinstance(properties, dict):  # pragma: no cover - guarded by pin tests
        return frozenset()
    return frozenset(properties)


def _take_unknown_fields(candidate: Dict[str, Any]) -> List[Finding]:
    """Remove unrecognized top-level fields, reporting each (§5.2).

    Non-fatal: the field is reported and ignored, and the plugin still loads
    (Requirement 6.1). Removing it before schema validation is what keeps the
    closed schema's ``additionalProperties: false`` from turning this into a
    fatal error.
    """
    known = _known_manifest_fields()
    findings: List[Finding] = []
    for name in sorted(set(candidate) - known):
        candidate.pop(name, None)
        findings.append(
            _finding(
                Severity.WARNING,
                "manifest.unknown_field",
                "§5.2",
                f"ignoring unrecognized top-level manifest field {name!r}",
                MANIFEST_FILENAME,
            )
        )
    return findings


def _take_extensions(candidate: Dict[str, Any]) -> List[Finding]:
    """Remove ``extensions`` from the document to be schema-validated (§8.1).

    CAO implements **no** extension namespace, and §8.1 requires ignoring an
    unimplemented namespace *without validating the contents of its value*.
    The pinned schema constrains namespace values to objects, so leaving
    ``extensions`` in place would validate exactly what the spec forbids
    validating. It is therefore removed wholesale, and the only check kept is
    the one §8.1 states explicitly: the field itself must be an object.

    Consequently a namespace CAO does not implement produces **no finding at
    all** (Requirement 6.3) — not even an informational one.
    """
    if EXTENSIONS_FIELD not in candidate:
        return []

    value = candidate.pop(EXTENSIONS_FIELD)
    if isinstance(value, dict):
        return []

    # Non-fatal: report and ignore, keep loading components (Requirement 6.2).
    return [
        _finding(
            Severity.WARNING,
            "manifest.extensions_not_object",
            "§8.1",
            f"ignoring {EXTENSIONS_FIELD!r}: expected an object, " f"found {type(value).__name__}",
            MANIFEST_FILENAME,
        )
    ]


def _validate_against_schema(candidate: Dict[str, Any]) -> List[Finding]:
    """Validate the reduced manifest. Any error here is fatal (§11.3 rule 2)."""
    try:
        validator = schema_registry.plugin_manifest_validator()
    except schema_registry.SchemaUnavailableError as exc:
        # A CAO packaging fault, not the plugin's fault. Still fatal for this
        # plugin -- validating against nothing would be worse -- but the
        # message must not blame the plugin author.
        return [
            _finding(
                Severity.FATAL,
                "validator.schema_unavailable",
                "§5.2",
                f"CAO cannot load its pinned manifest schema: {exc}",
                MANIFEST_FILENAME,
            )
        ]

    findings: List[Finding] = []
    # Sorted so the report is stable for the same input, which the conformance
    # corpus depends on.
    for error in sorted(validator.iter_errors(candidate), key=lambda err: list(err.absolute_path)):
        location = "/".join(str(part) for part in error.absolute_path) or MANIFEST_FILENAME
        findings.append(
            _finding(
                Severity.FATAL,
                "manifest.schema_violation",
                "§5.2",
                f"{location}: {error.message}",
                MANIFEST_FILENAME,
            )
        )
    return findings


def _build_manifest(candidate: Dict[str, Any]) -> PluginManifest:
    """Build the validated manifest view.

    Safe to read fields directly: the document passed schema validation, so
    types are already guaranteed.
    """
    raw_author = candidate.get("author")
    author = None
    if isinstance(raw_author, dict):
        author = Author(
            name=raw_author.get("name"),
            email=raw_author.get("email"),
            url=raw_author.get("url"),
        )

    raw_keywords = candidate.get("keywords")
    keywords: Tuple[str, ...] = ()
    if isinstance(raw_keywords, list):
        keywords = tuple(item for item in raw_keywords if isinstance(item, str))

    return PluginManifest(
        schema_id=str(candidate["$schema"]),
        name=str(candidate["name"]),
        version=candidate.get("version"),
        description=candidate.get("description"),
        author=author,
        homepage=candidate.get("homepage"),
        repository=candidate.get("repository"),
        license=candidate.get("license"),
        keywords=keywords,
    )


# ---------------------------------------------------------------------------
# Components
# ---------------------------------------------------------------------------


def _discover_skills(root_real: Path) -> Tuple[List[DiscoveredSkill], List[Finding]]:
    """Discover skills under the fixed ``skills/`` location (§6.1, §7.1)."""
    findings: List[Finding] = []

    skills_dir = resolve_within_root(root_real, root_real / SKILLS_DIRNAME)
    if skills_dir is None:
        # §4.1 ladder rule 2: a fixed component location outside the root makes
        # that component TYPE invalid -- not the plugin.
        findings.append(
            _finding(
                Severity.SKIPPED,
                "skills.outside_root",
                "§4.1",
                f"{SKILLS_DIRNAME}/ resolves outside the plugin root; " f"skipping all skills",
                SKILLS_DIRNAME,
            )
        )
        return [], findings

    if not skills_dir.exists():
        # §6.2: an absent fixed location is explicitly not an error.
        return [], findings

    if not skills_dir.is_dir():
        # §6.2: present but the wrong filesystem kind invalidates this component
        # type only; MCP discovery continues unaffected (Requirement 12.3).
        findings.append(
            _finding(
                Severity.SKIPPED,
                "skills.not_a_directory",
                "§6.2",
                f"{SKILLS_DIRNAME} exists but is not a directory; skipping all skills",
                SKILLS_DIRNAME,
            )
        )
        return [], findings

    try:
        # Sorted so the report is deterministic. The discovered *set* is
        # independent of iteration order either way (Requirement 12.2); sorting
        # additionally makes the finding order reproducible.
        entries = sorted(skills_dir.iterdir(), key=lambda item: item.name)
    except OSError as exc:
        findings.append(
            _finding(
                Severity.SKIPPED,
                "skills.unreadable",
                "§6.2",
                f"could not read {SKILLS_DIRNAME}/: {exc}",
                SKILLS_DIRNAME,
            )
        )
        return [], findings

    skills: List[DiscoveredSkill] = []
    for entry in entries:
        # §7.1: only IMMEDIATE children are candidates; no recursive descent.
        skill, skill_findings = _validate_skill(root_real, entry)
        findings.extend(skill_findings)
        if skill is not None:
            skills.append(skill)

    return skills, findings


def _validate_skill(
    root_real: Path, entry: Path
) -> Tuple[Optional[DiscoveredSkill], List[Finding]]:
    """Validate one candidate skill directory independently (§7.1).

    Independence is the point (Requirement 12.1): whatever is wrong here is
    reported against this skill and nothing else.
    """
    relative = f"{SKILLS_DIRNAME}/{entry.name}"

    contained = resolve_within_root(root_real, entry)
    if contained is None:
        # §4.1 ladder rule 3: skip this skill only.
        return None, [
            _finding(
                Severity.SKIPPED,
                "skill.outside_root",
                "§4.1",
                f"skill {entry.name!r} resolves outside the plugin root",
                relative,
            )
        ]

    if not contained.is_dir():
        # Not a skill candidate at all. A stray LICENSE file inside skills/ is
        # not an error -- §7.1 defines a skill as a *directory* containing
        # SKILL.md, so a non-directory simply is not a candidate.
        return None, []

    skill_md = resolve_within_root(root_real, contained / SKILL_FILENAME)
    if skill_md is None:
        # A SKILL.md symlinked out of the root: skip this skill (§4.1 rule 3).
        return None, [
            _finding(
                Severity.SKIPPED,
                "skill.outside_root",
                "§4.1",
                f"{SKILL_FILENAME} for skill {entry.name!r} resolves outside " f"the plugin root",
                f"{relative}/{SKILL_FILENAME}",
            )
        ]

    if not skill_md.is_file():
        # §7.1 requires SKILL.md resolve to a REGULAR FILE. A directory named
        # SKILL.md, or no SKILL.md at all, means this is not a skill directory.
        return None, []

    # §7.1 delegates the SKILL.md format to the Agent Skills specification.
    # CAO already implements that check, and reusing it is what guarantees a
    # projected plugin skill behaves identically to a built-in one -- notably
    # the folder-name == frontmatter-name equality that list_skills() enforces.
    from cli_agent_orchestrator.utils.skills import validate_skill_folder

    try:
        validate_skill_folder(contained)
    except Exception as exc:
        return None, [
            _finding(
                Severity.SKIPPED,
                "skill.invalid",
                "§7.1",
                f"skipping skill {entry.name!r}: {exc}",
                relative,
            )
        ]

    return DiscoveredSkill(name=entry.name, directory=contained), []


def _discover_mcp(root_real: Path) -> Tuple[bool, List[Finding]]:
    """Detect ``mcp.json`` and report it as unsupported (Requirement 11.2).

    Increment 1 deliberately stops at detection. §11.3 rule 1 and §7.2.2 rule 4
    prescribe exactly this for an unsupported component type: note it, report
    it, keep loading everything else.
    """
    findings: List[Finding] = []

    mcp_path = resolve_within_root(root_real, root_real / MCP_FILENAME)
    if mcp_path is None:
        # §4.1 ladder rule 2, applied to the MCP component type.
        findings.append(
            _finding(
                Severity.SKIPPED,
                "mcp.outside_root",
                "§4.1",
                f"{MCP_FILENAME} resolves outside the plugin root; ignoring it",
                MCP_FILENAME,
            )
        )
        return False, findings

    if not mcp_path.exists():
        return False, findings  # §6.2: absent is not an error

    if not mcp_path.is_file():
        # §6.2: present but the wrong kind invalidates this component type only.
        findings.append(
            _finding(
                Severity.SKIPPED,
                "mcp.not_a_file",
                "§6.2",
                f"{MCP_FILENAME} exists but is not a regular file; " f"ignoring MCP configuration",
                MCP_FILENAME,
            )
        )
        return False, findings

    # Present and well-shaped, but this CAO version supports skills only.
    # NOTE: the file is deliberately NOT parsed or schema-validated here --
    # Requirement 11.3 reserves mcp.schema.json validation for Increment 2.
    findings.append(
        _finding(
            Severity.WARNING,
            "mcp.unsupported",
            "§11.3",
            "MCP servers are not supported in this CAO version; "
            "this plugin's skills are unaffected",
            MCP_FILENAME,
        )
    )
    return True, findings
