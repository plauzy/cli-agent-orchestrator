"""Init command for CLI Agent Orchestrator CLI."""

import errno
import shutil
from importlib import resources
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Dict, List

import click

from cli_agent_orchestrator.clients.database import init_db
from cli_agent_orchestrator.constants import SKILLS_DIR
from cli_agent_orchestrator.services.memory_reconciliation import reconcile_memory_startup

# Skill directories retired by a rename, as ``{old name: new name}``.
#
# PREPARED BUT DELIBERATELY INACTIVE. Decision M4 proposes renaming the
# event-plugin authoring skill ``cao-plugin`` -> ``cao-event-plugin``. A rename is
# not a no-op for an *existing* installation: seeding only ever adds directories,
# so an upgraded install would end up with BOTH ``cao-plugin`` and
# ``cao-event-plugin`` present, and the stale copy would keep appearing in every
# agent's skill catalog forever.
#
# The mechanism below removes the old directory once the new one is in place.
# The mapping is empty because M4 is unresolved and this must not act yet
# (Requirement 21.5). Activating it is one line:
#
#     RETIRED_SKILL_RENAMES = {"cao-plugin": "cao-event-plugin"}
#
# and the matching entry in ``scripts/sync_skills.py``'s ``SHIPPED_SKILLS``.
RETIRED_SKILL_RENAMES: Dict[str, str] = {}


def retire_renamed_skills() -> List[str]:
    """Remove skill directories superseded by a rename. Returns what was removed.

    Only removes ``old`` when ``new`` is actually present, so an interrupted or
    partial upgrade can never leave the user with neither. Best-effort: a
    directory that cannot be removed is logged by the caller's echo and skipped
    rather than failing ``cao init``, because a stale skill is a cosmetic problem
    and a failed init is not.
    """
    if not RETIRED_SKILL_RENAMES:
        return []

    removed: List[str] = []
    for old_name, new_name in sorted(RETIRED_SKILL_RENAMES.items()):
        old_dir = SKILLS_DIR / old_name
        new_dir = SKILLS_DIR / new_name

        # The new skill must exist first; otherwise this would delete the only
        # copy the user has.
        if not (new_dir / "SKILL.md").is_file():
            continue
        if not old_dir.is_dir():
            continue

        try:
            if old_dir.is_symlink():
                old_dir.unlink()
            else:
                shutil.rmtree(old_dir)
            removed.append(old_name)
        except OSError:
            # Left in place; the next `cao init` will try again.
            continue

    return removed


def seed_default_skills() -> int:
    """Seed packaged builtin skills into the local skill store."""
    SKILLS_DIR.mkdir(parents=True, exist_ok=True)
    bundled_skills = resources.files("cli_agent_orchestrator.skills")
    seeded_count = 0

    for skill_dir in bundled_skills.iterdir():
        if not skill_dir.is_dir() or not (skill_dir / "SKILL.md").is_file():
            continue

        destination_dir = SKILLS_DIR / skill_dir.name
        if destination_dir.exists():
            continue

        with resources.as_file(skill_dir) as source_dir:
            with TemporaryDirectory(
                prefix=f".{skill_dir.name}.",
                dir=SKILLS_DIR,
            ) as staging_root:
                staged_dir = Path(staging_root) / skill_dir.name
                shutil.copytree(Path(source_dir), staged_dir)
                try:
                    staged_dir.rename(destination_dir)
                except OSError as exc:
                    if exc.errno in (errno.EEXIST, errno.ENOTEMPTY) and destination_dir.exists():
                        continue
                    raise
        seeded_count += 1

    # Retirement runs AFTER seeding so the replacement skill is already present
    # when the superseded one is removed. Inert until M4 is resolved.
    retire_renamed_skills()

    return seeded_count


@click.command()
def init():
    """Initialize CLI Agent Orchestrator database."""
    try:
        init_db()
        repair_report = reconcile_memory_startup()
        seeded_count = seed_default_skills()
        if repair_report is not None:
            click.echo(repair_report.summary_text())
        click.echo(
            f"CLI Agent Orchestrator initialized successfully. "
            f"Seeded {seeded_count} builtin skills."
        )
    except Exception as e:
        raise click.ClickException(str(e))
