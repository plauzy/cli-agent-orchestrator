"""Antigravity CLI (`agy`) provider.

Antigravity CLI (https://antigravity.google.com) is Google's coding
agent CLI shipped alongside the Antigravity IDE. Regex patterns in this
module are calibrated against the captured fixture set under
``test/providers/fixtures/antigravity_cli_*.txt``.

Key characteristics (observed in agy 1.0.6, 220×50 tmux, macOS arm64):
- Command: ``agy`` (single static Go binary, not Node/Ink)
- Headless flag: ``--dangerously-skip-permissions`` (analogous to Gemini ``--yolo``)
- Print mode: ``agy --print "<prompt>" --dangerously-skip-permissions`` (prompt is
  POSITIONAL — ``--prompt`` is a misleadingly-named Boolean alias for ``--print``)
- Interactive mode: ``agy -i "<initial prompt>"`` (analogous to Gemini ``-i``)
- Idle prompt: input box with ``────`` (U+2500) borders and a ``> `` line
- Processing: Braille spinner + status bar reads ``esc to cancel`` (right side
  remains the model name). The status bar transition ``? for shortcuts`` →
  ``esc to cancel`` is the cleanest PROCESSING signal.
- Response prefix: NONE — response is 2-space indented plain text below the
  user query, no ``✦`` (Gemini) or other anchor character.
- Welcome banner: ``▄▀`` (U+2584 / U+2580) ASCII orbit art with version/email/model/cwd
- Trust folder: agy shows a "Do you trust the contents of this project?" prompt
  on first launch in an unknown cwd. Must auto-confirm with ``Enter``.

Status Detection Strategy:
- IDLE: ``? for shortcuts`` in bottom status bar, empty ``>`` input, no
  unconsumed response between the last query and the next ``────`` rule.
- PROCESSING: ``esc to cancel`` in bottom status bar OR Braille spinner glyph
  visible in last few lines.
- COMPLETED: ``? for shortcuts`` in bottom status bar AND 2-space indented
  response text present after the last ``> <query>`` line.
- ERROR: standard ``Error:``/``Traceback`` fallback (agy itself surfaces user-
  visible errors as inline message lines, not stderr-style prefixes).
"""

import logging
import os
import re
import shlex
import time
from pathlib import Path
from typing import List, Optional

from cli_agent_orchestrator.clients.tmux import tmux_client
from cli_agent_orchestrator.models.terminal import TerminalStatus
from cli_agent_orchestrator.providers.base import BaseProvider
from cli_agent_orchestrator.utils.agent_profiles import load_agent_profile
from cli_agent_orchestrator.utils.terminal import wait_for_shell

logger = logging.getLogger(__name__)


class ProviderError(Exception):
    """Exception raised for Antigravity CLI provider-specific errors."""

    pass


# =============================================================================
# Regex patterns for Antigravity CLI output analysis
# =============================================================================
# Patterns calibrated against fixtures under test/providers/fixtures/
# (antigravity_cli_idle.txt, _processing.txt, _response.txt, _error.txt,
# _permission.txt, _tool_call.txt, _interactive_clean.txt). Coverage tests
# live in test/providers/test_antigravity_cli_unit.py.
# =============================================================================

# ANSI strip pattern — same shape as Gemini CLI. agy uses 256-color (\x1b[38;5;Nm)
# rather than 24-bit RGB, but the strip regex catches both families.
ANSI_CODE_PATTERN = r"\x1b\[[0-9;]*m"

# Input-box horizontal rule: line of U+2500 BOX DRAWINGS LIGHT HORIZONTAL.
# Observed lengths in fixtures: 60-char short-rule (banner separator) and
# ~220-char full-width input box. Floor of 20 stays well below the short rule
# but above any incidental ASCII art.
INPUT_BOX_RULE_PATTERN = r"^─{20,}$"

# Welcome banner anchor — orbit/asteroid ASCII art using ▄ (U+2584) and ▀ (U+2580).
# The 8-character U+2580 run on banner row 3 is the most stable substring.
WELCOME_BANNER_PATTERN = r"▄▀▀▄|▀▀▀▀▀▀▀▀"

