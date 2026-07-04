"""Polecat: ephemeral read-only worker agent (Phase 3 / commit 13).

A Polecat is the Tier-2 unit of the read swarm. Each one runs in:
  * an isolated git worktree under ``CAO_HOME_DIR/worktrees/<polecat-id>/``
    so it cannot mutate the parent repository even if it tried, and
  * a CAO terminal whose ``allowed_tools`` was resolved with
    ``read_only=True`` (commit 12) so it cannot run shell mutations,
    edit files, or spawn child agents.

The hard rules from the v2.5 plan:
  1. A Polecat cannot spawn a Polecat. The read_only filter strips
     ``@cao-mcp-server`` from its tool surface, which removes the
     ``assign``/``handoff``/``send_message`` tools, so the Polecat
     literally has no way to invoke the Mayor's dispatch path.
  2. A Polecat is short-lived. The lifecycle is spawn → run task →
     report findings → terminate. There is no "long-running Polecat"
     state.

Commit 13 ships the Polecat *primitive*: the worktree provisioning,
the lifecycle handle, and the terminate path. The actual swarm
dispatch (spawning N polecats from one DAG decomposition and
synthesizing their outputs) lands in commit 14.

For testability, the actual terminal-spawning is injected via a
``spawner`` callable rather than calling ``terminal_service`` directly.
Tests pass a stub spawner; production wiring (commit 14) passes a
real one that calls into the existing ``terminal_service.create_terminal``.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional, Protocol

from opentelemetry import trace

from cli_agent_orchestrator.clients import git_worktree
from cli_agent_orchestrator.telemetry import semconv

logger = logging.getLogger(__name__)

_TRACER = trace.get_tracer("cao.orchestration.polecat", "2.5.0")


@dataclass(frozen=True)
class PolecatSpec:
    """Inputs the Mayor hands to a Polecat at spawn time."""

    task: str
    agent_profile: str
    parent_repo: Path
    worktree_root: Path
    polecat_id: str = field(
        default_factory=lambda: f"{git_worktree.CAO_WORKTREE_PREFIX}{uuid.uuid4().hex[:12]}"
    )


class TerminalSpawner(Protocol):
    """Caller-supplied terminal-creation callable.

    Production: a thin wrapper around ``terminal_service.create_terminal``
    that passes ``read_only=True`` through to ``_resolve_child_allowed_tools``.
    Tests: a stub that records the call and returns a synthetic ID.
    """

    def __call__(
        self,
        agent_profile: str,
        working_directory: Path,
        polecat_id: str,
    ) -> str:
        """Return the terminal_id of the newly-created Polecat terminal."""
        ...


class TerminalKiller(Protocol):
    """Caller-supplied terminal-teardown callable."""

    def __call__(self, terminal_id: str) -> None: ...


@dataclass
class Polecat:
    """A live Polecat handle. Use ``spawn`` to construct, ``terminate`` to
    tear down. The handle exposes the worktree path so the swarm
    coordinator (commit 14) can collect findings from the Polecat's
    output channel before terminating it.
    """

    spec: PolecatSpec
    worktree_path: Path
    terminal_id: str
    _killer: TerminalKiller
    _torn_down: bool = False

    def terminate(self) -> None:
        """Stop the terminal and remove the worktree.

        Idempotent — calling twice is a no-op. Always best-effort:
        a failure to remove the worktree is logged but not raised
        (the next ``prune_cao_worktrees`` call on lifespan startup
        will sweep it).
        """
        if self._torn_down:
            return
        self._torn_down = True

        try:
            self._killer(self.terminal_id)
        except Exception:
            logger.warning(
                "Polecat terminal teardown failed for %s", self.terminal_id, exc_info=True
            )

        try:
            git_worktree.remove_worktree(self.spec.parent_repo, self.worktree_path)
        except Exception:
            logger.warning(
                "Polecat worktree removal failed for %s", self.worktree_path, exc_info=True
            )


def spawn(
    spec: PolecatSpec,
    spawner: TerminalSpawner,
    killer: TerminalKiller,
) -> Polecat:
    """Create the worktree + Polecat terminal. Returns a live ``Polecat``.

    On failure at any step, partially-created state is rolled back:
      * if the spawner raises after the worktree is created, the
        worktree is removed before re-raising
      * if the worktree creation itself raises, no rollback is needed

    Records every step on a ``cao.polecat.spawn`` span so the swarm
    coordinator can correlate spawn latency with downstream stability.
    """
    with _TRACER.start_as_current_span("cao.polecat.spawn") as span:
        span.set_attribute(semconv.GEN_AI_AGENT_ID, spec.polecat_id)
        span.set_attribute(semconv.CAO_TIER, 2)
        span.set_attribute("cao.polecat.profile", spec.agent_profile)

        worktree_path = spec.worktree_root / spec.polecat_id
        # 1. Provision the worktree.
        git_worktree.create_worktree(spec.parent_repo, worktree_path)
        span.add_event("polecat.worktree.created", {"path": str(worktree_path)})

        # 2. Spawn the read-only terminal in that worktree.
        try:
            terminal_id = spawner(
                agent_profile=spec.agent_profile,
                working_directory=worktree_path,
                polecat_id=spec.polecat_id,
            )
        except Exception:
            # Roll back the worktree before re-raising — otherwise
            # the next prune_cao_worktrees has to clean up.
            try:
                git_worktree.remove_worktree(spec.parent_repo, worktree_path)
            except Exception:
                logger.warning(
                    "Failed to roll back worktree after spawner error",
                    exc_info=True,
                )
            raise

        span.add_event("polecat.terminal.spawned", {"terminal_id": terminal_id})

        return Polecat(
            spec=spec,
            worktree_path=worktree_path,
            terminal_id=terminal_id,
            _killer=killer,
        )
