"""Materialize plugin skills into the existing global skill store.

Why projection at all
---------------------
CAO delivers skills through several independent mechanisms, and two of them read
``SKILLS_DIR`` **as a literal path**: Kiro CLI receives one
``skill://{SKILLS_DIR}/**/SKILL.md`` glob baked into its agent JSON, and OpenCode
gets a single ``skills`` symlink to ``SKILLS_DIR``. Registering plugin skill
roots as extra search directories would cover the catalog-based providers but
would be invisible to both of those. Materializing each plugin skill *inside*
``SKILLS_DIR`` instead means every existing delivery path — ``list_skills()``,
``build_skill_catalog()``, ``compose_agent_prompt()``, the ``load_skill`` MCP
tool, Kiro's glob, OpenCode's symlink — works unmodified, with zero
provider-specific code.

The link is named with the **unprefixed** skill name. Namespacing it is not an
option: ``utils/skills.py::_load_skill_folder`` requires the folder name to equal
the frontmatter ``name``, and §4.1's posture forbids CAO rewriting a
PLUGIN_ROOT's bytes to match a prefixed folder.

Projection is derived state
---------------------------
It is rebuilt from scratch on every add/remove rather than patched incrementally
(Requirement 13.3), which is what makes the collision winner a pure function of
*which* plugins are installed rather than of *how they got there*.

Collision rules, in priority order
----------------------------------
1. A pre-existing built-in or user-added skill of the same name **always wins**.
   Projection is skipped and reported; the existing skill keeps resolving.
2. Among competing plugins, the **lexicographically smallest manifest name**
   wins. Deliberately not ``installed_at``: that encodes install *order*, so
   installing A-then-B and B-then-A would elect different winners from the same
   final installed set, and same-second installs would tie and fall back to scan
   order anyway.
3. When a rebuild reassigns an already-projected skill to a different plugin, a
   ``WARNING`` names both the previous and the new winner — a silently changed
   content source is not something a ``SKIPPED`` finding on the loser
   communicates.
"""

from __future__ import annotations

import logging
import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from cli_agent_orchestrator.agent_plugins.containment import is_within, realpath
from cli_agent_orchestrator.agent_plugins.models import Finding, Severity
from cli_agent_orchestrator.agent_plugins.store import InstalledPluginStore
from cli_agent_orchestrator.agent_plugins.validation import SKILLS_DIRNAME, validate_plugin
from cli_agent_orchestrator.constants import SKILLS_DIR

logger = logging.getLogger(__name__)

PROJECTION_MODE_SYMLINK = "symlink"
PROJECTION_MODE_COPY = "copy"


@dataclass(frozen=True)
class ProjectionOutcome:
    """Result of one projection rebuild."""

    # skill name -> owning plugin name, for everything actually materialized.
    projected: Dict[str, str] = field(default_factory=dict)
    findings: Tuple[Finding, ...] = ()
    mode: str = PROJECTION_MODE_SYMLINK
    swept: Tuple[str, ...] = ()  # dangling projections removed this pass

    def skills_for(self, plugin_name: str) -> Tuple[str, ...]:
        """Skill names this rebuild projected on behalf of ``plugin_name``."""
        return tuple(
            sorted(skill for skill, owner in self.projected.items() if owner == plugin_name)
        )


def _finding(
    severity: Severity, code: str, spec_ref: str, message: str, path: Optional[str] = None
) -> Finding:
    return Finding(severity=severity, code=code, spec_ref=spec_ref, message=message, path=path)


def _resolve_mode(mode: Optional[str]) -> str:
    """Determine the projection mode, defaulting through settings."""
    if mode in (PROJECTION_MODE_SYMLINK, PROJECTION_MODE_COPY):
        return mode  # type: ignore[return-value]
    try:
        from cli_agent_orchestrator.services.settings_service import get_skill_projection_mode

        return get_skill_projection_mode()
    except Exception as exc:  # pragma: no cover - settings must never block install
        logger.warning("Could not read skill projection mode, using symlink: %s", exc)
        return PROJECTION_MODE_SYMLINK


