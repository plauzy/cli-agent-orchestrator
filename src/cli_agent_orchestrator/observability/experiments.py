"""Bucketed-experiment primitive for v2.5 A/B testing patterns.

The Phase 4 + Phase 5 plan files document four A/B testing patterns:

  * Pattern A — held-out improvement benchmark (offline, paired bootstrap CI)
  * Pattern B — shadow-mode evaluation (env-flag-gated, runs both paths)
  * Pattern C — bucketed online experiment (this module)
  * Pattern D — kill-switch as auto-rollback (rides Phase 4 infrastructure)

This module ships Pattern C as a tiny stateless primitive: a stable
deterministic hash bucket keyed by ``(task_id, salt)``. Variant
assignment is recorded on every dispatch via ``cao.experiment.variant``
on the existing ``cao.dispatch`` span — no separate event store. Per-
variant aggregation comes via the existing WAL ``asi.mitigation``
records (filter on the variant tag), so adding an experiment doesn't
require a new schema.

Operators document the experiment in ``docs/runbooks.md`` and the
runbook horizon (e.g. one week, sequential testing) is what gates
the conclusion. The primitive itself is intentionally simple — no
storage, no lifecycle, no SDK. If you need richer tooling, layer it
on top.

Example::

    from cli_agent_orchestrator.observability.experiments import bucket

    variant = bucket(task_id, salt="anchoring-v1")
    if variant == "treatment":
        anchors = get_anchor_registry().anchors_for(task_class)
    else:
        anchors = None
    await dispatch_task(request, anchors=anchors)
"""

from __future__ import annotations

import hashlib
from typing import Literal

Variant = Literal["control", "treatment"]


def bucket(task_id: str, salt: str = "") -> Variant:
    """Stable 50/50 bucket assignment for a task.

    Pure function: same ``(task_id, salt)`` always returns the same
    variant within and across processes. Use the same ``salt`` for the
    duration of an experiment; rotate to ``salt + "-v2"`` to start a
    fresh assignment without re-shuffling existing tasks.

    Distribution is balanced to within bias of SHA-256, which is well
    below the noise floor for any realistic task volume.
    """
    digest = hashlib.sha256(f"{salt}|{task_id}".encode("utf-8")).digest()
    # Take the first byte; even values → control, odd → treatment.
    # SHA-256's first byte is uniform over 0..255, so the split is 50/50.
    return "treatment" if digest[0] & 1 else "control"


def is_treatment(task_id: str, salt: str = "") -> bool:
    """Convenience: ``bucket(...) == "treatment"``."""
    return bucket(task_id, salt) == "treatment"
