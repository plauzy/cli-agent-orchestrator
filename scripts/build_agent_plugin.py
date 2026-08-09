#!/usr/bin/env python3
"""Build CAO's own Agent Plugins packages, and guard them against drift.

CAO ships **two** packages, split by audience (see design.md "Two packages, not
one"):

* ``agent-plugin/cao`` — the **operator** package. "Drive a CAO fleet from a
  foreign client." Shipping repo-development skills here would enlarge the
  prompt surface of every foreign agent that installs it with instructions it
  will never act on.
* ``agent-plugin/cao-contributor`` — the **contributor** package. Authoring a
  provider or an event plugin. Ships no ``mcp.json`` in either increment:
  authoring skills read and write repo files through the host agent's own
  tools and need no CAO runtime.

``agent-plugin/`` itself is a **container, not a plugin root** — it carries no
``plugin.json``, and each child is independently addressable by the resolver's
``--subdir``.

Why the packages are committed rather than built on demand
---------------------------------------------------------
``cao plugin add ./agent-plugin/cao`` then works from a clone with no build
step, and a foreign client can point at the subdirectory of the GitHub repo
directly — which is also how CAO's own packages exercise the ``git`` resolver's
``--subdir`` support. The cost of committing generated content is drift, which
is what ``--check`` exists to make impossible to merge.

Skills are **copied**, never symlinked
--------------------------------------
§4.1 permits a symlink resolving *inside* a plugin root, but a link into
``../../skills/`` escapes it and must be rejected by a conformant loader. A copy
plus a drift guard is therefore the only conformant option.

The ``--check`` contract
------------------------
``--check`` evaluates **both packages independently** and reports problems for
all of them: a failure in one must never suppress reporting of a failure in the
other (Requirement 3.5), because that is how the contributor package would
quietly rot while the operator package stays current. It fails on:

* a generated tree that diverges from its allowlist or from the canonical skills
* a ``plugin.json`` that differs from what this configuration would generate
* a package ``version`` out of sync with CAO's package metadata
* a package the Validator does not load, or loads with a ``FATAL`` finding
* a skill present that the package's exclusion rules forbid

Exit codes
----------
=====  ==============================================
    0  both packages in sync and loadable
    1  drift, or a package failed validation
=====  ==============================================

Usage
-----
    python scripts/build_agent_plugin.py            # build/refresh both
    python scripts/build_agent_plugin.py --check    # drift + conformance gate
"""

from __future__ import annotations

import argparse
import filecmp
import json
import re
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

ROOT = Path(__file__).resolve().parent.parent

# Canonical source of every skill. Same tree ``scripts/sync_skills.py`` mirrors
# into the wheel, so a packaged skill is a third copy and the drift guards are
# what keep all three consistent.
CANONICAL_SKILLS_DIR = ROOT / "skills"

# Container for the packages. Deliberately NOT ``plugins/`` — that name already
# means the event-plugin system (decision D7), and reusing it at the repo root
# would reintroduce exactly the ambiguity the naming section works to remove.
PACKAGES_DIR = ROOT / "agent-plugin"

PYPROJECT = ROOT / "pyproject.toml"
LICENSE_FILE = ROOT / "LICENSE"

# The pinned Agent Plugins manifest schema. Kept as a literal rather than
# imported so this script can report a mismatch even if the package is not
# importable; a test asserts the two agree.
PLUGIN_SCHEMA_ID = "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json"

REPOSITORY_URL = "https://github.com/awslabs/cli-agent-orchestrator"
LICENSE_ID = "Apache-2.0"

BUILD_COMMAND = "python scripts/build_agent_plugin.py"

# Skills no package may ever ship.
#
# The vendored ext-apps tree is Apache-2.0 content with its own NOTICE
# attribution obligations; redistributing it inside a second package multiplies
# the attribution surface for no benefit.
GLOBALLY_EXCLUDED = ("vendor",)


@dataclass(frozen=True)
class PackageConfig:
    """Everything that distinguishes one package from another.

    Per-package *data*, deliberately not per-package code: adding
    ``cao-contributing`` when PR #448 lands must be a one-line allowlist edit
    with no change to package structure, build tooling, or CI
    (Requirement 2.7).
    """

    name: str
    description: str
    keywords: List[str]
    skills: List[str]
    # Skills that must NOT appear, asserted explicitly rather than left implicit
    # in the allowlist, so the intent survives an accidental allowlist edit.
    forbidden_skills: List[str] = field(default_factory=list)

    @property
    def root(self) -> Path:
        return PACKAGES_DIR / self.name


