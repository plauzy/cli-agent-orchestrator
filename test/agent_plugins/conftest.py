"""Shared fixtures for Agent Plugins tests.

Every fixture here builds an **isolated** store under ``tmp_path`` rather than
relocating ``CAO_HOME_DIR``, so a test can never write into a developer's real
plugin store and tests remain safe to run in parallel (``pytest-xdist`` is a
dev dependency).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
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

    Scalars are **quoted** deliberately. Unquoted YAML applies implicit typing,
    so a skill legitimately named ``true``, ``no``, or ``null`` would parse as a
    boolean or null and then compare unequal to its own folder name — the
    fixture would be generating an *invalid* skill while claiming it was valid.
    A property test caught exactly that. (The underlying YAML hazard is real for
    plugin authors too, but it lives in CAO's existing skill loader rather than
    in anything this feature introduces.)
    """
    skill_dir.mkdir(parents=True, exist_ok=True)
    skill_name = name if name is not None else skill_dir.name
    quoted_name = json.dumps(skill_name)
    quoted_description = json.dumps(description)
    (skill_dir / "SKILL.md").write_text(
        f"---\nname: {quoted_name}\ndescription: {quoted_description}\n---\n\n# {skill_name}\n",
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


@dataclass
class ProjectionEnv:
    """An isolated store plus its projection target directory.

    Bundled together because every projection assertion needs both, and because
    keeping ``skills_dir`` out of the real ``SKILLS_DIR`` is what stops a test
    from projecting into a developer's actual skill store.
    """

    store: InstalledPluginStore
    skills_dir: Path
    sources: Path

    def make_plugin(self, name: str, **kwargs: Any) -> Path:
        """Build a source package for ``name`` under this env's sources dir."""
        return make_plugin(self.sources / name, name, **kwargs)

    def install(self, name: str, *, force: bool = False, **kwargs: Any):
        """Install a freshly built plugin named ``name``."""
        from cli_agent_orchestrator.agent_plugins import installer
        from cli_agent_orchestrator.agent_plugins.models import PluginSource

        source_dir = kwargs.pop("source_dir", None) or self.make_plugin(name, **kwargs)
        return installer.install(
            PluginSource(kind="path", location=str(source_dir)),
            force=force,
            store=self.store,
            skills_dir=self.skills_dir,
            refresh_agents=False,
        )

    def uninstall(self, name: str, *, purge_data: bool = False):
        """Remove ``name`` from this env."""
        from cli_agent_orchestrator.agent_plugins import installer

        return installer.uninstall(
            name,
            purge_data=purge_data,
            store=self.store,
            skills_dir=self.skills_dir,
            refresh_agents=False,
        )

    def rebuild(self, **kwargs: Any):
        """Rebuild this env's projection."""
        from cli_agent_orchestrator.agent_plugins.projection import rebuild_projection

        return rebuild_projection(self.store, skills_dir=self.skills_dir, **kwargs)

    def skill_names(self) -> list:
        """Entry names currently present in the projection target."""
        if not self.skills_dir.is_dir():
            return []
        return sorted(entry.name for entry in self.skills_dir.iterdir())


@pytest.fixture
def env(tmp_path: Path) -> ProjectionEnv:
    """An isolated install/projection environment."""
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    return ProjectionEnv(
        store=InstalledPluginStore(
            plugins_dir=tmp_path / "agent-plugins",
            data_dir=tmp_path / "agent-plugin-data",
        ),
        skills_dir=skills_dir,
        sources=tmp_path / "sources",
    )


@pytest.fixture
def plugin_factory(tmp_path: Path):
    """Build plugin package directories under a dedicated sources tree."""
    sources = tmp_path / "sources"

    def _factory(name: str = "example", **kwargs: Any) -> Path:
        return make_plugin(sources / name, name, **kwargs)

    return _factory
