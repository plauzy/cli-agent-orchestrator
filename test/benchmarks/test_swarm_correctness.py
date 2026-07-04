"""Swarm-collector correctness benchmark (v2.5 close-out, item 1).

Pattern A — held-out correctness equivalence (no statistics; exact equality
on a deterministic test set with documented seeds). The asserted invariant:

    aggregated(swarm output)  ==  aggregated(union(single-Polecat outputs))

i.e. running a swarm with K partitions produces the same set of unique
findings (by dedup-key) as running K single-Polecat dispatches and unioning
their findings.

The aggregator is deterministic (canonical-JSON SHA-256), so equality is
exact. The benchmark uses the same stub spawner / killer / collector
pattern as ``test/orchestration/test_swarm.py`` so it runs without a real
git binary or real terminals.

Marker: ``slow`` (auto-deselected in default `pytest -m 'not e2e' --no-cov`).
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest

from cli_agent_orchestrator.orchestration import (
    SwarmRequest,
    TaskDAG,
    TaskEdge,
    TaskNode,
    dispatch_swarm,
)
from cli_agent_orchestrator.refinery import RefineryQueue

pytestmark = [
    pytest.mark.slow,
    pytest.mark.skipif(shutil.which("git") is None, reason="git binary not available"),
]


# ---------------------------------------------------------------------------
# Synthetic task generator (≥ 50 deterministic shapes)
# ---------------------------------------------------------------------------


def _shape(task_class: str, k: int, seed: int) -> TaskDAG:
    """Pure-parallel DAG with k nodes; every node carries a seed-derived tag.

    No edges → every node fans out as its own polecat. Tag determinism
    means the union(single-polecat) and swarm runs both produce the same
    canonical-JSON shapes.
    """
    return TaskDAG(
        session_id=f"bench-{seed}",
        task_class=task_class,
        nodes=tuple(TaskNode(id=f"n{seed:04d}-{i:02d}") for i in range(k)),
        edges=tuple(),
    )


def _suite() -> list[TaskDAG]:
    """50 deterministic task shapes spread across 5 task classes / sizes."""
    suite: list[TaskDAG] = []
    for cls_idx, task_class in enumerate(["audit", "review", "research", "scan", "lint"]):
        for s in range(10):
            seed = cls_idx * 10 + s
            k = 2 + (seed % 5)  # 2..6 nodes per task
            suite.append(_shape(task_class, k, seed))
    assert len(suite) == 50
    return suite


# ---------------------------------------------------------------------------
# Stubs (mirror test/orchestration/test_swarm.py)
# ---------------------------------------------------------------------------


def _stub_spawner_factory():
    counter = {"n": 0}

    def _spawn(agent_profile, working_directory, polecat_id):
        counter["n"] += 1
        # Embed the polecat_id so the collector can recover the originating node.
        return f"stub-{polecat_id}"

    return _spawn


def _stub_killer(_terminal_id: str) -> None:  # pragma: no cover - trivial
    return None


async def _deterministic_collector(polecat) -> dict[str, Any]:
    """Collector output is a function of partition content only.

    ``polecat.spec.task`` is deterministically built from the partition's
    node ids (see ``orchestration/swarm.py::_spawn_one``), so two
    independent runs over the same DAG produce the same collector output.
    Crucially this *excludes* the random ``polecat_id`` so the dedup keys
    line up between the swarm and union(single-polecat) runs.
    """
    return {"task": polecat.spec.task, "ok": True}


# ---------------------------------------------------------------------------
# Repo fixture (one shared git repo per benchmark file is plenty)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def repo(tmp_path_factory) -> Path:
    path = tmp_path_factory.mktemp("repo")
    subprocess.run(
        ["git", "-C", str(path), "init", "--initial-branch=main", "--quiet"],
        check=True,
    )
    subprocess.run(["git", "-C", str(path), "config", "user.email", "bench@cao.local"], check=True)
    subprocess.run(["git", "-C", str(path), "config", "user.name", "CAO Bench"], check=True)
    subprocess.run(["git", "-C", str(path), "config", "commit.gpgsign", "false"], check=True)
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
# The benchmark
# ---------------------------------------------------------------------------


async def _run_swarm(dag: TaskDAG, repo: Path, worktree_root: Path) -> set[str]:
    """Run the swarm dispatch end-to-end and return the dedup-key set."""
    refinery = RefineryQueue()
    request = SwarmRequest(
        dag=dag,
        parent_repo=repo,
        worktree_root=worktree_root,
        agent_profile="reviewer",
    )
    result = await dispatch_swarm(
        request,
        spawner=_stub_spawner_factory(),
        killer=_stub_killer,
        collector=_deterministic_collector,
        refinery=refinery,
    )
    assert result.aggregated is not None
    return {entry["dedup_key"] for entry in result.aggregated.unique}


async def _run_single_polecat_union(dag: TaskDAG, repo: Path, worktree_root: Path) -> set[str]:
    """Run each node as a 1-node DAG and union the dedup-key sets."""
    union: set[str] = set()
    for node in dag.nodes:
        sub_dag = TaskDAG(
            session_id=dag.session_id + f"-{node.id}",
            task_class=dag.task_class,
            nodes=(node,),
            edges=tuple(),
        )
        sub_keys = await _run_swarm(sub_dag, repo, worktree_root)
        union |= sub_keys
    return union


@pytest.mark.asyncio
async def test_swarm_output_equals_union_of_single_polecat_outputs(
    repo: Path,
    tmp_path: Path,
) -> None:
    """Pattern A correctness equivalence on 50 deterministic task shapes."""
    suite = _suite()
    mismatches: list[tuple[str, set[str], set[str]]] = []
    for dag in suite:
        # Fresh worktree roots per task — ``dispatch_swarm`` adds worktrees
        # under ``worktree_root`` and they must be unique per call.
        wr_swarm = tmp_path / f"wr-swarm-{dag.session_id}"
        wr_swarm.mkdir()
        wr_single = tmp_path / f"wr-single-{dag.session_id}"
        wr_single.mkdir()

        swarm_keys = await _run_swarm(dag, repo, wr_swarm)
        union_keys = await _run_single_polecat_union(dag, repo, wr_single)
        if swarm_keys != union_keys:
            mismatches.append((dag.session_id, swarm_keys, union_keys))

    assert not mismatches, (
        f"swarm/single-polecat mismatch on {len(mismatches)} of {len(suite)} tasks: "
        f"{mismatches[:3]}"
    )
