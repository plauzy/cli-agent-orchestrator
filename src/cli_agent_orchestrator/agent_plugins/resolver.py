"""Turn a user-supplied plugin source into a staging directory, and nothing else.

The resolver is deliberately thin (decision D2). It does **not** resolve names
against an index, solve dependencies, or verify signatures (Requirement 8.5) —
those are non-goals CAO inherits from the specification's own deferral, and
pretending otherwise would imply a trust model CAO cannot back.

Two source kinds:

* ``path`` — a local directory, **copied** into staging. Copying rather than
  referencing in place is what makes "validate before publish" meaningful: a
  source that changes between validation and publish would otherwise let
  unvalidated bytes reach the store, and a live plugin could mutate underneath
  a running session.
* ``git`` — a shallow clone at an optional ref, recording the resolved commit
  so the install record says exactly what was installed.

Submodules are a stated non-behavior
------------------------------------
The resolver never initializes or fetches git submodules. This is enforced with
explicit flags rather than relied upon as a ``--depth 1`` side effect, because
it is not one: a user with ``submodule.recurse=true`` in their git config gets
recursive clones by default, which would pull arbitrary third-party content
into staging where it would then have to pass containment. ``-c
submodule.recurse=false`` plus ``--no-recurse-submodules`` makes the
non-behavior independent of ambient configuration and of future git defaults.
"""

from __future__ import annotations

import logging
import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Sequence

from cli_agent_orchestrator.agent_plugins.models import PluginSource
from cli_agent_orchestrator.utils.path_validation import safe_join_under_base

logger = logging.getLogger(__name__)

# Source kinds this resolver understands.
SOURCE_KIND_PATH = "path"
SOURCE_KIND_GIT = "git"
SOURCE_KINDS = (SOURCE_KIND_PATH, SOURCE_KIND_GIT)

# A full git object id. Only a full id is accepted for the fetch-by-commit
# fallback: an abbreviated id can be ambiguous, which would make the pin
# non-deterministic.
_FULL_COMMIT_RE = re.compile(r"\A[0-9a-fA-F]{40}\Z")

# Seconds before a git operation is abandoned. A hung clone must not wedge an
# install indefinitely; the operator gets a reported failure instead.
GIT_TIMEOUT_SECONDS = 300


class PluginResolutionError(RuntimeError):
    """A source could not be resolved.

    Requirement 8.4 requires reporting the underlying cause, so the message
    always carries git's stderr or the offending path rather than a generic
    "resolution failed".
    """


@dataclass(frozen=True)
class ResolvedSource:
    """The outcome of resolving a source into staging."""

    root: Path  # candidate plugin root (after --subdir), absolute
    staging: Path  # the staging directory the source was materialized into
    source: PluginSource
    resolved_ref: Optional[str] = None  # git commit id, when applicable


def _git_env() -> dict:
    """Environment for git subprocesses, with interactivity disabled.

    A clone of an arbitrary URL must never block waiting for a credential
    prompt — in a CLI that would look like a hang, and in the API server it
    would pin a worker forever.
    """
    env = dict(os.environ)
    env["GIT_TERMINAL_PROMPT"] = "0"
    env["GIT_ASKPASS"] = ""
    env["SSH_ASKPASS"] = ""
    env["GCM_INTERACTIVE"] = "never"
    return env


