"""Tests for the Cedar adapter + parallel-evaluation policy (v2.5 close-out)."""

from __future__ import annotations

from typing import Any

import pytest

from cli_agent_orchestrator.refinery import (
    CedarPolicy,
    ParallelEvaluatingPolicy,
    PermissivePolicy,
    PolicyOutcome,
    select_policy,
)


class _StaticPolicy:
    def __init__(self, outcome: PolicyOutcome) -> None:
        self.outcome = outcome
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def evaluate(self, action: str, payload: dict[str, Any]) -> PolicyOutcome:
        self.calls.append((action, payload))
        return self.outcome


class TestCedarPolicy:
    def test_permissive_when_engine_unavailable(self):
        # The test environment doesn't install cedarpy by default. The
        # adapter must behave permissively rather than crash so opting
        # into Cedar later is a deployment-level change, not a code one.
        cedar = CedarPolicy(policies="permit (principal, action, resource);")
        assert cedar.evaluate("create_terminal", {}) == PolicyOutcome.ALLOW

    def test_permissive_when_no_policies(self):
        cedar = CedarPolicy(policies="")
        assert cedar.evaluate("anything", {}) == PolicyOutcome.ALLOW


class TestParallelEvaluatingPolicy:
    def test_yaml_authoritative_returns_yaml_outcome(self):
        yaml = _StaticPolicy(PolicyOutcome.ALLOW)
        cedar = _StaticPolicy(PolicyOutcome.DENY)

        policy = ParallelEvaluatingPolicy(
            yaml_policy=yaml, cedar_policy=cedar, authoritative="yaml"
        )

        assert policy.evaluate("act", {}) == PolicyOutcome.ALLOW
        # Both engines saw the request — divergence is observable.
        assert len(yaml.calls) == 1
        assert len(cedar.calls) == 1

    def test_cedar_authoritative_returns_cedar_outcome(self):
        yaml = _StaticPolicy(PolicyOutcome.ALLOW)
        cedar = _StaticPolicy(PolicyOutcome.DENY)

        policy = ParallelEvaluatingPolicy(
            yaml_policy=yaml, cedar_policy=cedar, authoritative="cedar"
        )

        assert policy.evaluate("act", {}) == PolicyOutcome.DENY

    def test_cedar_failure_falls_back_to_yaml(self):
        yaml = _StaticPolicy(PolicyOutcome.ALLOW)

        class _ExplodingCedar:
            def evaluate(self, action, payload):
                raise RuntimeError("cedar exploded")

        policy = ParallelEvaluatingPolicy(
            yaml_policy=yaml, cedar_policy=_ExplodingCedar(), authoritative="yaml"
        )

        # No exception escapes; the YAML decision is returned.
        assert policy.evaluate("act", {}) == PolicyOutcome.ALLOW

    def test_invalid_authoritative_raises(self):
        with pytest.raises(ValueError):
            ParallelEvaluatingPolicy(
                yaml_policy=PermissivePolicy(),
                cedar_policy=PermissivePolicy(),
                authoritative="opa",  # not yet supported
            )


class TestSelectPolicy:
    def test_yaml_engine_default(self, monkeypatch):
        monkeypatch.delenv("CAO_REFINERY_ENGINE", raising=False)
        yaml = _StaticPolicy(PolicyOutcome.ALLOW)
        out = select_policy(yaml_policy=yaml)
        assert out is yaml

    def test_parallel_engine_yaml_authoritative(self, monkeypatch):
        monkeypatch.setenv("CAO_REFINERY_ENGINE", "parallel")
        out = select_policy()
        assert isinstance(out, ParallelEvaluatingPolicy)
        # YAML authoritative — same outcome as the yaml policy.

    def test_cedar_engine_authoritative(self, monkeypatch):
        monkeypatch.setenv("CAO_REFINERY_ENGINE", "cedar")
        out = select_policy()
        assert isinstance(out, ParallelEvaluatingPolicy)

    def test_unknown_engine_falls_back_to_yaml(self, monkeypatch):
        monkeypatch.setenv("CAO_REFINERY_ENGINE", "ZALGO")
        yaml = _StaticPolicy(PolicyOutcome.ALLOW)
        out = select_policy(yaml_policy=yaml)
        assert out is yaml