# The event-plugin authoring skill's name is unsettled (decision M4:
# ``cao-plugin`` -> ``cao-event-plugin``). It is referenced through this
# constant so a rename is one edit; the packaged directory name must equal the
# skill's frontmatter ``name``, so the rename moves both together.
EVENT_PLUGIN_AUTHORING_SKILL = "cao-plugin"

OPERATOR_PACKAGE = PackageConfig(
    name="cao",
    description=(
        "Drive CLI Agent Orchestrator multi-agent sessions from any "
        "Agent-Plugins-compatible client. Prerequisites: the `uv` toolchain "
        "must be on PATH (the MCP server is launched via `uvx`), and a CAO API "
        "server must be running locally at http://127.0.0.1:9889 "
        "(`cao-server`). All communication is localhost-only."
    ),
    keywords=["orchestration", "multi-agent", "cao", "tmux"],
    skills=[
        # The core capability. Without it the package does nothing.
        "cao-session-management",
        # Choosing the right profile before delegating.
        "cao-agent-routing",
        # MAINTAINER-TUNABLE, defaulting to inclusion. An operator messaging a
        # running fleet is acting as a supervisor's peer and needs the
        # assign/handoff/idle-inbox semantics. The counter-argument is that CAO
        # already injects these into its own terminals, so shipping them again
        # couples this portable package to CAO's internal orchestration
        # contract. Reversing the default is a one-line edit here.
        "cao-supervisor-protocols",
        "cao-worker-protocols",
    ],
    forbidden_skills=[
        # Contributor-facing: moved to cao-contributor, not dropped (Req 1.4).
        "cao-provider",
        EVENT_PLUGIN_AUTHORING_SKILL,
    ],
)

CONTRIBUTOR_PACKAGE = PackageConfig(
    # Provisional pending M4: if maintainers scope this package to event-plugin
    # authoring specifically, the package name itself is in play.
    name="cao-contributor",
    description=(
        "Skills for extending CLI Agent Orchestrator: authoring providers and "
        "event plugins. Development-facing; install the `cao` plugin instead "
        "to drive sessions."
    ),
    keywords=["cao", "development", "provider", "extension"],
    skills=[
        "cao-provider",
        EVENT_PLUGIN_AUTHORING_SKILL,
        # NOTE: "cao-contributing" is deliberately ABSENT. It depends on PR #448
        # (open, draft), so the skill does not exist in the tree and this build
        # does not claim it. Its absence is not a validation failure
        # (Requirement 2.6). When #448 merges, add it on the line above --
        # nothing else changes (Requirement 2.7).
    ],
    forbidden_skills=[
        # Operator-facing skills must not crowd a contributor's prompt (Req 2.4).
        "cao-session-management",
        "cao-agent-routing",
        "cao-supervisor-protocols",
        "cao-worker-protocols",
    ],
)

PACKAGES: List[PackageConfig] = [OPERATOR_PACKAGE, CONTRIBUTOR_PACKAGE]


class BuildError(RuntimeError):
    """The build cannot proceed."""


def cao_version() -> str:
    """Read CAO's version from package metadata.

    Uses the same start-of-line anchored pattern ``scripts/bump_version.py``
    writes with, so the two cannot disagree about which key is authoritative.
    An unanchored ``version = "..."`` would also match ``python_version`` under
    ``[tool.mypy]``.
    """
    content = PYPROJECT.read_text(encoding="utf-8")
    match = re.search(r'(?m)^version = "([^"]+)"', content)
    if not match:
        raise BuildError(f"could not find a version in {PYPROJECT.name}")
    return match.group(1)


def render_manifest(config: PackageConfig, version: str) -> str:
    """Render a package's ``plugin.json``.

    Deterministic, and field order is fixed, because ``--check`` compares the
    generated text against what is committed.
    """
    manifest = {
        "$schema": PLUGIN_SCHEMA_ID,
        "name": config.name,
        "version": version,
        "description": config.description,
        "repository": REPOSITORY_URL,
        "license": LICENSE_ID,
        "keywords": list(config.keywords),
    }
    return json.dumps(manifest, indent=2) + "\n"


def canonical_skill_dir(skill: str) -> Path:
    """Locate a skill in the canonical tree, guarding against a typo."""
    source = CANONICAL_SKILLS_DIR / skill
    if not (source / "SKILL.md").is_file():
        raise BuildError(
            f"allowlisted skill {skill!r} has no SKILL.md at "
            f"skills/{skill}/ — check the allowlist for a typo"
        )
    return source


