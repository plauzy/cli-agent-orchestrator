"""Git worktree management for Polecat sandboxes (Phase 3 / commit 13).

Each Polecat in the read swarm runs against an isolated git worktree
under ``CAO_HOME_DIR/worktrees/<polecat-id>``, so a misbehaving Polecat
cannot mutate the parent repository the operator launched CAO from.
The Polecat is also configured ``read_only=True`` (commit 12), so even
within its sandbox it can't run ``git commit``, ``rm``, etc.

Worktree creation runs the standard ``git worktree add`` command. The
file lock guards the parent repository so a swarm of N Polecats
spawning concurrently can't race the underlying ``.git/worktrees``
metadata. (Empirically, parallel ``git worktree add`` calls against
the same repo can produce stale references on git 2.x.)

Stranded-worktree garbage collection: a CAO crash can leave behind
worktrees under the ``cao-polecat-`` prefix. ``prune_cao_worktrees``
sweeps those on lifespan startup.
"""

from __future__ import annotations

import contextlib
import errno
import fcntl
import logging
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

logger = logging.getLogger(__name__)

CAO_WORKTREE_PREFIX = "cao-polecat-"


class GitWorktreeError(RuntimeError):
    """Wraps any failure from a ``git worktree`` subprocess."""


@dataclass(frozen=True)
class WorktreeRecord:
    """A single entry from ``git worktree list --porcelain``."""

    path: Path
    head: str  # commit SHA
    branch: str | None  # full ref name (refs/heads/...) or None for detached


@contextlib.contextmanager
def _repo_lock(repo_path: Path) -> Iterator[None]:
    """File-lock the parent repo to serialize concurrent worktree creates.

    Uses ``fcntl.flock`` on a sentinel file under ``.git/cao-worktree.lock``.
    On platforms without fcntl (none today, but documented for clarity),
    this would degrade to no lock.
    """
    lock_path = repo_path / ".git" / "cao-worktree.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    # Open in append mode so the file persists; flock locks the fd.
    fd = os.open(str(lock_path), os.O_RDWR | os.O_CREAT, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        try:
            fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)


def _run_git(repo_path: Path, *args: str) -> str:
    """Run ``git -C <repo> <args>`` and return stdout, raising on non-zero."""
    cmd = ["git", "-C", str(repo_path), *args]
    try:
        result = subprocess.run(
            cmd,
            check=True,
            capture_output=True,
            text=True,
            timeout=30.0,
        )
    except FileNotFoundError as e:  # git binary missing
        raise GitWorktreeError(f"git not found: {e}") from e
    except subprocess.TimeoutExpired as e:
        raise GitWorktreeError(f"git timed out: {' '.join(cmd)}") from e
    except subprocess.CalledProcessError as e:
        raise GitWorktreeError(f"git failed: {' '.join(cmd)}\nstderr: {e.stderr.strip()}") from e
    return result.stdout


def create_worktree(
    repo_path: Path,
    worktree_path: Path,
    *,
    ref: str = "HEAD",
    branch: str | None = None,
) -> Path:
    """Create a worktree at ``worktree_path`` checked out to ``ref``.

    If ``branch`` is given, creates a new branch off ``ref``. Otherwise
    the worktree is checked out in detached-HEAD mode — perfect for
    a Polecat that's read-only by construction anyway.
    """
    if worktree_path.exists():
        raise GitWorktreeError(f"Worktree path already exists: {worktree_path}")
    worktree_path.parent.mkdir(parents=True, exist_ok=True)

    with _repo_lock(repo_path):
        if branch is not None:
            _run_git(repo_path, "worktree", "add", "-b", branch, str(worktree_path), ref)
        else:
            _run_git(repo_path, "worktree", "add", "--detach", str(worktree_path), ref)
    return worktree_path


def remove_worktree(repo_path: Path, worktree_path: Path) -> None:
    """Remove a worktree (force, even if dirty)."""
    with _repo_lock(repo_path):
        try:
            _run_git(repo_path, "worktree", "remove", "--force", str(worktree_path))
        except GitWorktreeError:
            # If the path is already gone, prune the stale metadata.
            _run_git(repo_path, "worktree", "prune")


def list_worktrees(repo_path: Path) -> list[WorktreeRecord]:
    """Parse ``git worktree list --porcelain`` into a list of records."""
    output = _run_git(repo_path, "worktree", "list", "--porcelain")
    records: list[WorktreeRecord] = []
    current: dict[str, str] = {}
    for raw_line in output.splitlines():
        line = raw_line.rstrip()
        if not line:
            if current:
                records.append(_record_from_porcelain(current))
                current = {}
            continue
        if " " in line:
            key, _, value = line.partition(" ")
        else:
            # Bare keys like "bare" or "detached" appear without a value.
            key, value = line, ""
        current[key] = value
    if current:
        records.append(_record_from_porcelain(current))
    return records


def _record_from_porcelain(entry: dict[str, str]) -> WorktreeRecord:
    return WorktreeRecord(
        path=Path(entry["worktree"]),
        head=entry.get("HEAD", ""),
        branch=entry.get("branch") or None,
    )


def prune_cao_worktrees(repo_path: Path, worktree_root: Path) -> int:
    """Remove every worktree under ``worktree_root`` whose name starts
    with ``CAO_WORKTREE_PREFIX``. Returns the count removed.

    Called from the FastAPI lifespan on every boot so a CAO crash
    can't accumulate stranded worktrees.
    """
    if not worktree_root.exists():
        return 0
    removed = 0
    try:
        existing = list_worktrees(repo_path)
    except GitWorktreeError:
        logger.warning("prune_cao_worktrees: unable to list worktrees", exc_info=True)
        return 0

    for record in existing:
        if record.path.parent != worktree_root:
            continue
        if not record.path.name.startswith(CAO_WORKTREE_PREFIX):
            continue
        try:
            remove_worktree(repo_path, record.path)
            removed += 1
            logger.info("Pruned stranded CAO worktree %s", record.path)
        except GitWorktreeError:
            logger.warning("Failed to prune stranded worktree %s", record.path, exc_info=True)

    # Also nuke any leftover *directories* under worktree_root that match
    # the prefix but aren't tracked by git anymore — these are the
    # "git worktree metadata gone but filesystem still there" case.
    for entry in worktree_root.iterdir():
        if not entry.is_dir():
            continue
        if not entry.name.startswith(CAO_WORKTREE_PREFIX):
            continue
        if any(r.path == entry for r in existing):
            continue
        try:
            _force_rmtree(entry)
            removed += 1
            logger.info("Removed orphan worktree directory %s", entry)
        except OSError:
            logger.warning("Failed to remove orphan directory %s", entry, exc_info=True)

    return removed


def _force_rmtree(path: Path) -> None:
    """Like ``shutil.rmtree`` but tolerates read-only files."""
    import shutil
    import stat as _stat

    def _on_rm_error(func, p, exc_info):  # type: ignore[no-untyped-def]
        # Clear read-only bit and retry.
        try:
            os.chmod(p, _stat.S_IWUSR | _stat.S_IRUSR | _stat.S_IXUSR)
            func(p)
        except OSError as e:
            if e.errno == errno.ENOENT:
                return
            raise

    shutil.rmtree(str(path), onerror=_on_rm_error)
