"""Cedar policy adapter + parallel-evaluation harness (v2.5 close-out, item 10).

The Refinery policy gate is currently :class:`YamlRulePolicy`. This
module ships:

  * :class:`CedarPolicy` — adapter that evaluates a list of Cedar policy
    statements through the ``cedarpy`` engine when the package is
    available. Falls back to permissive when the engine isn't installed
    (Cedar is an optional extra in v2.5; runtime opt-in).
  * :class:`ParallelEvaluatingPolicy` — runs both YAML and Cedar engines
    on every request, returns the YAML decision (the canonical engine
    today), and emits a ``cao.refinery.policy.divergence`` OTel span
    when the two engines disagree. Operators run this in shadow mode
    for one runbook horizon, fix divergences, then flip the
    ``CAO_REFINERY_ENGINE`` env var to ``cedar`` to make Cedar
    authoritative.

The runtime engine is selected by ``CAO_REFINERY_ENGINE``:

  * ``yaml`` (default) — :class:`YamlRulePolicy` directly. v2.5 baseline.
  * ``parallel`` — :class:`ParallelEvaluatingPolicy`, YAML authoritative.
  * ``cedar`` — :class:`ParallelEvaluatingPolicy` with Cedar
    authoritative (operators flip after the runbook horizon).

The Phase 3 design promised Cedar as a v2.6 deliverable. v2.5 closes
the gap by shipping the adapter + harness in shadow mode — no runtime
change unless an operator opts in.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Optional

from opentelemetry import trace

from cli_agent_orchestrator.refinery.policy import (
    PermissivePolicy,
    Policy,
    PolicyOutcome,
    YamlRulePolicy,
)

logger = logging.getLogger(__name__)
_TRACER = trace.get_tracer("cao.refinery.cedar", "2.5.0")


# ---------------------------------------------------------------------------
# CedarPolicy adapter
# ---------------------------------------------------------------------------


class CedarPolicy:
    """Adapter that evaluates Cedar policy statements via ``cedarpy``.

    The engine is the gold-standard policy language for AWS-style
    ABAC; the v2.5 close-out scope is the *adapter*, not a full
    translation of every YAML rule. Operators write Cedar policies
    by hand (or via the migration script in ``docs/cedar-migration.md``)
    and pass them in at construction.

    When ``cedarpy`` is unavailable, the adapter degrades to permissive
    so it doesn't break operators who haven't opted in. Production
    callers running ``CAO_REFINERY_ENGINE=cedar`` should install the
    extra explicitly.
    """

    def __init__(
        self,
        policies: str = "",
        *,
        principal: str = 'User::"refinery"',
    ) -> None:
        self._policies = policies
        self._principal = principal
        self._engine: Optional[Any] = None
        try:
            import cedarpy as _cedarpy  # type: ignore[import-not-found,import-untyped]

            self._engine = _cedarpy
        except ImportError:
            logger.info(
                "cedarpy not installed; CedarPolicy will be permissive. "
                "Install with: pip install cedarpy"
            )

    def evaluate(self, action: str, payload: dict[str, Any]) -> PolicyOutcome:
        if self._engine is None or not self._policies:
            return PolicyOutcome.ALLOW

        # Translate the Refinery's (action, payload) into Cedar's
        # (principal, action, resource, context) shape.
        request = {
            "principal": self._principal,
            "action": f'Action::"{action}"',
            "resource": f'Resource::"refinery/{action}"',
            "context": payload,
        }
        try:
            decision = self._engine.is_authorized(
                request=request,
                policies=self._policies,
                entities=[],
            )
        except Exception:
            logger.warning("Cedar evaluation failed for action=%s", action, exc_info=True)
            return PolicyOutcome.ALLOW

        # ``cedarpy.is_authorized`` returns an object with a ``decision``
        # attribute / dict key — normalize both shapes.
        verdict = (
            decision.get("decision")
            if isinstance(decision, dict)
            else getattr(decision, "decision", None)
        )
        if verdict == "Allow":
            return PolicyOutcome.ALLOW
        # Cedar has no native ESCALATE; map "Deny" to DENY. The Refinery
        # treats DENY and ESCALATE distinctly; operators encode "needs
        # operator approval" as a separate Cedar action that's denied,
        # then the YAML rule (still authoritative in shadow mode)
        # decides whether to ESCALATE.
        return PolicyOutcome.DENY


# ---------------------------------------------------------------------------
# ParallelEvaluatingPolicy
# ---------------------------------------------------------------------------


class ParallelEvaluatingPolicy:
    """Run both YAML and Cedar engines, return one, emit a divergence span.

    ``authoritative`` selects which engine's outcome the Refinery acts
    on. The non-authoritative engine still runs — its outcome is
    emitted as a span attribute so operators can run a one-week
    shadow horizon, audit divergences, and flip the env var when
    confident.

    Both engines are called inside the Refinery's single-writer lock,
    so they must remain cheap. The Cedar engine is an in-process
    library call against a small policy set; v2.5 does not authorize
    ``cedarpy`` invocations against an external policy store.
    """

    def __init__(
        self,
        *,
        yaml_policy: Optional[Policy] = None,
        cedar_policy: Optional[Policy] = None,
        authoritative: str = "yaml",
    ) -> None:
        self._yaml = yaml_policy or PermissivePolicy()
        self._cedar = cedar_policy or PermissivePolicy()
        if authoritative not in ("yaml", "cedar"):
            raise ValueError(f"authoritative must be 'yaml' or 'cedar', got {authoritative!r}")
        self._authoritative = authoritative

    def evaluate(self, action: str, payload: dict[str, Any]) -> PolicyOutcome:
        yaml_outcome = self._yaml.evaluate(action, payload)
        try:
            cedar_outcome = self._cedar.evaluate(action, payload)
        except Exception:
            logger.warning("Cedar shadow evaluation failed", exc_info=True)
            cedar_outcome = yaml_outcome  # No divergence on failure.

        with _TRACER.start_as_current_span("cao.refinery.policy.divergence") as span:
            span.set_attribute("cao.refinery.policy.action", action)
            span.set_attribute("cao.refinery.policy.yaml_outcome", yaml_outcome.value)
            span.set_attribute("cao.refinery.policy.cedar_outcome", cedar_outcome.value)
            span.set_attribute(
                "cao.refinery.policy.diverged",
                yaml_outcome != cedar_outcome,
            )
            span.set_attribute("cao.refinery.policy.authoritative", self._authoritative)

        return yaml_outcome if self._authoritative == "yaml" else cedar_outcome


# ---------------------------------------------------------------------------
# Engine selection
# ---------------------------------------------------------------------------


def select_policy(
    *,
    yaml_policy: Optional[Policy] = None,
    cedar_policy: Optional[Policy] = None,
    engine_env: str = "CAO_REFINERY_ENGINE",
) -> Policy:
    """Pick the runtime policy engine from the env var.

    Returns:
      - YamlRulePolicy directly when CAO_REFINERY_ENGINE=yaml (default)
      - ParallelEvaluatingPolicy(yaml, cedar, authoritative='yaml') when
        CAO_REFINERY_ENGINE=parallel
      - ParallelEvaluatingPolicy(yaml, cedar, authoritative='cedar') when
        CAO_REFINERY_ENGINE=cedar

    Unknown values fall back to ``yaml`` with a warning — operators
    typo'ing the env var shouldn't break the gate.
    """
    engine = os.environ.get(engine_env, "yaml").lower()
    yaml_policy = yaml_policy or PermissivePolicy()
    cedar_policy = cedar_policy or CedarPolicy()

    if engine == "yaml":
        return yaml_policy
    if engine == "parallel":
        return ParallelEvaluatingPolicy(
            yaml_policy=yaml_policy,
            cedar_policy=cedar_policy,
            authoritative="yaml",
        )
    if engine == "cedar":
        return ParallelEvaluatingPolicy(
            yaml_policy=yaml_policy,
            cedar_policy=cedar_policy,
            authoritative="cedar",
        )
    logger.warning("Unknown %s=%r; falling back to yaml", engine_env, engine)
    return yaml_policy


__all__ = [
    "CedarPolicy",
    "ParallelEvaluatingPolicy",
    "select_policy",
]