def _run_git(args: Sequence[str], cwd: Optional[Path] = None) -> str:
    """Run git with submodule recursion forced off; return stripped stdout."""
    command = [
        "git",
        # Belt and braces: neutralize an ambient submodule.recurse=true for
        # every subcommand, not just clone.
        "-c",
        "submodule.recurse=false",
        # Never consult a credential helper that could block or leak.
        "-c",
        "credential.helper=",
        *args,
    ]
    try:
        result = subprocess.run(
            command,
            cwd=str(cwd) if cwd else None,
            check=True,
            capture_output=True,
            text=True,
            env=_git_env(),
            timeout=GIT_TIMEOUT_SECONDS,
        )
    except FileNotFoundError as exc:
        raise PluginResolutionError("git executable not found on PATH") from exc
    except subprocess.TimeoutExpired as exc:
        raise PluginResolutionError(
            f"git {' '.join(args)} timed out after {GIT_TIMEOUT_SECONDS}s"
        ) from exc
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or "").strip()
        raise PluginResolutionError(
            f"git {' '.join(args)} failed (exit {exc.returncode}): {detail}"
        ) from exc
    return result.stdout.strip()


def _resolve_path_source(source: PluginSource, staging: Path) -> ResolvedSource:
    """Copy a local directory's contents into ``staging`` (Requirement 8.1)."""
    origin = Path(source.location).expanduser()
    if not origin.exists():
        raise PluginResolutionError(f"plugin source path does not exist: {origin}")
    if not origin.is_dir():
        raise PluginResolutionError(
            f"plugin source path is not a directory: {origin} "
            f"(a plugin is a directory containing plugin.json)"
        )

    staging.mkdir(parents=True, exist_ok=True)
    try:
        # symlinks=True: the package's own internal links are part of its bytes
        # and §4.1 permits those resolving inside the root. Dereferencing them
        # here would both alter the package and let a link that points outside
        # the root smuggle external content in as a regular file, bypassing the
        # containment check that would otherwise reject it.
        shutil.copytree(origin, staging, symlinks=True, dirs_exist_ok=True)
    except OSError as exc:
        raise PluginResolutionError(f"could not copy plugin source {origin}: {exc}") from exc

    return ResolvedSource(
        root=_apply_subdir(staging, source.subdir),
        staging=staging,
        source=source,
        resolved_ref=None,
    )


def _resolve_git_source(source: PluginSource, staging: Path) -> ResolvedSource:
    """Shallow-clone a repository into ``staging`` (Requirements 8.2, 8.3)."""
    staging.mkdir(parents=True, exist_ok=True)

    clone_args: List[str] = [
        "clone",
        "--depth",
        "1",
        "--no-recurse-submodules",
        "--no-tags",
    ]
    if source.ref:
        clone_args += ["--branch", source.ref]
    clone_args += [source.location, str(staging)]

    try:
        _run_git(clone_args)
    except PluginResolutionError as exc:
        # --branch only accepts a branch or tag name. A caller pinning an exact
        # commit (which is what an install record replays) lands here, so fall
        # back to fetching that one object.
        if source.ref and _FULL_COMMIT_RE.match(source.ref):
            _clone_at_commit(source.location, source.ref, staging)
        else:
            raise PluginResolutionError(
                f"could not clone {source.location}"
                + (f" at ref {source.ref!r}" if source.ref else "")
                + f": {exc}"
            ) from exc

    # Capture the commit before discarding the repository metadata below.
    resolved_ref = _run_git(["rev-parse", "HEAD"], cwd=staging)

    # A cloned ``.git`` directory is version-control metadata, not package
    # bytes, and PLUGIN_ROOT is meant to hold the package. Dropping it keeps
    # the store from accumulating whole repository histories -- which is not
    # hypothetical: ``git clone`` silently ignores ``--depth`` for a local
    # path source, so a local clone arrives with full history attached.
    git_dir = staging / ".git"
    if git_dir.is_dir() and not git_dir.is_symlink():
        shutil.rmtree(git_dir, ignore_errors=True)
    elif git_dir.exists():
        # A worktree/submodule checkout uses a ``.git`` *file* pointing elsewhere.
        git_dir.unlink(missing_ok=True)

    return ResolvedSource(
        root=_apply_subdir(staging, source.subdir),
        staging=staging,
        source=source,
        resolved_ref=resolved_ref,
    )


