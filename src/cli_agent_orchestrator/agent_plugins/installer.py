"""Sequence resolve -> validate -> publish -> project.

The ordering is load-bearing, not stylistic. Validating the **staged copy**
before anything is published is what makes "a failed install changes nothing"
(Requirement 9.2, property P4) a structural guarantee rather than a cleanup
routine that might itself fail halfway.

    1. Resolve the source into staging.
    2. Validate the staged copy. Not loadable -> return the report, publish
       nothing.
    3. Refuse a name collision unless ``force`` (mirrors ``cao skills add``).
    4. Publish atomically (stage -> rename).
    5. Rebuild the projection.
    6. Refresh baked provider artifacts via the **existing**
       ``skill_injection.refresh_all_cao_managed_agents()``. Skipping this would
       leave Copilot's ``.agent.md`` catalogs stale -- it is the one delivery
       path baked at install time rather than read at launch.
    7. Write the install record.

Removal is not symmetric with install, because two providers read ``SKILL.md``
from disk mid-session (Kiro's ``skill://`` glob and OpenCode's ``skills``
symlink). Neither snapshots content at launch, so removing a plugin can pull a
skill out from under an agent that is currently mid-task. ``affected_sessions()``
exists so the operator is told; it **warns and never refuses** (Requirement
15.3), because blocking removal on any live session would make the store
un-cleanable while a long session runs.
"""

from __future__ import annotations

import fnmatch
import logging
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

from cli_agent_orchestrator.agent_plugins.models import (
    Finding,
    PluginRecord,
    PluginSource,
    PluginValidationReport,
    Severity,
    utc_now,
)
from cli_agent_orchestrator.agent_plugins.projection import ProjectionOutcome, rebuild_projection
from cli_agent_orchestrator.agent_plugins.resolver import resolve
from cli_agent_orchestrator.agent_plugins.store import InstalledPluginStore
from cli_agent_orchestrator.agent_plugins.validation import validate_plugin

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class InstallOutcome:
    """Result of an install attempt."""

    installed: bool
    report: PluginValidationReport
    record: Optional[PluginRecord] = None
    projection: Optional[ProjectionOutcome] = None
    dry_run: bool = False
    refreshed_agents: int = 0

    @property
    def findings(self) -> Tuple[Finding, ...]:
        """Validation findings plus any raised by the projection rebuild."""
        projection_findings = self.projection.findings if self.projection else ()
        return tuple(self.report.findings) + tuple(projection_findings)

    @property
    def projected_skill_names(self) -> Tuple[str, ...]:
        """Skills this install actually made available."""
        if self.projection is None or self.record is None:
            return ()
        return self.projection.skills_for(self.record.name)


@dataclass(frozen=True)
class UninstallOutcome:
    """Result of a removal."""

    name: str
    removed: bool
    purged_data: bool = False
    projection: Optional[ProjectionOutcome] = None
    refreshed_agents: int = 0


@dataclass(frozen=True)
class AffectedSession:
    """A live terminal whose agent can reach a skill that is about to vanish."""

    terminal_id: str
    session_name: str
    provider: str
    agent_profile: Optional[str]
    skill_names: Tuple[str, ...] = field(default_factory=tuple)


class PluginInstallError(RuntimeError):
    """An install or removal could not be completed."""


