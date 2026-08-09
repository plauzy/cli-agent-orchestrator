"""Agent plugin management commands (agent-plugins.org 1.0.0).

Structured as a direct sibling of ``cli/commands/skills.py``: same
``click.group()`` shape, same ``raise click.ClickException(str(exc))`` error
convention, same post-mutation refresh behaviour. An operator who knows
``cao skills`` should not have to learn a second idiom.

Naming is not settled (decision **M1**)
---------------------------------------
The verb is exposed here as ``cao plugin``, which design.md records as the
recommended option, with ``cao agent-plugin`` as the alternative. **M1 is
unresolved**, so this surface is built and tested but must not ship to end users
until maintainers record the decision (Requirement 16.4, 16.5). Two things
enforce that rather than leaving it to memory:

* the group is registered ``hidden=True``, so it does not appear in ``cao
  --help``;
* the TUI catalog classifies all four leaves ``Policy::Hidden``, which is also
  what that catalog's own rule requires of any newly added command.

Renaming the verb later is a one-line change here plus the matching
``leaf_name``/``parent`` edits in ``tui/src/catalog.rs``.

These commands are **not** the event-plugin surface. ``cao.plugins`` entry
points and ``PluginRegistry`` are unrelated and untouched (decision D7).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import click

from cli_agent_orchestrator.agent_plugins import installer, projection, provenance
from cli_agent_orchestrator.agent_plugins.models import Severity
from cli_agent_orchestrator.agent_plugins.resolver import detect_source
from cli_agent_orchestrator.agent_plugins.store import InstalledPluginStore
from cli_agent_orchestrator.agent_plugins.validation import validate_plugin

# Requirement 22.1: the CLI must state, at or before the point of install, that
# installing a plugin runs untrusted code and content. Stated plainly rather
# than softened -- CAO implements no trust model, no signing, and no provenance
# verification for agent plugins, and saying so is the only honest posture.
UNTRUSTED_CONTENT_WARNING = (
    "Installing an agent plugin runs untrusted code and content from that "
    "source. CAO does not verify plugin authorship or integrity: there is no "
    "signing and no provenance check. Only install plugins from sources you "
    "trust."
)


def _severity_rank(severity: Severity) -> int:
    """Order findings worst-first for human output."""
    order = {Severity.FATAL: 0, Severity.SKIPPED: 1, Severity.WARNING: 2, Severity.INFO: 3}
    return order.get(severity, 4)


def _echo_findings(findings, indent: str = "  ") -> None:
    """Render findings worst-first, citing the clause each one enforces."""
    for finding in sorted(findings, key=lambda item: _severity_rank(item.severity)):
        click.echo(
            f"{indent}{finding.severity.value.upper():<8} "
            f"{finding.code} ({finding.spec_ref}): {finding.message}"
        )


@click.group(hidden=True)
def plugin() -> None:
    """Manage agent plugins (agent-plugins.org).

    Hidden pending decision M1 on the command verb. Not for end users yet.
    """


@plugin.command("add")
@click.argument("source")
@click.option("--ref", "ref", default=None, help="Git branch, tag, or commit to install from.")
@click.option(
    "--subdir",
    default=None,
    help="Subdirectory within the source to treat as the plugin root.",
)
@click.option("--force", is_flag=True, help="Replace an already-installed plugin of the same name.")
@click.option(
    "--dry-run",
    is_flag=True,
    help="Resolve and validate only; install nothing.",
)
def add(source: str, ref: Optional[str], subdir: Optional[str], force: bool, dry_run: bool) -> None:
    """Install an agent plugin from a local path or a git repository."""
    # Requirement 22.1: before anything is resolved or published.
    click.echo(UNTRUSTED_CONTENT_WARNING, err=True)

    try:
        plugin_source = detect_source(source, ref=ref, subdir=subdir)
        outcome = installer.install(plugin_source, force=force, dry_run=dry_run)
    except Exception as exc:
        raise click.ClickException(str(exc)) from exc

    report = outcome.report
    name = report.manifest.name if report.manifest else source

    if not report.loadable:
        click.echo(f"Plugin at '{source}' is not loadable:")
        _echo_findings(report.findings)
        # Nothing was published; the installed set is unchanged.
        raise click.ClickException("plugin validation failed; nothing was installed")

    if dry_run:
        click.echo(f"Plugin '{name}' is valid ({len(report.skills)} skill(s)); nothing installed")
        if report.findings:
            _echo_findings(report.findings)
        return

    click.echo(f"Plugin '{name}' installed successfully")
    projected = outcome.projected_skill_names
    if projected:
        click.echo(f"Projected {len(projected)} skill(s): {', '.join(projected)}")
    else:
        click.echo("No skills were projected")

    # Non-fatal findings matter here: they explain why a skill the plugin ships
    # is not available.
    non_fatal = [f for f in outcome.findings if f.severity is not Severity.FATAL]
    if non_fatal:
        click.echo("Findings:")
        _echo_findings(non_fatal)

    if outcome.refreshed_agents:
        click.echo(f"Refreshed {outcome.refreshed_agents} installed agent(s)")


@plugin.command("list")
@click.option("--json", "as_json", is_flag=True, help="Emit a machine-readable report.")
def list_command(as_json: bool) -> None:
    """List installed agent plugins."""
    try:
        store = InstalledPluginStore()
        # Design: the dangling-link sweep runs on projection rebuild AND on
        # `plugin list`, so simply looking at the store repairs stale links.
        # It never raises.
        swept = projection.sweep_dangling(store)
        records = store.list_installed()
        owners = provenance.projected_skills(store)
    except Exception as exc:
        raise click.ClickException(str(exc)) from exc

    if as_json:
        payload: Dict[str, Any] = {
            "plugins": [_record_to_dict(record, owners) for record in records],
            "swept": list(swept),
        }
        click.echo(json.dumps(payload, indent=2))
        return

    # Reported before the empty-store shortcut: an operator who runs this
    # command specifically to clear stale links must still be told what it did,
    # and the store being empty is exactly when that happens.
    if swept:
        click.echo(f"Swept {len(swept)} dangling projected skill link(s): {', '.join(swept)}")

    if not records:
        click.echo("No agent plugins installed")
        return

    click.echo(f"{'Name':<32} {'Version':<12} {'Skills'}")
    click.echo("-" * 100)
    for record in records:
        projected = [skill for skill, owner in sorted(owners.items()) if owner == record.name]
        click.echo(
            f"{record.name:<32} {(record.version or '-'):<12} "
            f"{', '.join(projected) if projected else '-'}"
        )

    for record in records:
        non_fatal = [f for f in record.findings if f.severity is not Severity.FATAL]
        if non_fatal:
            click.echo(f"\n{record.name}:")
            _echo_findings(non_fatal)


def _record_to_dict(record, owners: Dict[str, str]) -> Dict[str, Any]:
    """Serialize an install record for ``--json``."""
    return {
        "name": record.name,
        "version": record.version,
        "schema_id": record.schema_id,
        "source": record.source.to_dict() if record.source else None,
        "resolved_ref": record.resolved_ref,
        "installed_at": record.installed_at.isoformat() if record.installed_at else None,
        "skill_names": list(record.skill_names),
        "projected_skill_names": sorted(
            skill for skill, owner in owners.items() if owner == record.name
        ),
        "findings": [finding.to_dict() for finding in record.findings],
    }


@plugin.command("remove")
@click.argument("name")
@click.option("--purge-data", is_flag=True, help="Also delete the plugin's persistent data.")
@click.option("--yes", is_flag=True, help="Skip the confirmation prompt.")
def remove(name: str, purge_data: bool, yes: bool) -> None:
    """Remove an installed agent plugin."""
    try:
        store = InstalledPluginStore()
        if store.get(name) is None:
            raise FileNotFoundError(f"Agent plugin '{name}' is not installed.")

        owned, affected = installer.removal_impact(name, store)
    except click.ClickException:
        raise
    except Exception as exc:
        raise click.ClickException(str(exc)) from exc

    # Requirements 15.1-15.3: warn, require confirmation, never refuse. Removal
    # is not symmetric with install because Kiro and OpenCode read SKILL.md from
    # disk mid-session, so this can pull a skill out from under a running agent.
    if affected and not yes:
        click.echo(
            f"Removing '{name}' affects {len(affected)} live terminal(s) that can "
            f"reach the skill(s) it provides:"
        )
        for session in affected:
            click.echo(
                f"  session {session.session_name} terminal {session.terminal_id} "
                f"({session.provider}"
                + (f", profile {session.agent_profile}" if session.agent_profile else "")
                + f"): {', '.join(session.skill_names)}"
            )
        click.echo("Those agents may attempt to load a skill that no longer resolves.")
        if not click.confirm("Remove anyway?", default=False):
            click.echo("Aborted; nothing was removed")
            return

    if purge_data and not yes:
        if not click.confirm(
            f"--purge-data will permanently delete '{name}' persistent data. Continue?",
            default=False,
        ):
            click.echo("Aborted; nothing was removed")
            return

    try:
        outcome = installer.uninstall(name, purge_data=purge_data)
    except Exception as exc:
        raise click.ClickException(str(exc)) from exc

    click.echo(f"Agent plugin '{name}' removed successfully")
    if owned:
        click.echo(f"Withdrew {len(owned)} projected skill(s): {', '.join(owned)}")
    if purge_data:
        click.echo("Deleted its persistent plugin data")
    if outcome.refreshed_agents:
        click.echo(f"Refreshed {outcome.refreshed_agents} installed agent(s)")


@plugin.command("validate")
@click.argument("path", type=click.Path(path_type=Path))
@click.option("--json", "as_json", is_flag=True, help="Emit a machine-readable report.")
@click.pass_context
def validate(ctx: click.Context, path: Path, as_json: bool) -> None:
    """Validate a candidate plugin directory without installing it."""
    try:
        report = validate_plugin(path)
    except Exception as exc:  # pragma: no cover - validate_plugin is total
        raise click.ClickException(str(exc)) from exc

    if as_json:
        click.echo(json.dumps(report.to_dict(), indent=2))
    else:
        name = report.manifest.name if report.manifest else "(unknown)"
        click.echo(f"Plugin:   {name}")
        click.echo(f"Root:     {report.root}")
        click.echo(f"Loadable: {'yes' if report.loadable else 'no'}")
        click.echo(f"Skills:   {', '.join(report.skill_names) if report.skills else '(none)'}")
        click.echo(
            f"MCP:      {'present (unsupported in this version)' if report.mcp_present else 'absent'}"
        )
        if report.findings:
            click.echo("Findings:")
            _echo_findings(report.findings)

    # Non-zero exit on an unloadable plugin, so CI and scripts can gate on it.
    if not report.loadable:
        ctx.exit(1)
