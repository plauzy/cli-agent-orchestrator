"""Tests for the Polecat ephemeral worker (commit 13).

Drives ``spawn_polecat`` against a real fixture git repo so the
worktree provisioning is exercised end-to-end. The terminal
spawning is mocked via the injected ``spawner`` callable — the
actual terminal-creation wiring lands in commit 14.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from cli_agent_orchestrator.clients.git_worktree import CAO_WORKTREE_PREFIX
from cli_agent_orchestrator.orchestration import PolecatSpec, spawn_polecat

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="git binary not available")


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    path = tmp_path / "repo"
    path.mkdir()
    subprocess.run(
        ["git", "-C", str(path), "init", "--initial-branch=main", "--quiet"],
        check=True,
    )
    subprocess.run(["git", "-C", str(path), "config", "user.email", "test@cao.local"], check=True)
    subprocess.run(["git", "-C", str(path), "config", "user.name", "CAO Test"], check=True)
    # See test_git_worktree.py for why we force-disable GPG signing.
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
    path = tmp_path / "worktrees"
    path.mkdir()
    return path


# ---------------------------------------------------------------------------
# Stub spawner / killer
# ---------------------------------------------------------------------------


class _RecordingSpawner:
    def __init__(self) -> None:
        self.calls: list[dict] = []
        self.next_terminal_id = "stub-terminal-1"

    def __call__(self, agent_profile, working_directory, polecat_id):
        self.calls.append(
            {
                "agent_profile": agent_profile,
                "working_directory": working_directory,
                "polecat_id": polecat_id,
            }
        )
        return self.next_terminal_id


class _RecordingKiller:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def __call__(self, terminal_id: str) -> None:
        self.calls.append(terminal_id)


# ---------------------------------------------------------------------------
# Spawn + lifecycle
# ---------------------------------------------------------------------------


class TestSpawn:
    def test_creates_worktree_and_terminal(self, repo, worktree_root):
        spawner = _RecordingSpawner()
        killer = _RecordingKiller()
        spec = PolecatSpec(
            task="audit auth code",
            agent_profile="reviewer",
            parent_repo=repo,
            worktree_root=worktree_root,
        )
        polecat = spawn_polecat(spec, spawner, killer)

        # Worktree was provisioned.
        assert polecat.worktree_path.exists()
        assert polecat.worktree_path.parent == worktree_root
        assert polecat.worktree_path.name.startswith(CAO_WORKTREE_PREFIX)
        # Spawner was called with the right args.
        assert len(spawner.calls) == 1
        call = spawner.calls[0]
        assert call["agent_profile"] == "reviewer"
        assert call["working_directory"] == polecat.worktree_path
        assert call["polecat_id"] == spec.polecat_id
        # Terminal id propagated onto the handle.
        assert polecat.terminal_id == "stub-terminal-1"

    def test_polecat_id_has_cao_prefix_for_pruning(self, repo, worktree_root):
        spec = PolecatSpec(
            task="x",
            agent_profile="reviewer",
            parent_repo=repo,
            worktree_root=worktree_root,
        )
        # The default factory must use the CAO prefix so prune_cao_worktrees
        # can recognise it on later boots.
        assert spec.polecat_id.startswith(CAO_WORKTREE_PREFIX)


# ---------------------------------------------------------------------------
# Terminate (idempotent + best-effort)
# ---------------------------------------------------------------------------


class TestTerminate:
    def test_removes_worktree_and_kills_terminal(self, repo, worktree_root):
        spawner = _RecordingSpawner()
        killer = _RecordingKiller()
        spec = PolecatSpec(
            task="x",
            agent_profile="reviewer",
            parent_repo=repo,
            worktree_root=worktree_root,
        )
        polecat = spawn_polecat(spec, spawner, killer)
        path = polecat.worktree_path

        polecat.terminate()
        assert not path.exists()
        assert killer.calls == ["stub-terminal-1"]

    def test_terminate_is_idempotent(self, repo, worktree_root):
        spec = PolecatSpec(
            task="x",
            agent_profile="reviewer",
            parent_repo=repo,
            worktree_root=worktree_root,
        )
        spawner = _RecordingSpawner()
        killer = _RecordingKiller()
        polecat = spawn_polecat(spec, spawner, killer)

        polecat.terminate()
        polecat.terminate()  # second call must not raise or re-call
        assert killer.calls == ["stub-terminal-1"]

    def test_killer_failure_does_not_block_worktree_removal(self, repo, worktree_root):
        def broken_killer(terminal_id):
            raise RuntimeError("tmux exploded")

        spawner = _RecordingSpawner()
        spec = PolecatSpec(
            task="x",
            agent_profile="reviewer",
            parent_repo=repo,
            worktree_root=worktree_root,
        )
        polecat = spawn_polecat(spec, spawner, broken_killer)
        path = polecat.worktree_path
        polecat.terminate()
        # Worktree still removed despite killer raising.
        assert not path.exists()


# ---------------------------------------------------------------------------
# Spawn rollback
# ---------------------------------------------------------------------------


class TestSpawnRollback:
    def test_spawner_failure_rolls_back_worktree(self, repo, worktree_root):
        def boom(*args, **kwargs):
            raise RuntimeError("can't make terminal")

        killer = _RecordingKiller()
        spec = PolecatSpec(
            task="x",
            agent_profile="reviewer",
            parent_repo=repo,
            worktree_root=worktree_root,
        )
        with pytest.raises(RuntimeError, match="can't make terminal"):
            spawn_polecat(spec, boom, killer)

        # No worktree should be left behind.
        leftovers = [p for p in worktree_root.iterdir() if p.name.startswith(CAO_WORKTREE_PREFIX)]
        assert leftovers == []
        # Killer never invoked since the terminal never existed.
        assert killer.calls == []
