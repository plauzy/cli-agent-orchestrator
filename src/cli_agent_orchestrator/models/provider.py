from enum import Enum


class ProviderType(str, Enum):
    """Provider type enumeration."""

    KIRO_CLI = "kiro_cli"
    CLAUDE_CODE = "claude_code"
    CODEX = "codex"
    KIMI_CLI = "kimi_cli"
    COPILOT_CLI = "copilot_cli"
    OPENCODE_CLI = "opencode_cli"
    HERMES = "hermes"
    CURSOR_CLI = "cursor_cli"
    ANTIGRAVITY_CLI = "antigravity_cli"
    # Ported net-new providers (fork plauzy/cao):
    Q_CLI = "q_cli"
    GEMINI_CLI = "gemini_cli"
    MOCK_CLI = "mock_cli"
