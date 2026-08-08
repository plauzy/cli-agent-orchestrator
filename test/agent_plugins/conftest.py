"""Shared fixtures for Agent Plugins tests.

Every fixture here builds an **isolated** store under ``tmp_path`` rather than
relocating ``CAO_HOME_DIR``, so a test can never write into a developer's real
plugin store and tests remain safe to run in parallel (``pytest-xdist`` is a
dev dependency).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

import pytest

from cli_agent_orchestrator.agent_plugins.store import InstalledPluginStore

# The one canonical schema identifier CAO pins locally. Kept here so fixtures
# and assertions cannot drift from each other.
SCHEMA_ID = "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json"


def make_manifest(name: str = "example", **overrides: Any) -> Dict[str, Any]:
    """A minimal valid ``plugin.json`` body, with optional field overrides."""
    manifest: Dict[str, Any] = {"$schema": SCHEMA_ID, "name": name, "version": "1.0.0"}
    manifest.update(overrides)
    return manifest


def write_skill(
    skill_dir: Path, name: Optional[str] = None, description: str = "A test skill."
) -> Path:
    """Write a valid ``SKILL.md`` folder at ``skill_dir``.

    The frontmatter ``name`` must equal the folder name — ``_load_skill_folder``
    enforces that, and so does the Agent Skills specification.
    """
    skill_dir.mkdir(parents=True, exist_ok=True)
    skill_name = name if name is not None else skill_dir.name
    (skill_dir / "SKILL.md").write_text(
        f"---\nname: {skill_name}\ndescription: {description}\n---\n\n# {skill_name}\n",
        encoding="utf-8",
    )
    return skill_dir


def make_plugin(
    root: Path,
    name: str = "example",
    *,
    skills: Iterable[str] = ("example-skill",),
    manifest: Optional[Dict[str, Any]] = None,
    raw_manifest: Optional[str] = None,
    mcp: Optional[Dict[str, Any]] = None,
) -> Path:
    """Materialize a plugin package directory at ``root``.

    ``raw_manifest`` writes bytes verbatim (for malformed-JSON cases);
    otherwise ``manifest`` or a generated minimal manifest is serialized.
    """
    root.mkdir(parents=True, exist_ok=True)
    if raw_manifest is not None:
        (root / "plugin.json").write_text(raw_manifest, encoding="utf-8")
    else:
        body = manifest if manifest is not None else make_manifest(name)
        (root / "plugin.json").write_text(json.dumps(body, indent=2), encoding="utf-8")

    for skill_name in skills:
        write_skill(root / "skills" / skill_name)

    if mcp is not None:
        (root / "mcp.json").write_text(json.dumps(mcp, indent=2), encoding="utf-8")

    return root


@pytest.fixture
def store(tmp_path: Path) -> InstalledPluginStore:
    """An empty, isolated plugin store with disjoint root and data trees."""
    return InstalledPluginStore(
        plugins_dir=tmp_path / "agent-plugins",
        data_dir=tmp_path / "agent-plugin-data",
    )


@pytest.fixture
def plugin_factory(tmp_path: Path):
    """Build plugin package directories under a dedicated sources tree."""
    sources = tmp_path / "sources"

    def _factory(name: str = "example", **kwargs: Any) -> Path:
        return make_plugin(sources / name, name, **kwargs)

    return _factory