# Welcome banner text fragments (all present once init completes).
WELCOME_VERSION_PATTERN = r"Antigravity CLI\s+\d+\.\d+\.\d+"
WELCOME_MODEL_PATTERN = r"(?:Gemini|Claude|GPT)[\s\w\.\(\)]+"

# Status bar — bottom-most line. Right edge always shows the current model
# (e.g. "Gemini 3.1 Pro (High)"). Left edge swaps between two strings:
#   IDLE / COMPLETED → "? for shortcuts"
#   PROCESSING       → "esc to cancel"
STATUS_BAR_IDLE_PATTERN = r"\?\s+for shortcuts"
STATUS_BAR_PROCESSING_PATTERN = r"esc to cancel"
STATUS_BAR_MODEL_PATTERN = r"(?:Gemini|Claude|GPT)[\w\s\.\(\)]*\b"

# Number of lines from the bottom to scan for the status bar / idle prompt.
# Status bar is on the very last non-blank line. Bubble Tea sometimes re-renders
# the input box and status bar block together — 10 lines covers the redraw plus
# trailing blank padding in the alt-screen buffer.
STATUS_BAR_TAIL_LINES = 10

# User query prefix inside the input box. Lines like ``> Reply with PONG``
# represent submitted user queries. The empty ``>`` line is the idle input.
QUERY_LINE_PATTERN = r"^>\s+\S"  # query with text content
IDLE_PROMPT_LINE_PATTERN = r"^>\s*$"  # empty input prompt

# Simplified idle pattern for log-file monitoring. The status-bar text survives
# in the pipe-pane log file because it's printed on the bottom line of the
# alt-screen buffer; it's the most reliable single-line anchor for IDLE.
IDLE_PATTERN_LOG = r"\?\s+for shortcuts"

# Processing spinner: Braille pattern characters U+2800–U+28FF, followed by
# whitespace and a status verb. Verbs observed across fixtures: Generating
# (idle/processing fixtures), Working (permission fixture). Loading/Thinking/
# Running kept defensively for Gemini-CLI parity.
PROCESSING_SPINNER_PATTERN = r"[⠀-⣿]\s+(?:Generating|Loading|Thinking|Running|Working)"

# Tip line shown below spinner on some interactions.
TIP_LINE_PATTERN = r"└\s+Tip:"

# Response prefix — agy does NOT prefix response lines with a special char.
# Responses appear as 2-space indented plain text below the user query.
# Tool-call output uses the same 2-space body indent (verified in tool_call
# fixture), so the single pattern handles both.
RESPONSE_INDENT_PATTERN = r"^\s{2}\S"  # 2+ leading spaces, then non-space content

# Trust-folder interactive prompt — shown on first launch in untrusted cwd.
# Provider must auto-confirm by sending Enter.
TRUST_FOLDER_PROMPT_PATTERN = r"Do you trust the contents of this project\?"

# Generic error patterns (same shape as gemini_cli — provider-agnostic).
ERROR_PATTERN = (
    r"^(?:Error:|ERROR:|Traceback \(most recent call last\):|ConnectionError:|APIError:)"
)


# =============================================================================
# Provider class
# =============================================================================