def _collect_claims(
    store: InstalledPluginStore,
) -> Tuple[Dict[str, List[Tuple[str, Path]]], List[Finding]]:
    """Map each skill name to the plugins claiming it.

    Each installed plugin is re-validated rather than trusted from its install
    record, so the projection reflects what is actually on disk: a plugin whose
    bytes were corrupted or hand-edited after install cannot project skills that
    would now fail validation. This is affordable because rebuilds happen on
    add/remove, never on the terminal-launch path (Requirement 13.5).
    """
    claims: Dict[str, List[Tuple[str, Path]]] = {}
    findings: List[Finding] = []

    # Sorted by plugin name so the whole computation is a total order over
    # persisted state, never over directory scan order (Requirement 14.5).
    for record in sorted(store.list_installed(), key=lambda item: item.name):
        try:
            root = store.plugin_root(record.name)
        except ValueError:
            continue
        report = validate_plugin(root)
        if not report.loadable:
            findings.append(
                _finding(
                    Severity.SKIPPED,
                    "projection.plugin_unloadable",
                    "§11.3",
                    f"plugin {record.name!r} is installed but no longer loadable; "
                    f"projecting none of its skills",
                    record.name,
                )
            )
            continue
        for skill in report.skills:
            claims.setdefault(skill.name, []).append((record.name, skill.directory))

    return claims, findings


def _managed_names(skills_dir: Path, plugins_dir: Path, ledger: Dict[str, str]) -> set:
    """Names in ``skills_dir`` that CAO's projection owns.

    The ledger is authoritative because in copy mode a projected skill is an
    ordinary directory with nothing to distinguish it. Symlinks pointing into the
    plugin store are additionally treated as managed so a lost ledger still
    self-heals instead of orphaning links forever.
    """
    managed = set(ledger)
    plugins_real = realpath(plugins_dir)
    if plugins_real is None or not skills_dir.is_dir():
        return managed

    try:
        entries = list(skills_dir.iterdir())
    except OSError:
        return managed

    for entry in entries:
        if not entry.is_symlink():
            continue
        target = realpath(entry)
        if target is not None and is_within(plugins_real, target):
            managed.add(entry.name)
    return managed


def rebuild_projection(
    store: Optional[InstalledPluginStore] = None,
    *,
    skills_dir: Optional[Path] = None,
    mode: Optional[str] = None,
) -> ProjectionOutcome:
    """Rebuild the whole projection from the installed set.

    Idempotent: running it twice against an unchanged installed set produces an
    identical result and leaves the filesystem unchanged the second time.
    """
    store = store if store is not None else InstalledPluginStore()
    target_dir = Path(skills_dir) if skills_dir is not None else SKILLS_DIR
    resolved_mode = _resolve_mode(mode)

    findings: List[Finding] = []
    claims, claim_findings = _collect_claims(store)
    findings.extend(claim_findings)

    previous = store.read_projection()
    managed = _managed_names(target_dir, store.plugins_dir, previous)

    # Sweep first, so a dangling projection cannot be mistaken for a
    # pre-existing skill that would then beat every plugin claiming that name.
    swept = _sweep_dangling(target_dir, managed)

    target_dir.mkdir(parents=True, exist_ok=True)
    try:
        existing = {entry.name for entry in target_dir.iterdir()}
    except OSError as exc:
        logger.warning("Could not enumerate %s: %s", target_dir, exc)
        existing = set()

    # Rule 1 and 2: elect a winner per skill name.
    winners: Dict[str, Tuple[str, Path]] = {}
    for skill_name in sorted(claims):
        claimants = sorted(claims[skill_name], key=lambda item: item[0])

        # A pre-existing, non-managed entry always wins.
        if skill_name in existing and skill_name not in managed:
            for plugin_name, _ in claimants:
                findings.append(
                    _finding(
                        Severity.SKIPPED,
                        "projection.preexisting_skill",
                        "§7.1",
                        f"not projecting skill {skill_name!r} from plugin "
                        f"{plugin_name!r}: a built-in or user-added skill of that "
                        f"name already exists and keeps precedence",
                        skill_name,
                    )
                )
            continue

        winner_name, winner_dir = claimants[0]
        winners[skill_name] = (winner_name, winner_dir)

        for loser_name, _ in claimants[1:]:
            findings.append(
                _finding(
                    Severity.SKIPPED,
                    "projection.plugin_collision",
                    "§7.1",
                    f"not projecting skill {skill_name!r} from plugin {loser_name!r}: "
                    f"plugin {winner_name!r} provides the same skill name and wins "
                    f"(lexicographically smallest plugin name)",
                    skill_name,
                )
            )

        # Rule 3: an already-projected skill changing hands is observable.
        prior_owner = previous.get(skill_name)
        if prior_owner is not None and prior_owner != winner_name:
            findings.append(
                _finding(
                    Severity.WARNING,
                    "projection.winner_changed",
                    "§7.1",
                    f"skill {skill_name!r} now resolves to plugin {winner_name!r}; "
                    f"it previously resolved to plugin {prior_owner!r}",
                    skill_name,
                )
            )

    # Retire managed entries that no longer win anything.
    for stale in sorted(managed - set(winners)):
        _remove_projection(target_dir / stale)

    projected: Dict[str, str] = {}
    for skill_name in sorted(winners):
        plugin_name, source_dir = winners[skill_name]
        materialize_finding = _materialize(
            target_dir / skill_name, source_dir, resolved_mode, skill_name, plugin_name
        )
        if materialize_finding is not None:
            findings.append(materialize_finding)
            if materialize_finding.severity is Severity.SKIPPED:
                continue
        projected[skill_name] = plugin_name

    store.write_projection(projected)

    return ProjectionOutcome(
        projected=projected,
        findings=tuple(findings),
        mode=resolved_mode,
        swept=tuple(swept),
    )


