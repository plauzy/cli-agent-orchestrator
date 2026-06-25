"""Unit tests for Antigravity CLI (`agy`) provider.

Regex-constant calibration is verified here against the captured fixture
set under ``test/providers/fixtures/antigravity_cli_*.txt``. Each
calibrated pattern gets a positive assertion (matches the right-state
fixture) and a negative assertion (does NOT match a wrong-state fixture)
so regressions on either side are caught.

The provider-class integration tests (initialization, command-building,
extraction, lifecycle) are intentionally left as ``pytest.skip()``
placeholders — they require a tmux mock layer that is not yet wired in
for this provider and will land alongside the ROADMAP §3/§4 work.
"""

import re
from pathlib import Path

import pytest

from cli_agent_orchestrator.providers.antigravity_cli import (
    ANSI_CODE_PATTERN,
    INPUT_BOX_RULE_PATTERN,
    PROCESSING_SPINNER_PATTERN,
    QUERY_LINE_PATTERN,
    RESPONSE_INDENT_PATTERN,
    STATUS_BAR_IDLE_PATTERN,
    STATUS_BAR_MODEL_PATTERN,
    STATUS_BAR_PROCESSING_PATTERN,
    TRUST_FOLDER_PROMPT_PATTERN,
    WELCOME_BANNER_PATTERN,
    WELCOME_VERSION_PATTERN,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _read_fixture(name: str) -> str:
    return (FIXTURES_DIR / name).read_text()


def _strip_ansi(text: str) -> str:
    return re.sub(ANSI_CODE_PATTERN, "", text)


# =============================================================================
# Regex calibration tests — fixture-driven positive + negative coverage
# =============================================================================


class TestAntigravityCliRegexCalibration:
    """Verifies each calibrated regex against the captured fixture set.

    Hard rule: when a test fails, tighten the regex — do NOT weaken the test.
    """

    # -------------------------------------------------------------------------
    # Status bar — IDLE / COMPLETED ("? for shortcuts")
    # -------------------------------------------------------------------------

    def test_status_bar_idle_matches_response_fixture(self):
        """STATE 4 / response fixture must show '? for shortcuts'."""
        clean = _strip_ansi(_read_fixture("antigravity_cli_response.txt"))
        assert re.search(
            STATUS_BAR_IDLE_PATTERN, clean
        ), "IDLE status-bar pattern should match the response (COMPLETED) fixture"

    def test_status_bar_idle_matches_tool_call_fixture(self):
        """Tool-call completed state also reverts to '? for shortcuts'."""
        clean = _strip_ansi(_read_fixture("antigravity_cli_tool_call.txt"))
        assert re.search(STATUS_BAR_IDLE_PATTERN, clean)

    def test_status_bar_idle_does_not_match_processing_fixture(self):
        """While processing, status bar is 'esc to cancel' — IDLE must not match."""
        clean = _strip_ansi(_read_fixture("antigravity_cli_processing.txt"))
        assert not re.search(
            STATUS_BAR_IDLE_PATTERN, clean
        ), "IDLE pattern false-positive against PROCESSING fixture"

    # -------------------------------------------------------------------------
    # Status bar — PROCESSING ("esc to cancel")
    # -------------------------------------------------------------------------

    def test_status_bar_processing_matches_processing_fixture(self):
        clean = _strip_ansi(_read_fixture("antigravity_cli_processing.txt"))
        assert re.search(STATUS_BAR_PROCESSING_PATTERN, clean)

    def test_status_bar_processing_matches_permission_fixture(self):
        """Permission-prompt fixture is mid-processing ('Working...' spinner)."""
        clean = _strip_ansi(_read_fixture("antigravity_cli_permission.txt"))
        assert re.search(STATUS_BAR_PROCESSING_PATTERN, clean)

    def test_status_bar_processing_does_not_match_response_fixture(self):
        """Completed response shows '? for shortcuts', never 'esc to cancel'."""
        clean = _strip_ansi(_read_fixture("antigravity_cli_response.txt"))
        assert not re.search(STATUS_BAR_PROCESSING_PATTERN, clean)

    # -------------------------------------------------------------------------
    # Status bar — model indicator (right edge)
    # -------------------------------------------------------------------------

    def test_status_bar_model_matches_response_fixture(self):
        """Status bar right edge always carries the model name."""
        clean = _strip_ansi(_read_fixture("antigravity_cli_response.txt"))
        assert re.search(STATUS_BAR_MODEL_PATTERN, clean)

    # -------------------------------------------------------------------------
    # Spinner — Braille glyph + verb
    # -------------------------------------------------------------------------

    def test_processing_spinner_matches_generating_in_processing_fixture(self):
        """`⣾  Generating...` is the canonical PROCESSING signal."""
        clean = _strip_ansi(_read_fixture("antigravity_cli_processing.txt"))
        assert re.search(PROCESSING_SPINNER_PATTERN, clean)

    def test_processing_spinner_matches_working_in_permission_fixture(self):
        """Permission fixture uses `⢿  Working...` — calibration extended the
        verb list to include `Working`."""
        clean = _strip_ansi(_read_fixture("antigravity_cli_permission.txt"))
        assert re.search(
            PROCESSING_SPINNER_PATTERN, clean
        ), "PROCESSING_SPINNER_PATTERN missing `Working` verb"

    def test_processing_spinner_does_not_match_response_fixture(self):
        """Completed response has no spinner glyph + verb sequence."""
        clean = _strip_ansi(_read_fixture("antigravity_cli_response.txt"))
        assert not re.search(PROCESSING_SPINNER_PATTERN, clean)

    # -------------------------------------------------------------------------
    # Welcome banner / version
    # -------------------------------------------------------------------------

    def test_welcome_banner_matches_response_fixture(self):
        """Welcome banner is rendered on every interactive launch."""
        clean = _strip_ansi(_read_fixture("antigravity_cli_response.txt"))
        assert re.search(
            WELCOME_BANNER_PATTERN, clean
        ), "WELCOME_BANNER_PATTERN should match the banner row in fixtures"

    def test_welcome_version_matches_response_fixture(self):
        clean = _strip_ansi(_read_fixture("antigravity_cli_response.txt"))
        assert re.search(WELCOME_VERSION_PATTERN, clean)

    # -------------------------------------------------------------------------
    # Trust-folder prompt (first-launch interactive overlay)
    # -------------------------------------------------------------------------

    def test_trust_folder_prompt_matches_interactive_clean_fixture(self):
        """STATE 1 of the multi-state clean capture is the trust prompt."""
        text = _read_fixture("antigravity_cli_interactive_clean.txt")
        assert re.search(TRUST_FOLDER_PROMPT_PATTERN, text)

    def test_trust_folder_prompt_does_not_match_response_fixture(self):
        clean = _strip_ansi(_read_fixture("antigravity_cli_response.txt"))
        assert not re.search(TRUST_FOLDER_PROMPT_PATTERN, clean)

    # -------------------------------------------------------------------------
    # Query / response structural patterns
    # -------------------------------------------------------------------------

    def test_query_line_matches_response_fixture(self):
        """`> Reply with the single word PONG ...` is a multiline anchor."""
        clean = _strip_ansi(_read_fixture("antigravity_cli_response.txt"))
        assert re.search(QUERY_LINE_PATTERN, clean, flags=re.MULTILINE)

    def test_response_indent_matches_response_fixture(self):
        """The `  PONG` response line is the canonical 2-space-indented body."""
        clean = _strip_ansi(_read_fixture("antigravity_cli_response.txt"))
        assert re.search(RESPONSE_INDENT_PATTERN, clean, flags=re.MULTILINE)

    def test_input_box_rule_matches_response_fixture(self):
        """At least one ──── rule must be present in every interactive capture."""
        clean = _strip_ansi(_read_fixture("antigravity_cli_response.txt"))
        assert re.search(INPUT_BOX_RULE_PATTERN, clean, flags=re.MULTILINE)

    # -------------------------------------------------------------------------
    # ANSI strip integrity
    # -------------------------------------------------------------------------

    def test_ansi_strip_preserves_pong_response(self):
        """Stripping ANSI must leave the literal response text intact."""
        clean = _strip_ansi(_read_fixture("antigravity_cli_response.txt"))
        assert "PONG" in clean

    def test_ansi_strip_preserves_status_bar_text(self):
        """Status-bar text must survive ANSI strip in every state fixture."""
        clean_proc = _strip_ansi(_read_fixture("antigravity_cli_processing.txt"))
        clean_resp = _strip_ansi(_read_fixture("antigravity_cli_response.txt"))
        assert "esc to cancel" in clean_proc
        assert "? for shortcuts" in clean_resp


# =============================================================================
# Provider-class integration tests — require tmux mock layer (deferred)
# =============================================================================


class TestAntigravityCliProviderIntegration:
    """Provider lifecycle tests deferred until tmux mock layer is wired in."""

    def test_initialize_success(self):
        pytest.skip("Deferred: requires tmux_client mock — see ROADMAP §3/§4")

    def test_extract_simple_response(self):
        pytest.skip("Deferred: extraction integration test pending tmux mocks")

    def test_exit_cli_returns_ctrl_d(self):
        pytest.skip("Deferred: integration coverage pending tmux mocks")