class AntigravityCliProvider(BaseProvider):
    """Provider for Antigravity CLI (``agy``) integration.

    Regex patterns are calibrated against the captured fixture set. The
    remaining open items (tracked in ROADMAP.md) are non-regex:
    plugin/MCP surface, tool-restriction enforcement, and the agy
    log-file format for pipe-pane monitoring.
    """

    def __init__(
        self,
        terminal_id: str,
        session_name: str,
        window_name: str,
        agent_profile: Optional[str] = None,
        allowed_tools: Optional[List[str]] = None,
        skill_prompt: Optional[str] = None,
    ):
        """Initialize provider state."""
        super().__init__(terminal_id, session_name, window_name, allowed_tools, skill_prompt)
        self._initialized = False
        self._agent_profile = agent_profile
        # Mirror gemini_cli's tracking of `-i` usage to handle the post-init
        # IDLE-vs-COMPLETED ambiguity (Bubble Tea may exhibit the same quirk).
        self._uses_prompt_interactive = False
        self._received_input_after_init = False
        # If we discover an MCP plugin install surface, track names for cleanup.
        self._registered_plugins: List[str] = []

    # -------------------------------------------------------------------------
    # Command building
    # -------------------------------------------------------------------------

    def _build_agy_command(self) -> str:
        """Build the ``agy`` launch command for tmux ``send_keys``.

        STARTER IMPLEMENTATION — covers only the headless launch flag and a
        system-prompt-as-``-i`` injection. MCP servers and tool restrictions
        are NOT implemented; see ROADMAP.md §3 and §4.

        Returns:
            Shell-escaped command string ready for ``send_keys``.
        """
        command_parts = ["agy", "--dangerously-skip-permissions"]

        if self._agent_profile is not None:
            try:
                profile = load_agent_profile(self._agent_profile)

                if profile.model:
                    # Agy model names contain spaces and parens (e.g.
                    # "Claude Opus 4.6 (Thinking)"). shlex.join() below
                    # handles quoting.
                    command_parts.extend(["--model", profile.model])

                system_prompt = profile.system_prompt or ""
                system_prompt = self._apply_skill_prompt(system_prompt)
                if system_prompt:
                    # agy has no documented GEMINI.md equivalent yet. For v0
                    # we pass the entire system prompt as the -i initial
                    # message; once a config-file injection surface is found
                    # we should prefer that (cf. gemini_cli.py lesson #12).
                    command_parts.extend(["-i", system_prompt])
                    self._uses_prompt_interactive = True

                # MCP servers — STUB. ``agy plugin`` syntax unknown. See ROADMAP.md §3.
                if profile.mcpServers:
                    logger.warning(
                        "AntigravityCliProvider: profile %s declares MCP servers but "
                        "agy MCP integration is not implemented (terminal %s). "
                        "Servers ignored.",
                        self._agent_profile,
                        self.terminal_id,
                    )

            except Exception as e:
                raise ProviderError(f"Failed to load agent profile '{self._agent_profile}': {e}")

        # Tool restrictions — STUB. agy surface unknown. See ROADMAP.md §4.
        if self._allowed_tools and "*" not in self._allowed_tools:
            logger.warning(
                "AntigravityCliProvider: tool restrictions requested but agy has no "
                "documented restriction mechanism. Terminal %s will run unrestricted.",
                self.terminal_id,
            )

        return shlex.join(command_parts)

    # -------------------------------------------------------------------------
    # Lifecycle
    # -------------------------------------------------------------------------

    def initialize(self) -> bool:
        """Initialize agy in the tmux window.

        STARTER IMPLEMENTATION — minimal happy-path. Includes the trust-folder
        auto-confirm loop because that prompt blocks first launches.

        Returns:
            True on successful initialization.

        Raises:
            TimeoutError: shell or agy did not become ready in time.
        """
        if not wait_for_shell(tmux_client, self.session_name, self.window_name, timeout=10.0):
            raise TimeoutError("Shell initialization timed out after 10 seconds")

        # Warm-up echo (mirror gemini_cli rationale — see gemini_cli.py initialize()
        # for the why; same shell-init race condition applies).
        warmup_marker = "CAO_AGY_READY"
        tmux_client.send_keys(self.session_name, self.window_name, f"echo {warmup_marker}")
        warmup_start = time.time()
        while time.time() - warmup_start < 15.0:
            output = tmux_client.get_history(self.session_name, self.window_name)
            if output and warmup_marker in output:
                break
            time.sleep(0.5)
        else:
            logger.warning("Shell warm-up marker not detected within timeout, proceeding anyway")
        time.sleep(2)

        command = self._build_agy_command()
        tmux_client.send_keys(self.session_name, self.window_name, command)

        init_start = time.time()
        # agy is a Go binary so startup is faster than Gemini's Node/Ink
        # (~3-5s vs 10-15s), but the Electron-auth cookie load can be slow
        # on first run — keep parity with the Gemini provider budget.
        init_timeout = 180.0

        if self._uses_prompt_interactive:
            target_states = (TerminalStatus.COMPLETED,)
        else:
            target_states = (TerminalStatus.IDLE, TerminalStatus.COMPLETED)

        while time.time() - init_start < init_timeout:
            output = tmux_client.get_history(self.session_name, self.window_name)
            if output:
                clean_output = re.sub(ANSI_CODE_PATTERN, "", output)

                # Auto-confirm the trust-folder prompt by selecting the default
                # ("Yes, I trust this folder") and pressing Enter.
                if re.search(TRUST_FOLDER_PROMPT_PATTERN, clean_output):
                    logger.info(
                        "Antigravity CLI trust-folder prompt detected, confirming with Enter"
                    )
                    tmux_client.send_keys(self.session_name, self.window_name, "Enter")
                    time.sleep(2.0)
                    continue

            status = self.get_status(output=output)
            if status in target_states:
                break
            time.sleep(1.0)
        else:
            diag = tmux_client.get_history(self.session_name, self.window_name)
            diag_tail = "\n".join((diag or "").splitlines()[-50:])
            logger.error(
                "agy init timeout — terminal %s, uses_prompt_interactive=%s, target=%s\n%s",
                self.terminal_id,
                self._uses_prompt_interactive,
                target_states,
                diag_tail,
            )
            raise TimeoutError(f"Antigravity CLI initialization timed out after {init_timeout}s.")

        self._initialized = True
        return True

    def mark_input_received(self) -> None:
        """Notify that external input was sent to this terminal.

        Mirrors gemini_cli — used to break the post-init IDLE/COMPLETED tie.
        If agy reaches a true IDLE between init and first user input under
        Bubble Tea, this flag becomes a no-op; harmless either way.
        """
        self._received_input_after_init = True

    # -------------------------------------------------------------------------
    # Status detection
    # -------------------------------------------------------------------------

    def get_status(
        self, tail_lines: Optional[int] = None, output: Optional[str] = None
    ) -> TerminalStatus:
        """Return current Antigravity CLI status by analyzing terminal output.

        Uses the bottom status-bar text as the primary IDLE/PROCESSING
        discriminator, with the Braille spinner as a fallback signal.
        """
        if output is None:
            output = tmux_client.get_history(
                self.session_name, self.window_name, tail_lines=tail_lines
            )
        if not output:
            return TerminalStatus.ERROR

        clean_output = re.sub(ANSI_CODE_PATTERN, "", output)
        all_lines = clean_output.strip().splitlines()
        bottom_lines = all_lines[-STATUS_BAR_TAIL_LINES:]

        # Status-bar check ordering matters because the spinner text can briefly
        # disappear between Bubble Tea redraws (~50-100ms). Prefer the more
        # durable "esc to cancel" footer over the spinner glyph.
        if any(re.search(STATUS_BAR_PROCESSING_PATTERN, line) for line in bottom_lines):
            return TerminalStatus.PROCESSING

        if any(re.search(PROCESSING_SPINNER_PATTERN, line) for line in bottom_lines):
            return TerminalStatus.PROCESSING

        idle_bar = any(re.search(STATUS_BAR_IDLE_PATTERN, line) for line in bottom_lines)
        if not idle_bar:
            # No idle bar and no processing signal — check for an error before
            # defaulting to PROCESSING (the model may be loading auth/auth screens).
            if re.search(ERROR_PATTERN, clean_output, re.MULTILINE):
                return TerminalStatus.ERROR
            return TerminalStatus.PROCESSING

        # Idle bar visible — distinguish IDLE (no response yet) vs COMPLETED
        # (response present after the last query).
        last_query_idx = None
        for i, line in enumerate(all_lines):
            if re.search(QUERY_LINE_PATTERN, line):
                last_query_idx = i

        if last_query_idx is not None:
            tail = all_lines[last_query_idx + 1 :]
            has_response = any(re.search(RESPONSE_INDENT_PATTERN, line) for line in tail)
            if has_response:
                # Same post-init handling as gemini_cli when -i was used:
                # don't return COMPLETED before external input is received.
                if (
                    self._initialized
                    and self._uses_prompt_interactive
                    and not self._received_input_after_init
                ):
                    return TerminalStatus.IDLE
                return TerminalStatus.COMPLETED

        return TerminalStatus.IDLE

    def get_idle_pattern_for_log(self) -> str:
        """Return pattern that indicates IDLE state in pipe-pane log output.

        If a future ``agy --log-file`` capture shows the status bar is
        stripped, swap this for the closing ``────`` rule + empty ``>``
        line sequence — both anchors are present in the alt-screen capture.
        """
        return IDLE_PATTERN_LOG

    # -------------------------------------------------------------------------
    # Response extraction
    # -------------------------------------------------------------------------

    def extract_last_message_from_script(self, script_output: str) -> str:
        """Extract the last assistant response from terminal output.

        Finds the last ``> <query>`` line, then collects the
        2-space-indented content lines until the next ``────`` rule or
        status-bar match.

        Raises:
            ValueError: if no response content can be extracted.
        """
        clean_output = re.sub(ANSI_CODE_PATTERN, "", script_output)
        clean_lines = clean_output.split("\n")

        last_query_idx: Optional[int] = None
        for i, line in enumerate(clean_lines):
            if re.search(QUERY_LINE_PATTERN, line):
                last_query_idx = i

        if last_query_idx is None:
            raise ValueError("No Antigravity CLI user query found — no '>' query line detected")

        # Walk forward, collecting indented response lines until we hit the
        # next ──── rule or status-bar marker.
        response_lines: List[str] = []
        for i in range(last_query_idx + 1, len(clean_lines)):
            line = clean_lines[i]
            stripped = line.strip()

            if not stripped:
                continue

            if re.search(INPUT_BOX_RULE_PATTERN, line.rstrip()):
                break

            if re.search(STATUS_BAR_IDLE_PATTERN, line) or re.search(
                STATUS_BAR_PROCESSING_PATTERN, line
            ):
                break

            if re.search(PROCESSING_SPINNER_PATTERN, line):
                continue

            if re.search(TIP_LINE_PATTERN, line):
                continue

            if re.search(IDLE_PROMPT_LINE_PATTERN, line):
                continue

            # Strip the 2-space response indent. Tool-call output uses the
            # same body indent (verified against the tool_call fixture).
            if line.startswith("  "):
                response_lines.append(line[2:].rstrip())
            else:
                response_lines.append(stripped)

        if not response_lines:
            raise ValueError(
                "Empty Antigravity CLI response — no indented content after the last query"
            )

        return "\n".join(response_lines).strip()

    # -------------------------------------------------------------------------
    # Exit / cleanup
    # -------------------------------------------------------------------------

    def exit_cli(self) -> str:
        """Return the keystroke to exit ``agy``.

        Ctrl+D matches every Charm/Bubble Tea CLI we've integrated. If a
        future build of agy requires ``/quit`` or ``/exit`` instead, update
        this string alongside the corresponding test.
        """
        return "C-d"

    def cleanup(self) -> None:
        """Clean up provider resources.

        Currently a no-op because v0 doesn't write any files (no GEMINI.md
        equivalent, no policy TOML, no MCP server entries). Once
        plugin/restriction surfaces land (ROADMAP §3/§4), unregister them
        here — see ``gemini_cli._unregister_mcp_servers`` for the shape.
        """
        if self._registered_plugins:
            logger.warning(
                "AntigravityCliProvider.cleanup: %d plugins not de-registered "
                "(implementation pending) for terminal %s",
                len(self._registered_plugins),
                self.terminal_id,
            )
        self._initialized = False
