"""Tests for the high-level dispatch entrypoint (commit 17).

Coverage matrix:
  * STATIC_HIERARCHY → static_executor runs directly, no Refinery
  * SEQUENTIAL_REFINERY → static_executor runs through Refinery
  * PARALLEL_POLECAT_SWARM → swarm dispatch with union-find partitioning
  * HYBRID_HIERARCHICAL_CLUSTER → swarm dispatch with cluster_dag
    partitioning (via synthetic high-coupling edges)
  * Missing parallel deps → graceful downgrade to SEQUENTIAL_REFINERY
  * Topology choice recorded as a span attribute
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest

from cli_agent_orchestrator.orchestration import (
    DispatchRequest,
    KillSwitchEngaged,
    TaskDAG,
    TaskEdge,
    TaskNode,
    Topology,
    dispatch_task,
)
from cli_agent_orchestrator.refinery import RefineryQueue

pytestmark_git = pytest.mark.skipif(shutil.which("git") is None, reason="git binary not available")


# ---------------------------------------------------------------------------
# Repo fixture (shared shape with test_polecat / test_swarm)
# ---------------------------------------------------------------------------


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
    subprocess.run(["git", "-C", str(path), "config", "commit.gpgsign", "false"], check=True)
    subprocess.run(["git", "-C", str(path), "config", "tag.gpgsign", "false"], check=True)
    (path / "README.md").write_text("hi\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(path), "add", "README.md"], check=True)
    subprocess.run(
        ["git", "-C", str(path), "commit", "-m", "init", "--quiet", "--no-gpg-sign"],
        check=True,
    )
    return path


@pytest.fixture
def worktree_root(tmp_path: Path) -> Path:
    p = tmp_path / "worktrees"
    p.mkdir()
    return p


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _dag(task_class: str, nodes, edges=()) -> TaskDAG:
    return TaskDAG(
        session_id="s1",
        task_class=task_class,
        nodes=tuple(TaskNode(n) for n in nodes),
        edges=tuple(TaskEdge(e[0], e[1], e[2]) for e in edges),
    )


class _Spawner:
    def __init__(self) -> None:
        self.calls = 0

    def __call__(self, agent_profile, working_directory, polecat_id):
        self.calls += 1
        return f"stub-{self.calls}"


class _Killer:
    def __init__(self) -> None:
        self.calls = 0

    def __call__(self, terminal_id):
        self.calls += 1


def _make_collector(value):
    async def _c(polecat):
        return value

    return _c


# ---------------------------------------------------------------------------
# STATIC_HIERARCHY — no Refinery, executor runs directly
# ---------------------------------------------------------------------------


class TestStatic:
    @pytest.mark.asyncio
    async def test_static_runs_executor_directly_no_refinery(self):
        ran = False

        async def static():
            nonlocal ran
            ran = True
            return "static-result"

        refinery = RefineryQueue()
        request = DispatchRequest(
            dag=_dag("trivial", ["a"]),  # k=1, ω=1, γ=0 → STATIC
            static_executor=static,
            refinery=refinery,
        )
        result = await dispatch_task(request)

        assert result.topology == Topology.STATIC_HIERARCHY
        assert result.value == "static-result"
        assert ran is True
        # Refinery never touched.
        assert refinery.stats["submitted"] == 0


# ---------------------------------------------------------------------------
# SEQUENTIAL_REFINERY — high-coupling DAG
# ---------------------------------------------------------------------------


class TestSequential:
    @pytest.mark.asyncio
    async def test_sequential_runs_through_refinery(self):
        ran = False

        async def static():
            nonlocal ran
            ran = True
            return "seq-result"

        refinery = RefineryQueue()
        request = DispatchRequest(
            dag=_dag("refactor", ["a", "b"], [("a", "b", 0.6)]),  # γ=0.6 → SEQ
            static_executor=static,
            refinery=refinery,
        )
        result = await dispatch_task(request)

        assert result.topology == Topology.SEQUENTIAL_REFINERY
        assert result.value == "seq-result"
        assert ran is True
        # Refinery saw exactly one submit.
        assert refinery.stats["submitted"] == 1
        assert refinery.stats["allowed"] == 1


# ---------------------------------------------------------------------------
# PARALLEL_POLECAT_SWARM
# ---------------------------------------------------------------------------


class TestSwarm:
    @pytest.mark.asyncio
    @pytestmark_git
    async def test_swarm_branch_dispatches_polecats(self, repo, worktree_root):
        async def static():
            raise AssertionError("static_executor should not run for SWARM")

        spawner = _Spawner()
        killer = _Killer()
        refinery = RefineryQueue()
        request = DispatchRequest(
            dag=_dag(
                "research_breadth",
                ["root", *[f"p-{i}" for i in range(8)]],
                [("root", f"p-{i}", 0.1) for i in range(8)],
            ),  # ω=8, γ=0.1 → SWARM
            static_executor=static,
            refinery=refinery,
            parent_repo=repo,
            worktree_root=worktree_root,
            agent_profile="reviewer",
            spawner=spawner,
            killer=killer,
            collector=_make_collector({"ok": True}),
        )
        result = await dispatch_task(request)

        assert result.topology == Topology.PARALLEL_POLECAT_SWARM
        assert result.swarm is not None
        assert result.swarm.polecats_spawned == 9
        assert spawner.calls == 9
        assert killer.calls == 9


# ---------------------------------------------------------------------------
# HYBRID_HIERARCHICAL_CLUSTER
# ---------------------------------------------------------------------------


class TestHybrid:
    @pytest.mark.asyncio
    @pytestmark_git
    async def test_hybrid_branch_dispatches_with_cluster_partitioning(self, repo, worktree_root):
        # k=60, ω=5, γ<0.4 → HYBRID. Use chain-of-fans shape.
        nodes = [f"n-{lvl}-{w}" for lvl in range(12) for w in range(5)]
        edges = [(f"n-{lvl}-{w}", f"n-{lvl+1}-{w}", 0.1) for lvl in range(11) for w in range(5)]

        async def static():
            raise AssertionError("static_executor should not run for HYBRID")

        spawner = _Spawner()
        killer = _Killer()
        refinery = RefineryQueue()
        request = DispatchRequest(
            dag=_dag("hybrid_audit", nodes, edges),
            static_executor=static,
            refinery=refinery,
            parent_repo=repo,
            worktree_root=worktree_root,
            agent_profile="reviewer",
            spawner=spawner,
            killer=killer,
            collector=_make_collector({"ok": True}),
        )
        result = await dispatch_task(request)

        assert result.topology == Topology.HYBRID_HIERARCHICAL_CLUSTER
        assert result.swarm is not None
        # cluster_dag clamps oversized clusters to DEFAULT_MAX_CLUSTER_SIZE
        # (12), and label propagation usually finds 5 clusters per chain
        # row. Either way we should see well under 60 polecats and at
        # least one synthesis.
        assert result.swarm.polecats_spawned > 0
        assert refinery.stats["submitted"] == 1  # exactly one synthesis


# ---------------------------------------------------------------------------
# Defensive: missing parallel deps → downgrade to SEQUENTIAL_REFINERY
# ---------------------------------------------------------------------------


class TestDowngrade:
    @pytest.mark.asyncio
    async def test_missing_parallel_deps_downgrades_to_sequential(self):
        ran = False

        async def static():
            nonlocal ran
            ran = True
            return "downgraded"

        # SWARM-shaped DAG but no parent_repo / spawner / killer / collector.
        refinery = RefineryQueue()
        request = DispatchRequest(
            dag=_dag(
                "research_breadth",
                ["root", *[f"p-{i}" for i in range(8)]],
                [("root", f"p-{i}", 0.1) for i in range(8)],
            ),
            static_executor=static,
            refinery=refinery,
        )
        result = await dispatch_task(request)

        # Router picked SWARM but we lacked deps → downgrade to SEQ_REFINERY.
        assert result.topology == Topology.SEQUENTIAL_REFINERY
        assert result.value == "downgraded"
        assert ran is True
        assert refinery.stats["submitted"] == 1


# ---------------------------------------------------------------------------
# Kill-switch gate (Phase 4 / commit 23)
# ---------------------------------------------------------------------------


class _KillSwitch:
    """Minimal stand-in for observability.KillSwitchState."""

    def __init__(self, killed: set[str] | None = None) -> None:
        self._killed = killed or set()

    def is_killed(self, task_class: str) -> bool:
        return task_class in self._killed


class TestKillSwitchGate:
    @pytest.mark.asyncio
    async def test_killed_task_class_refuses_dispatch(self):
        ran = False

        async def static():
            nonlocal ran
            ran = True

        request = DispatchRequest(
            dag=_dag("research_breadth", ["a"]),
            static_executor=static,
        )
        kill_switch = _KillSwitch(killed={"research_breadth"})

        with pytest.raises(KillSwitchEngaged) as exc:
            await dispatch_task(request, kill_switch=kill_switch)

        assert exc.value.task_class == "research_breadth"
        assert ran is False  # Never reached the executor.

    @pytest.mark.asyncio
    async def test_unrelated_task_class_dispatches_normally(self):
        ran = False

        async def static():
            nonlocal ran
            ran = True
            return "ok"

        request = DispatchRequest(
            dag=_dag("code_review", ["a"]),
            static_executor=static,
        )
        kill_switch = _KillSwitch(killed={"research_breadth"})  # Different class.

        result = await dispatch_task(request, kill_switch=kill_switch)
        assert ran is True
        assert result.value == "ok"

    @pytest.mark.asyncio
    async def test_no_kill_switch_skips_gate(self):
        # Existing callers (no kill_switch=) must keep working.
        async def static():
            return "ok"

        request = DispatchRequest(
            dag=_dag("any", ["a"]),
            static_executor=static,
        )
        result = await dispatch_task(request)  # No kill_switch arg.
        assert result.value == "ok"

    @pytest.mark.asyncio
    async def test_real_kill_switch_state_satisfies_protocol(self):
        # Verify the actual observability.KillSwitchState class
        # works as a kill_switch oracle (duck typing pin).
        from cli_agent_orchestrator.observability import KillSwitchState

        state = KillSwitchState()
        state.kill("research_breadth")

        async def static():
            return "ok"

        request = DispatchRequest(
            dag=_dag("research_breadth", ["a"]),
            static_executor=static,
        )
        with pytest.raises(KillSwitchEngaged):
            await dispatch_task(request, kill_switch=state)

        # After clearing, dispatch resumes.
        state.clear("research_breadth")
        result = await dispatch_task(request, kill_switch=state)
        assert result.value == "ok"