def _materialize(
    link_path: Path, source_dir: Path, mode: str, skill_name: str, plugin_name: str
) -> Optional[Finding]:
    """Create the projection for one skill. Returns a finding, if any."""
    _remove_projection(link_path)

    if mode == PROJECTION_MODE_SYMLINK:
        try:
            link_path.symlink_to(source_dir, target_is_directory=True)
            return None
        except OSError as exc:
            # Windows without Developer Mode or elevation. Fall back for this
            # skill rather than failing the install (Requirement 13.4), and
            # report the fallback so it is not silent.
            logger.warning("Symlink projection unsupported for %s: %s", skill_name, exc)
            copy_finding = _copy_projection(link_path, source_dir, skill_name, plugin_name)
            if copy_finding is not None:
                return copy_finding
            return _finding(
                Severity.WARNING,
                "projection.symlink_unsupported",
                "§7.1",
                f"symlink creation is unsupported here; copied skill "
                f"{skill_name!r} from plugin {plugin_name!r} instead",
                skill_name,
            )

    return _copy_projection(link_path, source_dir, skill_name, plugin_name)


def _copy_projection(
    link_path: Path, source_dir: Path, skill_name: str, plugin_name: str
) -> Optional[Finding]:
    """Copy a skill's content into the skill store."""
    try:
        shutil.copytree(source_dir, link_path, symlinks=True)
        return None
    except OSError as exc:
        return _finding(
            Severity.SKIPPED,
            "projection.failed",
            "§7.1",
            f"could not project skill {skill_name!r} from plugin " f"{plugin_name!r}: {exc}",
            skill_name,
        )


def _remove_projection(path: Path) -> bool:
    """Remove a managed projection entry, best-effort.

    Never raises. A projection CAO cannot remove is logged and left alone; the
    alternative — propagating the error — would let a permission problem on one
    stale link abort an entire install or removal.
    """
    try:
        if path.is_symlink() or path.is_file():
            path.unlink()
            return True
        if path.is_dir():
            shutil.rmtree(path)
            return True
    except OSError as exc:
        logger.warning("Could not remove projected skill '%s': %s", path, exc)
    return False


def sweep_dangling(
    store: Optional[InstalledPluginStore] = None, *, skills_dir: Optional[Path] = None
) -> Tuple[str, ...]:
    """Remove projections whose target no longer exists.

    Safe to call concurrently with terminal creation, which is the whole point:
    ``list_skills()`` gates on ``is_dir()`` and ``SKILL.md is_file()``, both
    ``False`` (not an exception) for a broken link, so a dangling projection is
    simply not enumerated. This sweep holds itself to the same never-raise
    discipline (Requirements 15.4, 15.5).
    """
    store = store if store is not None else InstalledPluginStore()
    target_dir = Path(skills_dir) if skills_dir is not None else SKILLS_DIR
    try:
        managed = _managed_names(target_dir, store.plugins_dir, store.read_projection())
        return tuple(_sweep_dangling(target_dir, managed))
    except Exception as exc:  # pragma: no cover - never-raise backstop
        logger.warning("Projection sweep failed: %s", exc)
        return ()


def _sweep_dangling(skills_dir: Path, managed: set) -> List[str]:
    """Unlink dangling managed projections; log and continue on failure."""
    if not skills_dir.is_dir():
        return []

    swept: List[str] = []
    for name in sorted(managed):
        path = skills_dir / name
        try:
            if not path.is_symlink():
                continue
            # os.path.exists follows the link: False means the target is gone.
            if os.path.exists(path):
                continue
        except OSError as exc:
            logger.warning("Could not inspect projected skill '%s': %s", path, exc)
            continue

        try:
            path.unlink()
            swept.append(name)
        except OSError as exc:
            # Requirement 15.5: log and keep going, never halt the sweep.
            logger.warning("Could not remove dangling projected skill '%s': %s", path, exc)
    return swept