def _relative_files(root: Path) -> List[Path]:
    """Every regular file under ``root``, sorted, excluding caches."""
    if not root.is_dir():
        return []
    return sorted(
        path.relative_to(root)
        for path in root.rglob("*")
        if path.is_file() and "__pycache__" not in path.parts
    )


def build_package(config: PackageConfig, version: str) -> None:
    """Generate one package's tree from its configuration."""
    root = config.root
    root.mkdir(parents=True, exist_ok=True)

    (root / "plugin.json").write_text(render_manifest(config, version), encoding="utf-8")

    # LICENSE travels with the package: it is redistributed content.
    shutil.copyfile(LICENSE_FILE, root / "LICENSE")

    skills_dir = root / "skills"
    skills_dir.mkdir(parents=True, exist_ok=True)

    # Drop skills no longer allowlisted, so a removal from the allowlist cannot
    # leave a stale copy shipping forever.
    allowed = set(config.skills)
    for existing in sorted(skills_dir.iterdir()):
        if existing.name not in allowed:
            if existing.is_dir() and not existing.is_symlink():
                shutil.rmtree(existing)
            else:
                existing.unlink()

    for skill in config.skills:
        source = canonical_skill_dir(skill)
        destination = skills_dir / skill
        if destination.exists():
            shutil.rmtree(destination)
        # Copy, never symlink: a link into ../../skills/ escapes the plugin root
        # and a conformant loader must reject it (§4.1).
        shutil.copytree(source, destination, ignore=shutil.ignore_patterns("__pycache__"))


def check_package(config: PackageConfig, version: str) -> List[str]:
    """Verify one package. Returns a list of problems, never raises.

    Returning problems rather than raising is what lets the caller evaluate
    every package independently (Requirement 3.5).
    """
    problems: List[str] = []
    root = config.root

    if not root.is_dir():
        return [f"package directory missing: agent-plugin/{config.name}/"]

    # -- manifest ----------------------------------------------------------
    manifest_path = root / "plugin.json"
    if not manifest_path.is_file():
        problems.append(f"{config.name}: plugin.json is missing")
    else:
        actual = manifest_path.read_text(encoding="utf-8")
        expected = render_manifest(config, version)
        if actual != expected:
            problems.append(
                f"{config.name}: plugin.json differs from the generated manifest "
                f"(version sync, description, or keywords drifted)"
            )
        try:
            parsed = json.loads(actual)
        except ValueError as exc:
            problems.append(f"{config.name}: plugin.json is not valid JSON: {exc}")
        else:
            # Called out separately so a version skew reports as a version skew
            # rather than as a generic manifest diff (Requirement 3.2).
            if parsed.get("version") != version:
                problems.append(
                    f"{config.name}: plugin.json version {parsed.get('version')!r} "
                    f"does not match CAO's package version {version!r}"
                )
            if parsed.get("$schema") != PLUGIN_SCHEMA_ID:
                problems.append(
                    f"{config.name}: plugin.json $schema is not the pinned 1.0.0 schema"
                )

    if not (root / "LICENSE").is_file():
        problems.append(f"{config.name}: LICENSE is missing from the package")

    # -- skills ------------------------------------------------------------
    skills_dir = root / "skills"
    if not skills_dir.is_dir():
        problems.append(f"{config.name}: skills/ is missing")
        return problems

    present = {entry.name for entry in skills_dir.iterdir() if entry.is_dir()}
    expected_skills = set(config.skills)

    for missing in sorted(expected_skills - present):
        problems.append(f"{config.name}: allowlisted skill not packaged: {missing}")
    for extra in sorted(present - expected_skills):
        problems.append(f"{config.name}: skill present but not allowlisted: {extra}")

    for forbidden in config.forbidden_skills:
        if forbidden in present:
            problems.append(f"{config.name}: skill {forbidden!r} must not ship in this package")
    for forbidden in GLOBALLY_EXCLUDED:
        if forbidden in present:
            problems.append(
                f"{config.name}: {forbidden!r} must not ship in any package "
                f"(vendored content carries its own attribution obligations)"
            )

    # Byte-level comparison against the canonical source.
    for skill in sorted(expected_skills & present):
        try:
            source = canonical_skill_dir(skill)
        except BuildError as exc:
            problems.append(f"{config.name}: {exc}")
            continue
        packaged = skills_dir / skill

        source_files = set(_relative_files(source))
        packaged_files = set(_relative_files(packaged))
        for missing in sorted(source_files - packaged_files):
            problems.append(f"{config.name}: missing in package: {skill}/{missing}")
        for stale in sorted(packaged_files - source_files):
            problems.append(f"{config.name}: stale in package: {skill}/{stale}")
        for shared in sorted(source_files & packaged_files):
            if not filecmp.cmp(source / shared, packaged / shared, shallow=False):
                problems.append(f"{config.name}: content differs: {skill}/{shared}")

    # -- Increment 1: no mcp.json anywhere --------------------------------
    # The contributor package must never ship one (Requirement 2.5); the
    # operator package must not until Increment 2 (Requirement 11.5).
    if (root / "mcp.json").exists():
        problems.append(
            f"{config.name}: mcp.json is present, but MCP support is Increment 2 "
            f"(and the contributor package never ships one)"
        )

    problems.extend(validate_package(config))
    return problems


