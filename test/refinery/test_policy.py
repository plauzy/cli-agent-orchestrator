"""Tests for the Refinery policy implementations (commit 11)."""

from __future__ import annotations

from pathlib import Path

import pytest

from cli_agent_orchestrator.refinery.policy import (
    PermissivePolicy,
    PolicyOutcome,
    YamlRulePolicy,
)


class TestPermissivePolicy:
    def test_always_returns_allow(self):
        policy = PermissivePolicy()
        assert policy.evaluate("create_terminal", {}) == PolicyOutcome.ALLOW
        assert policy.evaluate("delete_terminal", {"id": "x"}) == PolicyOutcome.ALLOW
        assert policy.evaluate("totally_made_up_action", {}) == PolicyOutcome.ALLOW


class TestYamlRulePolicyDirect:
    def test_empty_rules_yield_allow(self):
        assert YamlRulePolicy([]).evaluate("any", {}) == PolicyOutcome.ALLOW

    def test_action_match_denies(self):
        policy = YamlRulePolicy([{"action": "delete_flow", "outcome": "deny"}])
        assert policy.evaluate("delete_flow", {}) == PolicyOutcome.DENY
        # Unrelated action → falls through.
        assert policy.evaluate("create_terminal", {}) == PolicyOutcome.ALLOW

    def test_payload_regex_matches(self):
        policy = YamlRulePolicy(
            [
                {
                    "action": "delete_terminals_by_session",
                    "payload_match": {"tmux_session": "^prod-"},
                    "outcome": "escalate",
                }
            ]
        )
        # prod-* → escalate.
        assert (
            policy.evaluate("delete_terminals_by_session", {"tmux_session": "prod-east-1"})
            == PolicyOutcome.ESCALATE
        )
        # dev-* → allow.
        assert (
            policy.evaluate("delete_terminals_by_session", {"tmux_session": "dev-laptop"})
            == PolicyOutcome.ALLOW
        )

    def test_first_matching_rule_wins(self):
        policy = YamlRulePolicy(
            [
                {
                    "action": "delete_terminal",
                    "payload_match": {"id": "^safe-"},
                    "outcome": "allow",
                },
                {"action": "delete_terminal", "outcome": "deny"},
            ]
        )
        assert policy.evaluate("delete_terminal", {"id": "safe-1"}) == PolicyOutcome.ALLOW
        assert policy.evaluate("delete_terminal", {"id": "other"}) == PolicyOutcome.DENY

    def test_action_wildcard_matches_anything(self):
        policy = YamlRulePolicy([{"payload_match": {"sender_id": "^attacker-"}, "outcome": "deny"}])
        assert (
            policy.evaluate("create_inbox_message", {"sender_id": "attacker-1"})
            == PolicyOutcome.DENY
        )
        assert (
            policy.evaluate("update_message_status", {"sender_id": "attacker-1"})
            == PolicyOutcome.DENY
        )
        assert (
            policy.evaluate("create_inbox_message", {"sender_id": "user-42"}) == PolicyOutcome.ALLOW
        )


class TestYamlRulePolicyFromFile:
    def test_missing_file_yields_empty_policy(self, tmp_path: Path):
        policy = YamlRulePolicy.from_file(tmp_path / "does-not-exist.yaml")
        assert policy.evaluate("anything", {}) == PolicyOutcome.ALLOW

    def test_parses_yaml_rules(self, tmp_path: Path):
        # Skip if PyYAML isn't installed in the test env.
        pytest.importorskip("yaml")
        path = tmp_path / "rules.yaml"
        path.write_text(
            """
            rules:
              - action: delete_flow
                outcome: deny
              - action: delete_terminals_by_session
                payload_match:
                  tmux_session: "^prod-"
                outcome: escalate
            """,
            encoding="utf-8",
        )
        policy = YamlRulePolicy.from_file(path)
        assert policy.evaluate("delete_flow", {}) == PolicyOutcome.DENY
        assert (
            policy.evaluate("delete_terminals_by_session", {"tmux_session": "prod-x"})
            == PolicyOutcome.ESCALATE
        )
        assert policy.evaluate("create_terminal", {}) == PolicyOutcome.ALLOW