def _clone_at_commit(location: str, commit: str, staging: Path) -> None:
    """Fetch exactly one commit into ``staging``.

    Used when the ref is a full commit id, which ``clone --branch`` cannot
    take. Requires the server to allow fetching a reachable object by id
    (GitHub does); if it does not, the failure is reported like any other.
    """
    # A previous failed clone may have left a partial tree behind, or removed
    # the staging directory entirely.
    staging.mkdir(parents=True, exist_ok=True)
    for entry in staging.iterdir():
        if entry.is_dir() and not entry.is_symlink():
            shutil.rmtree(entry, ignore_errors=True)
        else:
            entry.unlink(missing_ok=True)

    _run_git(["init", "--quiet"], cwd=staging)
    _run_git(["remote", "add", "origin", location], cwd=staging)
    _run_git(["fetch", "--depth", "1", "--no-recurse-submodules", "origin", commit], cwd=staging)
    _run_git(["checkout", "--quiet", "FETCH_HEAD"], cwd=staging)


def _apply_subdir(staging: Path, subdir: Optional[str]) -> Path:
    """Address ``subdir`` inside ``staging`` as the candidate plugin root.

    Real plugins live in monorepo subdirectories — CAO's own packages will —
    so this is a first-class addressing mode, not a convenience
    (Requirement 8.3).

    Containment is enforced here rather than left to the validator: the
    validator's job starts at a plugin root, and a ``subdir`` of ``../../etc``
    would otherwise hand it a root outside staging entirely.
    """
    if not subdir:
        return staging.resolve()

    # Normalize separators and drop empty/"." segments so "a//b/./c" and
    # "a/b/c" address the same directory.
    parts = [part for part in re.split(r"[\\/]+", subdir) if part not in ("", ".")]
    if not parts:
        return staging.resolve()

    try:
        candidate = Path(
            safe_join_under_base(str(staging), *parts, description="plugin subdirectory")
        )
    except ValueError as exc:
        raise PluginResolutionError(
            f"--subdir {subdir!r} does not resolve inside the plugin source: {exc}"
        ) from exc

    if not candidate.is_dir():
        raise PluginResolutionError(
            f"--subdir {subdir!r} is not a directory inside the plugin source"
        )
    return candidate


def resolve(source: PluginSource, dest: Path) -> ResolvedSource:
    """Materialize ``source`` into ``dest`` and return the candidate root.

    Raises:
        PluginResolutionError: the source is unreachable or unusable. Nothing
            outside ``dest`` is touched, so the installed set is unchanged
            (Requirement 8.4).
    """
    staging = Path(dest)

    if source.kind == SOURCE_KIND_PATH:
        return _resolve_path_source(source, staging)
    if source.kind == SOURCE_KIND_GIT:
        return _resolve_git_source(source, staging)

    raise PluginResolutionError(
        f"unsupported plugin source kind {source.kind!r} "
        f"(expected one of: {', '.join(SOURCE_KINDS)})"
    )


def detect_source(
    location: str, *, ref: Optional[str] = None, subdir: Optional[str] = None
) -> PluginSource:
    """Classify a user-supplied location as a ``git`` or ``path`` source.

    Convenience for the CLI and the API so an operator can paste a GitHub URL
    or a local path without also declaring which kind it is. Anything that
    looks like a remote URL is treated as ``git``; everything else is a local
    path, and a nonexistent path is reported by the resolver rather than
    guessed at here.
    """
    candidate = location.strip()
    looks_remote = (
        candidate.startswith(("http://", "https://", "git://", "ssh://", "git+"))
        or candidate.endswith(".git")
        # scp-style remote, e.g. git@github.com:owner/repo
        or bool(re.match(r"\A[\w.+-]+@[\w.-]+:", candidate))
    )
    kind = SOURCE_KIND_GIT if looks_remote else SOURCE_KIND_PATH
    return PluginSource(kind=kind, location=candidate, ref=ref, subdir=subdir)