def install(
    source: PluginSource,
    *,
    force: bool = False,
    dry_run: bool = False,
    store: Optional[InstalledPluginStore] = None,
    skills_dir: Optional[Path] = None,
    refresh_agents: bool = True,
) -> InstallOutcome:
    """Install ``source``, or with ``dry_run`` only resolve and validate it.

    ``dry_run`` is exactly what ``cao plugin validate`` and CI use: it performs
    steps 1-2 and reports, touching no persistent state.

    Raises:
        PluginResolutionError: the source is unreachable.
        PluginInstallError: the name is taken and ``force`` was not given.
    """
    store = store if store is not None else InstalledPluginStore()

    # Staging lives beside the store so the publish rename is same-filesystem,
    # and is dot-prefixed so list_installed() ignores it if we die mid-flight.
    store.plugins_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix=".staging.", dir=str(store.plugins_dir)
    ) as staging_root:
        staging = Path(staging_root) / "package"

        resolved = resolve(source, staging)
        report = validate_plugin(resolved.root)

        if not report.loadable or report.manifest is None:
            # Nothing has been published; the installed set is untouched.
            return InstallOutcome(installed=False, report=report, dry_run=dry_run)

        if dry_run:
            return InstallOutcome(installed=False, report=report, dry_run=True)

        name = report.manifest.name
        if store.get(name) is not None and not force:
            raise PluginInstallError(
                f"Plugin '{name}' is already installed. Use --force to replace it."
            )

        record = PluginRecord(
            name=name,
            version=report.manifest.version,
            source=source,
            resolved_ref=resolved.resolved_ref,
            installed_at=utc_now(),
            schema_id=report.manifest.schema_id,
            skill_names=report.skill_names,
            projected_skill_names=(),  # filled in after the rebuild below
            findings=tuple(report.findings),
        )
        store.publish(resolved.root, record, force=force)

    projection = rebuild_projection(store, skills_dir=skills_dir)

    # Persist what was actually projected, so `cao plugin list` can explain why
    # a skill the plugin ships is not showing up.
    record = PluginRecord(
        name=record.name,
        version=record.version,
        source=record.source,
        resolved_ref=record.resolved_ref,
        installed_at=record.installed_at,
        schema_id=record.schema_id,
        skill_names=record.skill_names,
        projected_skill_names=projection.skills_for(record.name),
        findings=record.findings + projection.findings,
    )
    store.write_record(record)

    refreshed = _refresh_baked_provider_artifacts() if refresh_agents else 0

    return InstallOutcome(
        installed=True,
        report=report,
        record=record,
        projection=projection,
        refreshed_agents=refreshed,
    )


def uninstall(
    name: str,
    *,
    purge_data: bool = False,
    store: Optional[InstalledPluginStore] = None,
    skills_dir: Optional[Path] = None,
    refresh_agents: bool = True,
) -> UninstallOutcome:
    """Remove ``name``, restoring the pre-install store state.

    ``purge_data`` defaults to ``False``: §9.1 permits either, and CAO's rule is
    explicit so idempotence is decidable (Requirements 10.2-10.4).

    Removing something absent succeeds with ``removed=False`` rather than
    raising, so a repeated removal is not an error.
    """
    store = store if store is not None else InstalledPluginStore()

    was_installed = store.get(name) is not None
    store.unpublish(name, purge_data=purge_data)

    # Rebuilt even when nothing was installed: the rebuild is also the sweep,
    # and a stale projection is exactly what a repeated removal should clear.
    projection = rebuild_projection(store, skills_dir=skills_dir)
    refreshed = _refresh_baked_provider_artifacts() if refresh_agents else 0

    return UninstallOutcome(
        name=name,
        removed=was_installed,
        purged_data=purge_data,
        projection=projection,
        refreshed_agents=refreshed,
    )


def _refresh_baked_provider_artifacts() -> int:
    """Re-bake Copilot ``.agent.md`` catalogs, best-effort.

    Wrapped exactly as ``cli/commands/skills.py::_refresh_installed_agents``
    wraps it: a failure to refresh a provider artifact must not fail the install
    that already succeeded.
    """
    try:
        from cli_agent_orchestrator.utils.skill_injection import refresh_all_cao_managed_agents

        return len(refresh_all_cao_managed_agents())
    except Exception as exc:
        logger.warning("Failed to refresh installed agent prompts: %s", exc)
        return 0


# ---------------------------------------------------------------------------
# Removal safety
# ---------------------------------------------------------------------------

