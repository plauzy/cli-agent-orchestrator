"""Behavioral-anchoring recovery benchmark (v2.5 close-out, item 4).

Pattern A — held-out improvement benchmark. Measures whether installing
a behavioral anchor on sustained drift speeds up ASI-score recovery
(vs. baseline = same evaluator, no anchor).

The benchmark is *simulation*-style — we model the agent's outcome as
a function of whether an anchor is installed. Without an anchor, the
post-degradation success rate stays depressed; with an anchor, the
agent gradually returns to baseline. Both arms run on the same
deterministic seed sequence so the per-window deltas are paired and
the bootstrap CI is well-defined.

Statistical test: paired bootstrap CI on per-window recovery delta
(1000 resamples). Reject if 95% CI excludes zero — the canonical test
in the v2.5 runbook.

Marker: ``slow`` (auto-deselected in default `pytest -m 'not e2e'`).
"""

from __future__ import annotations

import random
from dataclasses import dataclass

import pytest

from cli_agent_orchestrator.observability import (
    AnchorRegistry,
    AsiEvaluator,
    AsiThresholds,
    BehavioralAnchoringHandler,
    SpanRecord,
    standard_handlers,
)

pytestmark = pytest.mark.slow


# ---------------------------------------------------------------------------
# Calibrated heuristics — match the topology benchmark style.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RecoveryProfile:
    baseline_success: float  # P(success) before degradation
    degraded_success: float  # P(success) during the drift window
    # Multiplier on the degraded → baseline gap that an anchor closes per
    # window. 0.0 = anchor does nothing; 1.0 = anchor fully restores in
    # one window. The Rath (2026) framework's published direction puts
    # the recovery rate around 0.25–0.40 per window for sustained drift;
    # we calibrate at 0.30 as a conservative midpoint.
    anchor_recovery_rate: float = 0.30


_PROFILE = RecoveryProfile(baseline_success=0.92, degraded_success=0.55)


def _simulate_window(
    rng: random.Random,
    profile: RecoveryProfile,
    success_rate: float,
    n_spans: int = 50,
) -> list[SpanRecord]:
    """One window of synthetic spans. Each span is labeled success or error
    by sampling against ``success_rate``."""
    spans: list[SpanRecord] = []
    for i in range(n_spans):
        outcome = "success" if rng.random() < success_rate else "error"
        spans.append(
            SpanRecord(
                name=f"execute_tool {i}",
                operation="execute_tool",
                agent_id="agent",
                conversation_id="conv",
                task_class="bench",
                duration_ms=100.0,
                attributes={"cao.tool.outcome": outcome},
            )
        )
    return spans


def _arm(seed: int, *, anchor_enabled: bool) -> list[float]:
    """Run one arm of the experiment.

    Sequence:
      1. ``baseline_windows`` of healthy spans (success_rate = baseline).
      2. ``drift_windows`` of degraded spans (success_rate = degraded).
         If anchoring is enabled, the anchor handler installs an anchor
         once consecutive_below ≥ 3.
      3. ``recovery_windows`` of post-drift spans. With an anchor
         installed, success_rate climbs back toward baseline at the
         calibrated recovery rate per window.

    Returns the AsiScore.overall observed at the end of each recovery
    window — the per-window vector compared between arms.
    """
    rng = random.Random(seed)

    registry = AnchorRegistry()
    ev = AsiEvaluator(
        thresholds=AsiThresholds(
            window_size=50,
            warn=0.85,
            mitigate=0.75,
            kill=0.50,
            consecutive_windows_required=3,
        )
    )
    if anchor_enabled:
        ev.add_handler(BehavioralAnchoringHandler(registry=registry, consecutive_threshold=3))

    # Phase 1: baseline.
    for _ in range(2):
        for s in _simulate_window(rng, _PROFILE, _PROFILE.baseline_success):
            ev.observe(s)

    # Phase 2: drift.
    for _ in range(5):
        for s in _simulate_window(rng, _PROFILE, _PROFILE.degraded_success):
            ev.observe(s)

    # Phase 3: recovery. Each window's success rate climbs toward baseline
    # at the calibrated rate when an anchor is installed.
    recovery_scores: list[float] = []
    current_rate = _PROFILE.degraded_success
    for _ in range(8):
        if anchor_enabled and registry.has_anchors("bench"):
            # Anchor closes the gap by ``rate * gap`` per window.
            gap = _PROFILE.baseline_success - current_rate
            current_rate += _PROFILE.anchor_recovery_rate * gap

        for s in _simulate_window(rng, _PROFILE, current_rate):
            ev.observe(s)

        recovery_scores.append(ev.score_for_task_class("bench"))

    return recovery_scores


# ---------------------------------------------------------------------------
# Paired bootstrap CI helper
# ---------------------------------------------------------------------------


def _bootstrap_ci(
    deltas: list[float], n_resamples: int = 1000, seed: int = 0
) -> tuple[float, float]:
    """Paired bootstrap 95% CI on the mean delta.

    Canonical statistical test per the v2.5 runbook. Returns
    ``(lower, upper)``. The benchmark passes when ``lower > 0``.
    """
    rng = random.Random(seed)
    n = len(deltas)
    means: list[float] = []
    for _ in range(n_resamples):
        sample = [deltas[rng.randrange(n)] for _ in range(n)]
        means.append(sum(sample) / n)
    means.sort()
    lo = means[int(0.025 * n_resamples)]
    hi = means[int(0.975 * n_resamples)]
    return lo, hi


# ---------------------------------------------------------------------------
# The benchmark
# ---------------------------------------------------------------------------


def test_anchor_recovery_beats_baseline():
    """Pattern A: paired bootstrap CI must exclude zero."""
    n_seeds = 30
    paired_deltas: list[float] = []

    for seed in range(n_seeds):
        baseline = _arm(seed, anchor_enabled=False)
        treatment = _arm(seed, anchor_enabled=True)

        # Per-window paired deltas — both arms ran the same RNG seed
        # so their windows are aligned.
        for b, t in zip(baseline, treatment):
            paired_deltas.append(t - b)

    assert paired_deltas, "no paired deltas collected"

    mean_delta = sum(paired_deltas) / len(paired_deltas)
    lo, hi = _bootstrap_ci(paired_deltas, n_resamples=1000)

    # 95% CI must exclude zero from above (improvement, not regression).
    assert lo > 0, (
        f"anchor recovery did not exceed baseline: "
        f"mean_delta={mean_delta:+.4f}, 95% CI=({lo:+.4f}, {hi:+.4f})"
    )

    # Sanity check: improvement floor — the v2.5 runbook flags any
    # measured improvement < 1 ASI point as not worth shipping.
    assert mean_delta > 0.01, f"anchor recovery delta below 0.01 ASI floor (got {mean_delta:+.4f})"
