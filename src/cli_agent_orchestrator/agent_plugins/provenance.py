"""Which plugin, if any, provides a given skill.

Projection deliberately names a link with the *unprefixed* skill name, so a
projected skill is indistinguishable from a built-in one by name alone. That is
the price of keeping every existing delivery path working unchanged, and this
module is how the information is recovered for display: ``cao plugin list``, the
web panel, and the ``cao skills list`` annotation.

``SkillMetadata`` is deliberately **not** extended. It models ``SKILL.md``
frontmatter, and provenance is not frontmatter — putting it there would imply
plugin authors write it.

Read-only by construction: nothing here mutates the store or the projection.
"""

from __future__ import annotations

import logging
from typing import Dict, Optional

from cli_agent_orchestrator.agent_plugins.store import InstalledPluginStore

logger = logging.getLogger(__name__)


def projected_skills(store: Optional[InstalledPluginStore] = None) -> Dict[str, str]:
    """Map every projected skill name to its owning plugin name.

    The projection ledger is consulted first because it records what is
    *actually* materialized right now. Install records are a fallback: they say
    what each plugin projected at its own install time, which can lag a
    subsequent rebuild that reassigned a collision winner.
    """
    store = store if store is not None else InstalledPluginStore()

    try:
        ledger = store.read_projection()
    except Exception as exc:  # pragma: no cover - read_projection is already total
        logger.warning("Could not read projection ledger: %s", exc)
        ledger = {}
    if ledger:
        return dict(ledger)

    owners: Dict[str, str] = {}
    try:
        records = store.list_installed()
    except Exception as exc:
        logger.warning("Could not list installed plugins: %s", exc)
        return owners

    # Sorted by name so a stale-record conflict resolves the same way the
    # projection engine would: lexicographically smallest plugin name wins.
    for record in sorted(records, key=lambda item: item.name):
        for skill_name in record.projected_skill_names:
            owners.setdefault(skill_name, record.name)
    return owners


def owning_plugin(skill_name: str, store: Optional[InstalledPluginStore] = None) -> Optional[str]:
    """Name of the plugin providing ``skill_name``, or ``None``.

    ``None`` means the skill is built-in, user-added, or absent — this function
    answers "is this from a plugin?", not "does this skill exist?".
    """
    return projected_skills(store).get(skill_name)
