"""Data models for Agent Plugins support.

These are frozen dataclasses rather than pydantic models — a deliberate
departure from ``cli_agent_orchestrator/models/``, which models *request and
response payloads*. These types model a **validation verdict** that must be
constructible for an arbitrary, hostile directory tree without ever raising
(Requirement 5.1). A validating constructor is the wrong tool for that job:
the whole point is that malformed input becomes a ``Finding``, not an
exception. Immutability additionally makes a report safe to hand to the CLI,
the API, the web panel, the installer, and CI without defensive copying.

``Severity`` uses an explicit ``str`` mixin rather than ``enum.StrEnum``
because ``requires-python`` is ``>=3.10`` and ``StrEnum`` landed in 3.11.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Optional, Tuple


class Severity(str, Enum):
    """How much a finding costs the plugin that produced it.

    The ladder is load-bearing: ``FATAL`` is the *only* severity that makes a
    plugin unloadable, so the boundary between "this plugin is rejected" and
    "one piece of it was dropped" is a single, checkable predicate rather than
    a judgement spread across call sites.
    """

    FATAL = "fatal"  # plugin rejected outright (§11.3 rule 2)
    SKIPPED = "skipped"  # one component type / skill / server entry dropped
    WARNING = "warning"  # reported, nothing dropped
    INFO = "info"  # informational only


@dataclass(frozen=True)
class Author:
    """The manifest ``author`` object. Closed to name/email/url per §5.4."""

    name: Optional[str] = None
    email: Optional[str] = None
    url: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Serialize, omitting absent members so a round-trip stays minimal."""
        out: Dict[str, Any] = {}
        if self.name is not None:
            out["name"] = self.name
        if self.email is not None:
            out["email"] = self.email
        if self.url is not None:
            out["url"] = self.url
        return out


