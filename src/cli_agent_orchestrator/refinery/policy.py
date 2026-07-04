"""Pluggable policy evaluation for the Refinery write queue (Phase 3 / commit 11).

The Refinery is the single-threaded write gate that every state-mutating
action passes through. Policy evaluation runs *before* the WAL append
and the actual mutation. Three outcomes are possible:

  * ALLOW    — proceed with the write
  * DENY     — reject without side effects
  * ESCALATE — pause; emit an input-required SSE event so the operator
               can approve via the MCP App widget (Phase 5 wiring)

Phase 3 ships:
  * a ``Policy`` Protocol so future implementations (Cedar in v2.6, OPA
    in v2.7, ...) drop in without touching ``RefineryQueue``,
  * a ``PermissivePolicy`` that always allows — matches v1.x behavior
    so commit 11 is a no-op for existing call sites,
  * a ``YamlRulePolicy`` that reads a small YAML rule list from
    ``~/.aws/cli-agent-orchestrator/refinery/rules.yaml`` for operators
    who want to deny or escalate specific actions today.

Cedar / cedarpy integration is deliberately deferred to v2.6 — we don't
need a full policy engine until per-tenant rule complexity actually
arrives, and adding cedarpy now would be premature in the same way
the libsql swap was deferred from commit 5.
"""

from __future__ import annotations

import logging
from enum import Enum
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

logger = logging.getLogger(__name__)


class PolicyOutcome(str, Enum):
    ALLOW = "allow"
    DENY = "deny"
    ESCALATE = "escalate"


@runtime_checkable
class Policy(Protocol):
    """A pluggable Refinery policy evaluator.

    Implementations must be cheap and side-effect-free — they run
    inside the Refinery's single-writer lock, so blocking I/O here
    serializes every other write. Heavy work belongs in a coroutine
    upstream, not in ``evaluate``.
    """

    def evaluate(self, action: str, payload: dict[str, Any]) -> PolicyOutcome: ...


class PermissivePolicy:
    """Always-ALLOW policy. Matches v1.x behavior; the v2.5 default."""

    def evaluate(self, action: str, payload: dict[str, Any]) -> PolicyOutcome:
        return PolicyOutcome.ALLOW


class YamlRulePolicy:
    """Loads a small ordered rule list from a YAML file.

    Rule schema::

        rules:
          - action: "delete_terminal"
            payload_match: {tmux_session: "^prod-"}  # regex per field
            outcome: "escalate"
            reason: "production session — operator confirms"
          - action: "delete_flow"
            outcome: "deny"

    Rules are evaluated in order; the first match wins. Rules without a
    ``payload_match`` match every payload for that action. Rules without
    an ``action`` (only payload match) match every action — useful for
    catch-all denies like "any payload mentioning prod-".

    Anything not matched falls back to ``ALLOW``.

    Phase 3 reads the file once at construction time. The ``rules.yaml``
    is operator-managed; reload requires a server restart, which we
    accept because policy churn is low-frequency.
    """

    def __init__(self, rules: list[dict[str, Any]]) -> None:
        # Pre-compile regex matchers for O(1) per-rule evaluation.
        import re as _re

        self._rules = []
        for rule in rules:
            compiled_match = {
                k: _re.compile(v) for k, v in (rule.get("payload_match") or {}).items()
            }
            self._rules.append(
                {
                    "action": rule.get("action"),
                    "payload_match": compiled_match,
                    "outcome": PolicyOutcome(rule.get("outcome", "deny")),
                    "reason": rule.get("reason", ""),
                }
            )

    @classmethod
    def from_file(cls, path: Path) -> "YamlRulePolicy":
        """Load from a YAML file; missing file → permissive (empty rules)."""
        if not path.exists():
            return cls([])
        try:
            import yaml as _yaml  # type: ignore[import-not-found,import-untyped]
        except ImportError:
            logger.warning(
                "PyYAML not available; YamlRulePolicy at %s will be empty (permissive)",
                path,
            )
            return cls([])
        try:
            data = _yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            return cls(data.get("rules", []))
        except Exception:
            logger.warning("Failed to parse %s; falling back to permissive", path, exc_info=True)
            return cls([])

    def evaluate(self, action: str, payload: dict[str, Any]) -> PolicyOutcome:
        for rule in self._rules:
            if rule["action"] is not None and rule["action"] != action:
                continue
            if not self._payload_matches(rule["payload_match"], payload):
                continue
            return rule["outcome"]  # type: ignore[no-any-return]
        return PolicyOutcome.ALLOW

    @staticmethod
    def _payload_matches(matchers: dict[str, Any], payload: dict[str, Any]) -> bool:
        for key, regex in matchers.items():
            value = payload.get(key)
            if value is None or not regex.search(str(value)):
                return False
        return True
