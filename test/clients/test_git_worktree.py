"""Tests for the git worktree manager (commit 13).

Runs against a real fixture repo created in a tmp_path. This is a slow-
ish test file because every test pays for ``git init`` + a commit, but
the operations themselves are millisecond-scale and the whole module
finishes in well under a second.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from cli_agent_orchestrator.clients.git_worktree import (
    CAO_WORKTREE_PREFIX,
    GitWorktreeError,
    create_worktree,
    list_worktrees,
    prune_cao_worktrees,
    remove_worktree,
)

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="git binary not available")


# ---------------------------------------------------------------------------
# Fixture: a real (tiny) git repo
# ---------------------------------------------------------------------------


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """Create a minimal git repo with one commit."""
    path = tmp_path / "repo"
    path.mkdir()
    subprocess.run(
        ["git", "-C", str(path), "init", "--initial-branch=main", "--quiet"],
        check=True,
    )
    # Make the repo committable without a global git identity set.
    subprocess.run(["git", "-C", str(path), "config", "user.email", "test@cao.local"], check=True)
    subprocess.run(["git", "-C", str(path), "config", "user.name", "CAO Test"], check=True)
    # Disable GPG signing locally — some sandboxes set commit.gpgsign=true
    # globally with no signing key available, which would fail the commit.
    subprocess.run(["git", "-C", str(path), "config", "commit.gpgsign", "false"], check=True)
    subprocess.run(["git", "-C", str(path), "config", "tag.gpgsign", "false"], check=True)
    (path / "README.md").write_text("hi\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(path), "add", "README.md"], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(path),
            "commit",
            "-m",
            "init",
            "--quiet",
            "--no-gpg-sign",
        ],
        check=True,
    )
    return path


@pytest.fixture
def worktree_root(tmp_path: Path) -> Path:
    """Where Polecat worktrees live."""
    path = tmp_path / "worktrees"
    path.mkdir()
    return path


# ---------------------------------------------------------------------------
# create_worktree / remove_worktree
# ---------------------------------------------------------------------------


class TestCreateWorktree:
    def test_creates_detached_worktree_at_path(self, repo, worktree_root):
        wt = worktree_root / f"{CAO_WORKTREE_PREFIX}1"
        result = create_worktree(repo, wt)
        assert result == wt
        assert wt.exists()
        # README copy from the parent should be present.
        assert (wt / "README.md").read_text(encoding="utf-8") == "hi\n"

    def test_create_with_branch(self, repo, worktree_root):
        wt = worktree_root / f"{CAO_WORKTREE_PREFIX}2"
        create_worktree(repo, wt, branch="polecat-test-branch")
        # Verify the branch exists in the parent repo.
        result = subprocess.run(
            ["git", "-C", str(repo), "branch", "--list", "polecat-test-branch"],
            check=True,
            capture_output=True,
            text=True,
        )
        assert "polecat-test-branch" in result.stdout

    def test_existing_path_raises(self, repo, worktree_root):
        wt = worktree_root / f"{CAO_WORKTREE_PREFIX}3"
        wt.mkdir()
        with pytest.raises(GitWorktreeError, match="already exists"):
            create_worktree(repo, wt)


class TestRemoveWorktree:
    def test_removes_existing_worktree(self, repo, worktree_root):
        wt = worktree_root / f"{CAO_WORKTREE_PREFIX}4"
        create_worktree(repo, wt)
        assert wt.exists()
        remove_worktree(repo, wt)
        assert not wt.exists()

    def test_remove_already_gone_filesystem_falls_back_to_prune(self, repo, worktree_root):
        # Create a worktree, then nuke its filesystem behind git's back.
        wt = worktree_root / f"{CAO_WORKTREE_PREFIX}5"
        create_worktree(repo, wt)
        shutil.rmtree(wt)
        # remove_worktree should now silently prune the metadata.
        remove_worktree(repo, wt)
        # And the repo should not still consider it tracked.
        records = list_worktrees(repo)
        assert all(r.path != wt for r in records)


# ---------------------------------------------------------------------------
# list_worktrees
# ---------------------------------------------------------------------------


class TestListWorktrees:
    def test_returns_main_repo_only_initially(self, repo):
        records = list_worktrees(repo)
        assert len(records) == 1
        assert records[0].path == repo

    def test_lists_added_worktrees(self, repo, worktree_root):
        wt1 = worktree_root / f"{CAO_WORKTREE_PREFIX}a"
        wt2 = worktree_root / f"{CAO_WORKTREE_PREFIX}b"
        create_worktree(repo, wt1)
        create_worktree(repo, wt2, branch="branch-b")

        records = list_worktrees(repo)
        paths = {r.path for r in records}
        assert wt1 in paths
        assert wt2 in paths
        # Main repo + 2 added = 3 total.
        assert len(records) == 3


# ---------------------------------------------------------------------------
# prune_cao_worktrees
# ---------------------------------------------------------------------------


class TestPruneCaoWorktrees:
    def test_removes_worktrees_with_cao_prefix(self, repo, worktree_root):
        wt_cao = worktree_root / f"{CAO_WORKTREE_PREFIX}stranded"
        wt_other = worktree_root / "user-side-worktree"
        create_worktree(repo, wt_cao)
        create_worktree(repo, wt_other)

        removed = prune_cao_worktrees(repo, worktree_root)
        assert removed == 1
        assert not wt_cao.exists()
        # Non-CAO worktrees are left alone.
        assert wt_other.exists()

    def test_no_worktrees_yields_zero(self, repo, worktree_root):
        # Empty worktree_root.
        assert prune_cao_worktrees(repo, worktree_root) == 0

    def test_missing_root_yields_zero(self, repo, tmp_path: Path):
        ghost = tmp_path / "no-such-dir"
        assert prune_cao_worktrees(repo, ghost) == 0

    def test_orphan_filesystem_directory_is_swept(self, repo, worktree_root):
        # Stranded directory with the CAO prefix but no git tracking.
        orphan = worktree_root / f"{CAO_WORKTREE_PREFIX}orphan"
        orphan.mkdir()
        (orphan / "junk.txt").write_text("x", encoding="utf-8")

        removed = prune_cao_worktrees(repo, worktree_root)
        assert removed == 1
        assert not orphan.exists()


# ---------------------------------------------------------------------------
# Concurrent creation (lock smoke test)
# ---------------------------------------------------------------------------


class TestConcurrentCreate:
    def test_serial_creates_succeed(self, repo, worktree_root):
        # We can't easily race threads from a sync test without flakiness,
        # but we can at least verify that multiple sequential creates
        # under the lock do not corrupt the repo's worktree metadata.
        for i in range(5):
            create_worktree(repo, worktree_root / f"{CAO_WORKTREE_PREFIX}{i}")
        records = list_worktrees(repo)
        assert len(records) == 6  # main + 5