@dataclass(frozen=True)
class Finding:
    """One reportable observation about a candidate plugin.

    ``spec_ref`` is not decoration. It is what makes the implementation
    auditable against the specification during review, and the conformance
    corpus asserts on it directly — a finding that cannot cite the clause it
    enforces is a finding nobody can check.
    """

    severity: Severity
    code: str  # stable and machine-readable, e.g. "manifest.unknown_field"
    spec_ref: str  # e.g. "§5.2"
    message: str
    path: Optional[str] = None  # plugin-root-relative, when a path is implicated

    def to_dict(self) -> Dict[str, Any]:
        """Serialize for install records and ``--json`` output."""
        return {
            "severity": self.severity.value,
            "code": self.code,
            "spec_ref": self.spec_ref,
            "message": self.message,
            "path": self.path,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Finding":
        """Rehydrate from a persisted install record.

        Tolerant by construction: an install record written by a newer CAO may
        carry a severity this version does not know, and failing to read the
        record would be worse than degrading the severity to ``INFO``.
        """
        raw_severity = data.get("severity")
        try:
            severity = Severity(raw_severity)
        except ValueError:
            severity = Severity.INFO
        return cls(
            severity=severity,
            code=str(data.get("code", "")),
            spec_ref=str(data.get("spec_ref", "")),
            message=str(data.get("message", "")),
            path=data.get("path"),
        )


@dataclass(frozen=True)
class PluginManifest:
    """Validated view of ``plugin.json``. Closed per §5.2.

    ``extensions`` is intentionally **not** modelled in Increment 1. CAO
    implements no extension namespace, and §8.1 requires ignoring an
    unimplemented namespace *without validating its contents*. Giving it a
    field would invite exactly the validation the specification forbids.
    """

    schema_id: str  # the declared `$schema` value (required, §5.3)
    name: str  # required, constrained by §5.5
    version: Optional[str] = None
    description: Optional[str] = None
    author: Optional[Author] = None
    homepage: Optional[str] = None
    repository: Optional[str] = None
    license: Optional[str] = None
    keywords: Tuple[str, ...] = ()


@dataclass(frozen=True)
class DiscoveredSkill:
    """A skill directory found inside a plugin and proven contained in it."""

    name: str
    directory: Path  # absolute, realpath-contained in the plugin root
    projected_as: Optional[Path] = None  # set by the projection engine


@dataclass(frozen=True)
class MappedServer:
    """An ``mcp.json`` server entry mapped into CAO's internal MCP shape.

    Declared here only so ``PluginValidationReport.mcp_servers`` has a type.
    **Increment 1 never populates it** — mapping requires the placeholder
    expansion and ``mcp.schema.json`` validation that Requirement 11.3 places
    exclusively in Increment 2.
    """

    key: str
    config: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PluginValidationReport:
    """The total validator's verdict for one candidate directory.

    ``loadable`` is a **property**, not a field. Requirement 5.4 requires it be
    derived from the findings and never settable independently; making it a
    field would permit a report whose ``loadable`` and whose findings disagree,
    which is precisely the inconsistency Requirement 5.3 rules out.
    """

    root: Path
    manifest: Optional[PluginManifest] = None
    skills: Tuple[DiscoveredSkill, ...] = ()
    mcp_present: bool = False
    mcp_servers: Tuple[MappedServer, ...] = ()  # always empty in Increment 1
    findings: Tuple[Finding, ...] = ()

    @property
    def loadable(self) -> bool:
        """True if and only if no finding is ``FATAL`` (Requirement 5.3)."""
        return not any(finding.severity is Severity.FATAL for finding in self.findings)

    @property
    def skill_names(self) -> Tuple[str, ...]:
        """Names of the skills discovered as valid, in discovery order."""
        return tuple(skill.name for skill in self.skills)

    def findings_with(self, severity: Severity) -> Tuple[Finding, ...]:
        """All findings of exactly ``severity``."""
        return tuple(finding for finding in self.findings if finding.severity is severity)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize for ``--json`` output and the HTTP API."""
        return {
            "root": str(self.root),
            "loadable": self.loadable,
            "name": self.manifest.name if self.manifest else None,
            "version": self.manifest.version if self.manifest else None,
            "schema_id": self.manifest.schema_id if self.manifest else None,
            "skills": [
                {
                    "name": skill.name,
                    "directory": str(skill.directory),
                    "projected_as": (
                        str(skill.projected_as) if skill.projected_as is not None else None
                    ),
                }
                for skill in self.skills
            ],
            "mcp_present": self.mcp_present,
            "findings": [finding.to_dict() for finding in self.findings],
        }


@dataclass(frozen=True)
class PluginSource:
    """Where a plugin came from, and nothing about how to interpret it."""

    kind: str  # "path" | "git"
    location: str
    ref: Optional[str] = None  # git only: branch, tag, or commit-ish
    subdir: Optional[str] = None  # a subdirectory within the source as the plugin root

    def to_dict(self) -> Dict[str, Any]:
        """Serialize for the install record."""
        return {
            "kind": self.kind,
            "location": self.location,
            "ref": self.ref,
            "subdir": self.subdir,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PluginSource":
        """Rehydrate from a persisted install record."""
        return cls(
            kind=str(data.get("kind", "path")),
            location=str(data.get("location", "")),
            ref=data.get("ref"),
            subdir=data.get("subdir"),
        )


@dataclass(frozen=True)
class PluginRecord:
    """Install record persisted at ``AGENT_PLUGINS_DIR/.state/<name>.json``.

    This is the store's source of truth about *which* plugins are installed.
    ``projected_skill_names`` is a subset of ``skill_names``; every element of
    the difference is explained by a ``SKIPPED`` finding, which is what lets
    ``cao plugin list`` answer "why isn't my skill showing up?" without
    re-running validation.
    """

    name: str
    version: Optional[str] = None
    source: Optional[PluginSource] = None
    resolved_ref: Optional[str] = None  # git commit SHA, when applicable
    installed_at: Optional[datetime] = None
    schema_id: Optional[str] = None
    skill_names: Tuple[str, ...] = ()
    projected_skill_names: Tuple[str, ...] = ()
    findings: Tuple[Finding, ...] = ()

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the record for ``.state/<name>.json``."""
        return {
            "name": self.name,
            "version": self.version,
            "source": self.source.to_dict() if self.source else None,
            "resolved_ref": self.resolved_ref,
            "installed_at": (self.installed_at.isoformat() if self.installed_at else None),
            "schema_id": self.schema_id,
            "skill_names": list(self.skill_names),
            "projected_skill_names": list(self.projected_skill_names),
            "findings": [finding.to_dict() for finding in self.findings],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PluginRecord":
        """Rehydrate a record, tolerating anything a hand-edit may have done.

        A record that cannot be parsed strictly is still better read loosely
        than not at all: the store's callers need "which plugins exist" to keep
        working even if one field was corrupted.
        """
        raw_installed_at = data.get("installed_at")
        installed_at: Optional[datetime] = None
        if isinstance(raw_installed_at, str) and raw_installed_at:
            try:
                installed_at = datetime.fromisoformat(raw_installed_at)
            except ValueError:
                installed_at = None

        raw_source = data.get("source")
        source = PluginSource.from_dict(raw_source) if isinstance(raw_source, dict) else None

        raw_findings = data.get("findings")
        findings: Tuple[Finding, ...] = ()
        if isinstance(raw_findings, list):
            findings = tuple(
                Finding.from_dict(item) for item in raw_findings if isinstance(item, dict)
            )

        return cls(
            name=str(data.get("name", "")),
            version=data.get("version"),
            source=source,
            resolved_ref=data.get("resolved_ref"),
            installed_at=installed_at,
            schema_id=data.get("schema_id"),
            skill_names=_string_tuple(data.get("skill_names")),
            projected_skill_names=_string_tuple(data.get("projected_skill_names")),
            findings=findings,
        )


def _string_tuple(value: Any) -> Tuple[str, ...]:
    """Coerce persisted JSON into a tuple of strings, dropping junk.

    Mirrors ``settings_service``'s defensiveness about hand-edited JSON: a
    ``null`` or a number where a name belongs must not later raise from
    ``Path(...)`` and break plugin listing.
    """
    if not isinstance(value, list):
        return ()
    return tuple(item for item in value if isinstance(item, str) and item)


def utc_now() -> datetime:
    """Timezone-aware current time, so ``installed_at`` round-trips exactly."""
    return datetime.now(timezone.utc)
