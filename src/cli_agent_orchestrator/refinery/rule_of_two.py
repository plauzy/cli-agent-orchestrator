"""Rule-of-Two tool classification (Phase 3 / commit 11).

Meta's Rule-of-Two: a tool that simultaneously
  (a) consumes untrusted input,
  (b) accesses sensitive data, AND
  (c) changes state
is too dangerous to invoke without an explicit operator confirmation.
The Refinery uses this classification to early-deny (or escalate) the
worst-case combinations *before* policy evaluation runs.

Tools register their classification once at import time via
``classify(action, untrusted, sensitive, change_state)``. The Refinery
looks up the registered triple per ``WriteRequest.action``; an
unknown action defaults to ``(False, False, True)`` — change_state
without untrusted/sensitive — which the Rule-of-Two trivially allows.
This default keeps the gate's behavior conservative-but-permissive
for actions that haven't been classified yet.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Classification:
    """Tool risk triple per the Meta Rule-of-Two framework."""

    untrusted_input: bool
    sensitive_data: bool
    change_state: bool

    @property
    def violates_rule_of_two(self) -> bool:
        return self.untrusted_input and self.sensitive_data and self.change_state


_REGISTRY: dict[str, Classification] = {}


def classify(
    action: str,
    *,
    untrusted_input: bool,
    sensitive_data: bool,
    change_state: bool,
) -> None:
    """Register a Rule-of-Two classification for ``action``.

    Idempotent: re-registering the same action with the same triple
    is a no-op. Re-registering with a *different* triple raises so we
    catch conflicting declarations at import time.
    """
    triple = Classification(untrusted_input, sensitive_data, change_state)
    existing = _REGISTRY.get(action)
    if existing is not None and existing != triple:
        raise ValueError(
            f"Rule-of-Two conflict for action {action!r}: " f"existing={existing}, new={triple}"
        )
    _REGISTRY[action] = triple


def lookup(action: str) -> Classification:
    """Return the classification for ``action``, or a conservative default.

    Default is ``change_state=True`` only — by definition the action
    arrived through the Refinery, which only handles state-mutating
    requests, so change_state is implied. Untrusted/sensitive default
    to False since we can't assume them; the Rule-of-Two doesn't fire
    on (False, False, True) and policy evaluation runs as usual.
    """
    return _REGISTRY.get(action, Classification(False, False, True))


def reset_registry_for_tests() -> None:
    """Test helper. Production code should never call this."""
    _REGISTRY.clear()


# Default classifications for the Phase 1 mutation set.
#
# Note: Meta's Rule-of-Two targets the worst-case combination of
# (untrusted external input) + (sensitive data access) + (state change).
# CAO's internal mutations don't hit that bar today — the inbox path
# only carries CAO-internal traffic between processes the same operator
# already authorized. So every Phase 1 mutation is classified as
# change_state=True only. Operators who want stricter gating on specific
# actions (e.g., delete_terminals_by_session in production) declare it
# via the YamlRulePolicy rule list rather than re-classifying here.
#
# When CAO eventually accepts external A2A traffic that requests a
# state mutation (Phase 5+), the new actions registered for that path
# should set untrusted_input=True and the Rule-of-Two will fire when
# combined with sensitive_data.
classify("create_terminal", untrusted_input=False, sensitive_data=False, change_state=True)
classify("delete_terminal", untrusted_input=False, sensitive_data=False, change_state=True)
classify(
    "delete_terminals_by_session",
    untrusted_input=False,
    sensitive_data=False,
    change_state=True,
)
classify("create_inbox_message", untrusted_input=False, sensitive_data=False, change_state=True)
classify("update_message_status", untrusted_input=False, sensitive_data=False, change_state=True)
classify("create_flow", untrusted_input=False, sensitive_data=False, change_state=True)
classify("update_flow_run_times", untrusted_input=False, sensitive_data=False, change_state=True)
classify("update_flow_enabled", untrusted_input=False, sensitive_data=False, change_state=True)
classify("delete_flow", untrusted_input=False, sensitive_data=False, change_state=True)
