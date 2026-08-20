"""
Corpus test for kiro-cli TUI prompt detection.

This test validates that idle detection patterns match actual captured TUI output
across different kiro-cli versions (2.19.0 and older legacy-UI variants).

The corpus includes:
- Live-observed V2 TUI prompts from 2.19.0 (truecolor, lowercase "ask")
- Legacy UI prompts (256-color, different text)
- Negative cases: mid-animation frames, MCP boot screens, agent responses

This test MUST FAIL against the current patterns (as of 2026-08-19) because
the patterns are too narrow and do not match the actual V2 TUI output.
Fix validation: patterns should match all POSITIVE cases and reject all NEGATIVE.
"""

import pytest
import re
from pathlib import Path
from cli_agent_orchestrator.providers.kiro_cli import (
    IDLE_PROMPT_PATTERN_LOG,
    NEW_TUI_IDLE_PATTERN_LOG,
    TUI_INITIALIZING_PATTERN,
)


class TestKiroCliIdleCorpus:
    """Corpus-based idle prompt detection tests.

    These tests use real captured terminal output to validate that idle
    detection patterns work across kiro-cli versions.
    """

    @pytest.fixture
    def fixtures_dir(self):
        """Path to fixture files."""
        return Path(__file__).parent / "fixtures"

    def load_fixture(self, fixtures_dir, filename):
        """Load a fixture file, preserving raw escape sequences."""
        path = fixtures_dir / filename
        if not path.exists():
            pytest.skip(f"Fixture {filename} not found")
        return path.read_bytes().decode("utf-8", errors="replace")

    # =========================================================================
    # POSITIVE CASES: Lines that SHOULD match IDLE
    # =========================================================================

    def test_v2tui_ready_prompt_unmetered_matches_idle_pattern(self, fixtures_dir):
        """V2 TUI unmetered ready prompt SHOULD match as IDLE.

        Live-observed from kiro-cli 2.19.0 with V2 TUI.
        Text: lowercase "ask a question or describe a task ↵"
        Format: truecolor codes [38;2;R;G;Bm, no [brackets], no > sigil
        """
        prompt = self.load_fixture(
            fixtures_dir, "kiro_v2tui_ready_unmetered_v2.19.0.txt"
        )

        # Should match NEW_TUI_IDLE_PATTERN_LOG
        assert re.search(NEW_TUI_IDLE_PATTERN_LOG, prompt), (
            f"NEW_TUI_IDLE_PATTERN_LOG failed to match V2 TUI unmetered prompt.\n"
            f"Pattern: {NEW_TUI_IDLE_PATTERN_LOG}\n"
            f"Text: {repr(prompt)}"
        )

    def test_v2tui_ready_prompt_metered_matches_idle_pattern(self, fixtures_dir):
        """V2 TUI metered ready prompt (with context %) SHOULD match as IDLE.

        Live-observed from kiro-cli 2.19.0 with V2 TUI.
        The context meter line can wrap (meter on previous line, prompt on next).
        Text: lowercase "ask a question or describe a task ↵"
        Must match across multi-line output with the meter indicator.
        """
        prompt = self.load_fixture(
            fixtures_dir, "kiro_v2tui_ready_metered_v2.19.0.txt"
        )

        # Should match NEW_TUI_IDLE_PATTERN_LOG on any line
        assert re.search(NEW_TUI_IDLE_PATTERN_LOG, prompt), (
            f"NEW_TUI_IDLE_PATTERN_LOG failed to match V2 TUI metered prompt.\n"
            f"Pattern: {NEW_TUI_IDLE_PATTERN_LOG}\n"
            f"Text: {repr(prompt)}"
        )

    def test_legacy_ui_ready_prompt_matches_idle_pattern(self, fixtures_dir):
        """Legacy UI ready prompt SHOULD match as IDLE.

        256-color format (\\x1b[38;5;Nm), contains [brackets], has > sigil.
        This is the format that IDLE_PROMPT_PATTERN_LOG was designed for.
        From plan brief, live-observed with --legacy-ui on 2.0.1.
        """
        prompt = self.load_fixture(
            fixtures_dir, "kiro_legacy_ui_ready_v2.19.0.txt"
        )

        # Should match IDLE_PROMPT_PATTERN_LOG
        assert re.search(IDLE_PROMPT_PATTERN_LOG, prompt), (
            f"IDLE_PROMPT_PATTERN_LOG failed to match legacy UI prompt.\n"
            f"Pattern: {IDLE_PROMPT_PATTERN_LOG}\n"
            f"Text: {repr(prompt)}"
        )

    # =========================================================================
    # NEGATIVE CASES: Lines that SHOULD NOT match IDLE
    # =========================================================================

    def test_initializing_line_with_dot_does_not_match_idle(self, fixtures_dir):
        """'Initializing...' (three dots) SHOULD NOT match IDLE.

        This is the mid-boot indicator that appears before the idle prompt
        is interactive. A match here would cause premature IDLE verdict.
        Guard: TUI_INITIALIZING_PATTERN exists to catch this.
        """
        prompt = self.load_fixture(fixtures_dir, "kiro_v2tui_initializing_not_ready_v2.19.0.txt")

        # Must NOT match either idle pattern
        assert not re.search(NEW_TUI_IDLE_PATTERN_LOG, prompt), (
            f"NEW_TUI_IDLE_PATTERN_LOG incorrectly matched initializing line (should reject).\n"
            f"Pattern: {NEW_TUI_IDLE_PATTERN_LOG}\n"
            f"Text: {repr(prompt)}"
        )
        assert not re.search(IDLE_PROMPT_PATTERN_LOG, prompt), (
            f"IDLE_PROMPT_PATTERN_LOG incorrectly matched initializing line (should reject).\n"
            f"Pattern: {IDLE_PROMPT_PATTERN_LOG}\n"
            f"Text: {repr(prompt)}"
        )

        # But TUI_INITIALIZING_PATTERN SHOULD match (to guard against premature IDLE)
        assert re.search(TUI_INITIALIZING_PATTERN, prompt), (
            f"TUI_INITIALIZING_PATTERN failed to catch 'Initializing · type to queue'.\n"
            f"Pattern: {TUI_INITIALIZING_PATTERN}\n"
            f"Text: {repr(prompt)}"
        )

    def test_midanimation_initializing_does_not_match_idle(self, fixtures_dir):
        """Mid-animation 'Initializing...' frame SHOULD NOT match IDLE.

        The TUI animates 'Initializing...' character-by-character.
        Partial renders like '● Init...' (mid-animation) should not match IDLE.
        These appear in the pane before the ready prompt is present.
        """
        prompt = self.load_fixture(
            fixtures_dir, "kiro_v2tui_midanimation_initializing_v2.19.0.txt"
        )

        # Must NOT match idle patterns
        assert not re.search(NEW_TUI_IDLE_PATTERN_LOG, prompt), (
            f"NEW_TUI_IDLE_PATTERN_LOG incorrectly matched mid-animation frame.\n"
            f"Pattern: {NEW_TUI_IDLE_PATTERN_LOG}\n"
            f"Text: {repr(prompt)}"
        )

    def test_mcp_boot_screen_does_not_match_idle(self, fixtures_dir):
        """MCP server boot line SHOULD NOT match IDLE.

        'M of N mcp servers initialized. ctrl-c to start chatting now'
        appears before the idle prompt is interactive. A match would cause
        the inbox to paste into a non-interactive TUI, silently dropping input.

        This is the guard that TUI_INITIALIZING_PATTERN was added for.
        Critical: a false positive here is worse than a missed IDLE.
        """
        prompt = self.load_fixture(
            fixtures_dir, "kiro_mcp_boot_screen_not_ready_v2.19.0.txt"
        )

        # Must NOT match idle patterns
        assert not re.search(NEW_TUI_IDLE_PATTERN_LOG, prompt), (
            f"NEW_TUI_IDLE_PATTERN_LOG incorrectly matched MCP boot screen.\n"
            f"Pattern: {NEW_TUI_IDLE_PATTERN_LOG}\n"
            f"Text: {repr(prompt)}"
        )
        assert not re.search(IDLE_PROMPT_PATTERN_LOG, prompt), (
            f"IDLE_PROMPT_PATTERN_LOG incorrectly matched MCP boot screen.\n"
            f"Pattern: {IDLE_PROMPT_PATTERN_LOG}\n"
            f"Text: {repr(prompt)}"
        )

        # TUI_INITIALIZING_PATTERN SHOULD catch it
        assert re.search(TUI_INITIALIZING_PATTERN, prompt), (
            f"TUI_INITIALIZING_PATTERN failed to catch MCP boot screen.\n"
            f"Pattern: {TUI_INITIALIZING_PATTERN}\n"
            f"Text: {repr(prompt)}"
        )

    def test_agent_response_with_brackets_and_arrow_does_not_match_idle(self, fixtures_dir):
        """Agent response containing [brackets] and > SHOULD NOT match IDLE.

        If the patterns are too permissive, they might match agent output
        that happens to contain '[' and '>'. This is the guardrail against
        false positives in agent responses.
        """
        prompt = self.load_fixture(
            fixtures_dir, "kiro_agent_response_with_brackets.txt"
        )

        # Must NOT match idle patterns
        assert not re.search(NEW_TUI_IDLE_PATTERN_LOG, prompt), (
            f"NEW_TUI_IDLE_PATTERN_LOG incorrectly matched agent response.\n"
            f"Pattern: {NEW_TUI_IDLE_PATTERN_LOG}\n"
            f"Text: {repr(prompt)}"
        )
        assert not re.search(IDLE_PROMPT_PATTERN_LOG, prompt), (
            f"IDLE_PROMPT_PATTERN_LOG incorrectly matched agent response.\n"
            f"Pattern: {IDLE_PROMPT_PATTERN_LOG}\n"
            f"Text: {repr(prompt)}"
        )

    # =========================================================================
    # Combined Pattern Test: get_idle_pattern_for_log()
    # =========================================================================

    def test_combined_idle_pattern_matches_positive_cases(self, fixtures_dir):
        """Combined pattern (IDLE_PROMPT_PATTERN_LOG | NEW_TUI_IDLE_PATTERN_LOG)
        SHOULD match all positive cases.

        get_idle_pattern_for_log() returns a regex that matches either pattern.
        """
        from cli_agent_orchestrator.providers.kiro_cli import KiroCliProvider

        provider = KiroCliProvider("test", "session", "window-0", "developer")
        combined_pattern = provider.get_idle_pattern_for_log()

        # V2 TUI unmetered
        unmetered = self.load_fixture(
            fixtures_dir, "kiro_v2tui_ready_unmetered_v2.19.0.txt"
        )
        assert re.search(combined_pattern, unmetered), (
            f"Combined pattern failed to match V2 TUI unmetered.\n"
            f"Pattern: {combined_pattern}\n"
            f"Text: {repr(unmetered)}"
        )

        # V2 TUI metered
        metered = self.load_fixture(
            fixtures_dir, "kiro_v2tui_ready_metered_v2.19.0.txt"
        )
        assert re.search(combined_pattern, metered), (
            f"Combined pattern failed to match V2 TUI metered.\n"
            f"Pattern: {combined_pattern}\n"
            f"Text: {repr(metered)}"
        )

        # Legacy UI
        legacy = self.load_fixture(
            fixtures_dir, "kiro_legacy_ui_ready_v2.19.0.txt"
        )
        assert re.search(combined_pattern, legacy), (
            f"Combined pattern failed to match legacy UI.\n"
            f"Pattern: {combined_pattern}\n"
            f"Text: {repr(legacy)}"
        )

    def test_combined_idle_pattern_rejects_negative_cases(self, fixtures_dir):
        """Combined pattern SHOULD NOT match negative cases."""
        from cli_agent_orchestrator.providers.kiro_cli import KiroCliProvider

        provider = KiroCliProvider("test", "session", "window-0", "developer")
        combined_pattern = provider.get_idle_pattern_for_log()

        # Initializing line
        initializing = self.load_fixture(
            fixtures_dir, "kiro_v2tui_initializing_not_ready_v2.19.0.txt"
        )
        assert not re.search(combined_pattern, initializing), (
            f"Combined pattern incorrectly matched initializing line.\n"
            f"Pattern: {combined_pattern}\n"
            f"Text: {repr(initializing)}"
        )

        # MCP boot screen
        mcp_boot = self.load_fixture(
            fixtures_dir, "kiro_mcp_boot_screen_not_ready_v2.19.0.txt"
        )
        assert not re.search(combined_pattern, mcp_boot), (
            f"Combined pattern incorrectly matched MCP boot screen.\n"
            f"Pattern: {combined_pattern}\n"
            f"Text: {repr(mcp_boot)}"
        )
