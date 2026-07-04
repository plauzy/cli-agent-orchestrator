"""Tests for the Rule-of-Two classification registry (commit 11)."""

from __future__ import annotations

import pytest

from cli_agent_orchestrator.refinery.rule_of_two import (
    Classification,
    classify,
    lookup,
)


class TestClassification:
    def test_violates_only_when_all_three_true(self):
        assert Classification(True, True, True).violates_rule_of_two
        # Any one false → permitted.
        assert not Classification(False, True, True).violates_rule_of_two
        assert not Classification(True, False, True).violates_rule_of_two
        assert not Classification(True, True, False).violates_rule_of_two

    def test_no_flag_is_permitted(self):
        assert not Classification(False, False, False).violates_rule_of_two


class TestRegistry:
    def test_lookup_returns_registered_classification(self):
        # Classifications registered at import-time.
        c = lookup("create_terminal")
        assert c.change_state is True
        assert c.untrusted_input is False
        assert c.sensitive_data is False

    def test_unknown_action_defaults_to_change_state_only(self):
        c = lookup("an_action_we_never_registered")
        assert c == Classification(False, False, True)

    def test_re_registering_same_triple_is_noop(self):
        # Already registered at import; calling again with the same
        # triple must not raise.
        classify(
            "create_terminal",
            untrusted_input=False,
            sensitive_data=False,
            change_state=True,
        )

    def test_re_registering_different_triple_raises(self):
        with pytest.raises(ValueError, match="Rule-of-Two conflict"):
            classify(
                "create_terminal",
                untrusted_input=True,
                sensitive_data=True,
                change_state=True,
            )

    def test_phase_1_mutations_do_not_violate_rule_of_two(self):
        # Important — Phase 1 mutations must not be Rule-of-Two-denied
        # by default, otherwise Refinery rejects every inbox message.
        for action in (
            "create_terminal",
            "delete_terminal",
            "delete_terminals_by_session",
            "create_inbox_message",
            "update_message_status",
            "create_flow",
            "update_flow_run_times",
            "update_flow_enabled",
            "delete_flow",
        ):
            assert not lookup(action).violates_rule_of_two, action
