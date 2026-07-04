"""Tests for the bucketed-experiment primitive (v2.5 close-out, Pattern C)."""

from __future__ import annotations

from collections import Counter

import pytest

from cli_agent_orchestrator.observability import bucket, is_treatment


class TestBucket:
    def test_returns_one_of_two_variants(self):
        v = bucket("task-1")
        assert v in {"control", "treatment"}

    def test_stable_for_same_inputs(self):
        # Same task_id + salt → same variant, deterministically.
        for _ in range(3):
            assert bucket("task-1", salt="exp-1") == bucket("task-1", salt="exp-1")

    def test_different_salt_can_yield_different_variant(self):
        # Different salts MAY (and statistically should) give different
        # assignments for at least some tasks.
        per_salt = {
            salt: [bucket(f"t-{i}", salt=salt) for i in range(200)] for salt in ("salt-a", "salt-b")
        }
        # Different runs over the same 200 tasks should disagree on
        # roughly half of them.
        disagreements = sum(1 for a, b in zip(per_salt["salt-a"], per_salt["salt-b"]) if a != b)
        assert 60 <= disagreements <= 140  # 50/50 ± noise on n=200

    def test_distribution_is_balanced(self):
        # Across 1000 tasks, control / treatment should be 50/50 ± ~5%.
        counts = Counter(bucket(f"t-{i}") for i in range(1000))
        # Both variants present, and within tolerance.
        assert counts["control"] + counts["treatment"] == 1000
        assert 400 <= counts["control"] <= 600
        assert 400 <= counts["treatment"] <= 600

    def test_is_treatment_matches_bucket(self):
        for i in range(50):
            tid = f"task-{i}"
            assert is_treatment(tid) == (bucket(tid) == "treatment")
