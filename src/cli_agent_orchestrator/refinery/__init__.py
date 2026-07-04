"""Refinery write queue: the single-threaded gate for state mutations.

Phase 3 / commit 11 ships:
  * ``RefineryQueue.submit(WriteRequest)`` — serialized through an
    asyncio.Lock; runs Rule-of-Two + policy + optional WAL append
    + caller-supplied executor.
  * Pluggable ``Policy`` Protocol with ``PermissivePolicy`` (default,
    matches v1.x behavior) and ``YamlRulePolicy`` (simple operator-
    managed rule list).
  * Rule-of-Two classification registry — tools register their
    (untrusted, sensitive, change_state) triple; the Refinery early-
    denies any combination with all three flags.

Cedar / cedarpy integration is deferred to v2.6.
"""

from cli_agent_orchestrator.refinery.cedar_policy import (
    CedarPolicy,
    ParallelEvaluatingPolicy,
    select_policy,
)
from cli_agent_orchestrator.refinery.policy import (
    PermissivePolicy,
    Policy,
    PolicyOutcome,
    YamlRulePolicy,
)
from cli_agent_orchestrator.refinery.queue import (
    RefineryDenied,
    RefineryEscalated,
    RefineryQueue,
    RefineryResult,
    SyncWriteRequest,
    WriteRequest,
    get_refinery_queue,
    set_refinery_queue,
    submit_sync_or_run,
)
from cli_agent_orchestrator.refinery.rule_of_two import (
    Classification,
    classify,
    lookup,
)

__all__ = [
    "CedarPolicy",
    "Classification",
    "ParallelEvaluatingPolicy",
    "PermissivePolicy",
    "Policy",
    "PolicyOutcome",
    "RefineryDenied",
    "RefineryEscalated",
    "RefineryQueue",
    "RefineryResult",
    "SyncWriteRequest",
    "WriteRequest",
    "YamlRulePolicy",
    "classify",
    "get_refinery_queue",
    "lookup",
    "select_policy",
    "set_refinery_queue",
    "submit_sync_or_run",
]