# Providers that receive a skill catalog filtered by the profile's `skills`
# allowlist at launch. Every OTHER provider reaches the whole of SKILLS_DIR --
# Kiro through its `skill://` glob, OpenCode through its `skills` symlink,
# Copilot through a fully baked catalog -- so for those, profile-level scoping
# tells us nothing and any projected skill must be treated as reachable.
_FILTERED_CATALOG_PROVIDERS = frozenset({"claude_code", "codex", "kimi_cli", "antigravity_cli"})


def affected_sessions(skill_names: Sequence[str]) -> List[AffectedSession]:
    """Live terminals that can reach any of ``skill_names``.

    Never raises. This informs a warning, so every failure mode — no database
    yet, no tmux server, an unreadable agent profile — must degrade to "nothing
    known to be affected" rather than blocking a removal the operator asked for.

    Deliberately reads services directly rather than over HTTP: unlike
    ``cao session list``, this must still work (and report *nothing* affected)
    when no ``cao-server`` is running, and a ``ConnectionError`` is not a
    reason to refuse a removal.
    """
    wanted = {name for name in skill_names if name}
    if not wanted:
        return []

    try:
        from cli_agent_orchestrator.clients import database
        from cli_agent_orchestrator.services import session_service
    except Exception as exc:  # pragma: no cover - import-time environment issue
        logger.debug("Cannot inspect live sessions: %s", exc)
        return []

    try:
        live_sessions = {session["id"] for session in session_service.list_sessions()}
    except Exception as exc:
        logger.debug("Could not list live sessions: %s", exc)
        return []
    if not live_sessions:
        return []

    try:
        terminals = database.list_all_terminals()
    except Exception as exc:
        logger.debug("Could not list terminals: %s", exc)
        return []

    affected: List[AffectedSession] = []
    for terminal in terminals:
        session_name = terminal.get("tmux_session")
        if session_name not in live_sessions:
            continue  # a stale database row for a session that is gone

        provider = str(terminal.get("provider") or "")
        profile_name = terminal.get("agent_profile")
        reachable = _reachable_skills(provider, profile_name, wanted)
        if not reachable:
            continue

        affected.append(
            AffectedSession(
                terminal_id=str(terminal.get("id") or ""),
                session_name=str(session_name or ""),
                provider=provider,
                agent_profile=profile_name,
                skill_names=tuple(sorted(reachable)),
            )
        )
    return affected


def _reachable_skills(provider: str, profile_name: Optional[str], wanted: set) -> set:
    """Which of ``wanted`` this terminal's agent can reach."""
    if provider not in _FILTERED_CATALOG_PROVIDERS:
        # Kiro / OpenCode / Copilot see the whole skill store.
        return set(wanted)

    if not profile_name:
        return set(wanted)

    try:
        from cli_agent_orchestrator.utils.agent_profiles import load_agent_profile

        profile = load_agent_profile(profile_name)
    except Exception as exc:
        # An unreadable profile means we cannot prove the skill is unreachable,
        # and under-warning is the worse failure here.
        logger.debug("Could not load agent profile %r: %s", profile_name, exc)
        return set(wanted)

    patterns = getattr(profile, "skills", None)
    if patterns is None:
        return set(wanted)  # None means the full catalog
    if not patterns:
        return set()  # [] means no skills advertised

    return {
        name for name in wanted if any(fnmatch.fnmatchcase(name, pattern) for pattern in patterns)
    }


def removal_impact(
    name: str, store: Optional[InstalledPluginStore] = None
) -> Tuple[Tuple[str, ...], List[AffectedSession]]:
    """Skills ``name`` currently projects, and the live terminals reaching them.

    The pair the CLI and the API both need to render a confirmation prompt.
    """
    store = store if store is not None else InstalledPluginStore()

    from cli_agent_orchestrator.agent_plugins.provenance import projected_skills

    owned = tuple(
        sorted(skill for skill, owner in projected_skills(store).items() if owner == name)
    )
    if not owned:
        record = store.get(name)
        if record is not None:
            owned = record.projected_skill_names

    return owned, affected_sessions(owned)