def validate_package(config: PackageConfig) -> List[str]:
    """Run CAO's own Validator over a generated package (Requirement 3.4).

    Because the packages are committed, this doubles as the on-every-PR
    validation of CAO's own manifests against the pinned schemas.
    """
    try:
        from cli_agent_orchestrator.agent_plugins.models import Severity
        from cli_agent_orchestrator.agent_plugins.validation import validate_plugin
    except Exception as exc:  # pragma: no cover - only when run outside the venv
        return [
            f"{config.name}: could not import CAO's validator ({exc}); "
            f"run this through 'uv run' so the package is importable"
        ]

    report = validate_plugin(config.root)
    problems: List[str] = []

    if not report.loadable:
        problems.append(f"{config.name}: package is not loadable by CAO's Validator")
    for finding in report.findings:
        if finding.severity is Severity.FATAL:
            problems.append(
                f"{config.name}: FATAL {finding.code} ({finding.spec_ref}): {finding.message}"
            )

    for skill in config.skills:
        if skill not in report.skill_names:
            problems.append(
                f"{config.name}: Validator did not discover allowlisted skill {skill!r}"
            )

    return problems


def check_container() -> List[str]:
    """The container directory must not itself look like a plugin."""
    problems: List[str] = []
    if (PACKAGES_DIR / "plugin.json").exists():
        problems.append(
            "agent-plugin/ must not contain a plugin.json: it is a container, "
            "and the plugin roots are its children"
        )
    if PACKAGES_DIR.is_dir():
        known = {config.name for config in PACKAGES}
        for entry in sorted(PACKAGES_DIR.iterdir()):
            if entry.is_dir() and entry.name not in known:
                problems.append(f"unexpected package directory: agent-plugin/{entry.name}/")
    return problems


def main(argv: Optional[List[str]] = None) -> int:
    """Entry point."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Verify both packages instead of writing. Exits non-zero on drift.",
    )
    args = parser.parse_args(argv)

    try:
        version = cao_version()
    except BuildError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if args.check:
        # Evaluate every package even after one fails, so the report is complete.
        all_problems: Dict[str, List[str]] = {}
        for config in PACKAGES:
            all_problems[config.name] = check_package(config, version)
        container_problems = check_container()

        if any(all_problems.values()) or container_problems:
            print("CAO agent-plugin packages are OUT OF SYNC:", file=sys.stderr)
            for name in sorted(all_problems):
                problems = all_problems[name]
                if not problems:
                    print(f"  [{name}] OK", file=sys.stderr)
                    continue
                print(f"  [{name}]", file=sys.stderr)
                for problem in problems:
                    print(f"    - {problem}", file=sys.stderr)
            if container_problems:
                print("  [agent-plugin/]", file=sys.stderr)
                for problem in container_problems:
                    print(f"    - {problem}", file=sys.stderr)
            print(f"\nRun: {BUILD_COMMAND}  (then commit the result)", file=sys.stderr)
            return 1

        print(
            f"OK: {len(PACKAGES)} agent-plugin packages in sync at version {version} "
            f"({', '.join(config.name for config in PACKAGES)})"
        )
        return 0

    try:
        for config in PACKAGES:
            build_package(config, version)
    except BuildError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    for config in PACKAGES:
        print(
            f"Built agent-plugin/{config.name}/ at version {version} "
            f"with {len(config.skills)} skill(s): {', '.join(config.skills)}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
