"""Turn a user-supplied plugin source into a staging directory — and nothing else.

Two source kinds, both deliberately thin (decision D2). There is **no** name
resolution against an index, no version solving, no dependency graph, no
signature check, and no update-checking service. The manifest's ``version`` is
recorded for display and staleness comparison only, which is the one use §10.2
sanctions.

Staging is not an implementation detail: it is what makes validation meaningful.
A local source is **copied** rather than referenced in place, so the bytes that
get validated are the bytes that get published, and a plugin directory the
operator keeps editing cannot change under a running session.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from cli_agent_orchestrator.agent_plugins.containment import resolve_within_root
from cli_agent_orchestrator.agent_plugins.models import PluginSource

logger = logging.getLogger(__name__)

# A clone that cannot finish in this long is not going to; failing loudly beats
# a `cao plugin add` that hangs forever on an unreachable host.
GIT_TIMEOUT_S = 300

# Directory name the staged candidate plugin root is placed under.
_STAGE_DIRNAME = "source"


class ResolverError(RuntimeError):
    """Raised when a plugin source cannot be resolved into staging.

    Carries the underlying cause in its message. The installer turns this into a
    reported failure with the installed set untouched — nothing has been staged
    that could leak into the store.
    """


@dataclass(frozen=True)
class ResolvedSource:
    """A staged candidate plugin root, plus what the source resolved to."""

    root: Path
    """The candidate plugin root inside staging (``subdir`` already applied)."""

    staging: Path
    """The staging directory that owns ``root``; the caller deletes it."""

    resolved_ref: Optional[str] = None
    """Git commit SHA for a ``git`` source; ``None`` for a ``path`` source."""


def resolve(source: PluginSource, dest: Path) -> ResolvedSource:
    """Stage ``source`` under ``dest`` and return the candidate plugin root.

    Args:
        source: What the operator asked to install.
        dest: An existing, caller-owned staging directory. Everything written
            here is disposable; the installer deletes it whether or not the
            install succeeds.

    Raises:
        ResolverError: If the source is unreachable — an invalid local path, a
            failed git operation, or a ``subdir`` that does not exist or escapes
            the staged tree. The installed set is never touched on this path.
    """
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)

    if source.kind == "git":
        staged_root, resolved_ref = _resolve_git(source, dest)
    else:
        staged_root, resolved_ref = _resolve_path(source, dest)

    root = _apply_subdir(staged_root, source.subdir)
    return ResolvedSource(root=root, staging=dest, resolved_ref=resolved_ref)


def _resolve_path(source: PluginSource, dest: Path) -> tuple[Path, None]:
    """Copy a local directory into staging.

    ``symlinks=True`` is load-bearing, not a style choice. Following symlinks
    during the copy would materialize a link that points *outside* the source
    tree as real content inside the staged root — where containment would then
    happily accept it, because by then it genuinely is inside. Preserving links
    keeps the escape visible to ``containment.resolve_within_root``.
    """
    raw = os.path.expanduser(source.location.strip())
    if not raw:
        raise ResolverError("Plugin source path is empty")

    origin = Path(raw).resolve() if not os.path.isabs(raw) else Path(os.path.realpath(raw))
    if not origin.exists():
        raise ResolverError(f"Plugin source path does not exist: {source.location}")
    if not origin.is_dir():
        raise ResolverError(f"Plugin source path is not a directory: {source.location}")

    staged = dest / _STAGE_DIRNAME
    try:
        shutil.copytree(origin, staged, symlinks=True)
    except OSError as exc:
        raise ResolverError(f"Could not copy plugin source {source.location}: {exc}") from exc
    return staged, None


def _resolve_git(source: PluginSource, dest: Path) -> tuple[Path, Optional[str]]:
    """Shallow-clone a repository into staging and record the resolved commit."""
    location = source.location.strip()
    if not location:
        raise ResolverError("Plugin source git URL is empty")

    staged = dest / _STAGE_DIRNAME
    args: List[str] = [
        "clone",
        "--depth",
        "1",
        # Submodules are NOT initialized for a git plugin source. This is a
        # stated non-behavior, spelled with an explicit flag rather than left to
        # `git clone`'s current default: a future default change or a
        # differently-configured git would otherwise silently pull submodule
        # content into staging, which would then have to be reasoned about under
        # containment.
        "--no-recurse-submodules",
    ]
    if source.ref:
        args += ["--branch", source.ref]
    # `--` so a location beginning with `-` is never read as an option.
    args += ["--", location, str(staged)]

    _run_git(args, what=f"clone {location}")

    resolved_ref: Optional[str] = None
    try:
        resolved_ref = _run_git(["rev-parse", "HEAD"], what="resolve commit", cwd=staged)
    except ResolverError as exc:
        # A clone that produced a tree but no resolvable HEAD is odd but not
        # fatal to installing: record no ref rather than refusing the plugin.
        logger.warning("Could not resolve cloned commit for %s: %s", location, exc)

    return staged, resolved_ref


def _run_git(args: List[str], *, what: str, cwd: Optional[Path] = None) -> str:
    """Run a git command with prompts disabled and a hard timeout."""
    env = dict(os.environ)
    # Never block on an interactive credential or host-key prompt: a plugin
    # install must fail with a message, not hang holding the operator's terminal.
    env["GIT_TERMINAL_PROMPT"] = "0"
    env.setdefault("GIT_SSH_COMMAND", "ssh -oBatchMode=yes")

    try:
        result = subprocess.run(
            ["git", *args],
            cwd=str(cwd) if cwd else None,
            check=True,
            capture_output=True,
            text=True,
            timeout=GIT_TIMEOUT_S,
            env=env,
        )
    except FileNotFoundError as exc:
        raise ResolverError(
            "git executable not found on PATH; a git plugin source needs it"
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise ResolverError(f"git {what} timed out after {GIT_TIMEOUT_S}s") from exc
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or "").strip().splitlines()
        message = detail[-1] if detail else f"exit {exc.returncode}"
        raise ResolverError(f"git {what} failed: {message}") from exc
    return result.stdout.strip()


def _apply_subdir(staged_root: Path, subdir: Optional[str]) -> Path:
    """Address a subdirectory of the staged tree as the candidate plugin root.

    Real-world plugins live in monorepo subdirectories — CAO's own packages live
    at ``agent-plugin/<name>/`` in this repository, which is what dogfoods this
    path rather than merely testing it.

    The subdirectory is resolved with the same realpath containment used
    everywhere else, so ``--subdir ../../etc`` (or a symlink standing in for it)
    is rejected instead of walking out of staging.
    """
    if not subdir or not subdir.strip():
        return staged_root

    candidate = resolve_within_root(staged_root, subdir.strip())
    if candidate is None:
        raise ResolverError(f"Plugin subdirectory escapes the source tree: {subdir!r}")
    if not candidate.is_dir():
        raise ResolverError(f"Plugin subdirectory does not exist in the source: {subdir!r}")
    return candidate
