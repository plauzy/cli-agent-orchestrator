"""CAO Doctor — session startup health check."""

import json
import os
import subprocess
from pathlib import Path

import click

from cli_agent_orchestrator.constants import CAO_ENV_FILE

_REQUIRED_LOG_DIR = Path("/Volumes/workplace/.remember/logs/")
_REQUIRED_GIT_VARS = ["GIT_AUTHOR_EMAIL", "GIT_COMMITTER_EMAIL"]
_CAO_HEALTH_URL = "http://localhost:9889/health"
_SETTINGS_PATH = Path.home() / ".claude" / "settings.json"
_REQUIRED_PLUGINS: list[str] = [
    "remember@claude-plugins-official",
    "zoom-plugin@claude-plugins-official",
    "imessage@claude-plugins-official",
]


def _check_log_dir() -> tuple[str, str, str]:
    if _REQUIRED_LOG_DIR.exists() and os.access(_REQUIRED_LOG_DIR, os.W_OK):
        return ("logs dir", "OK", "")
    return (
        "logs dir",
        "MISSING",
        f"mkdir -p {_REQUIRED_LOG_DIR}",
    )


def _check_git_identity() -> tuple[str, str, str]:
    if not CAO_ENV_FILE.exists():
        return ("git identity", "NOT SET", "cao env set GIT_AUTHOR_EMAIL <email>")
    content = CAO_ENV_FILE.read_text()
    for var in _REQUIRED_GIT_VARS:
        if var not in content:
            return ("git identity", "NOT SET", f"cao env set {var} <value>")
    return ("git identity", "OK", "")


def _check_cao_server() -> tuple[str, str, str]:
    try:
        result = subprocess.run(
            ["curl", "-sf", "--max-time", "1", _CAO_HEALTH_URL],
            capture_output=True,
            timeout=2,
        )
        if result.returncode == 0:
            return ("CAO server", "OK", "")
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    return ("CAO server", "DOWN", "nohup cao-server > /tmp/cao-server.log 2>&1 &")


def _check_plugins() -> tuple[str, str, str]:
    if not _SETTINGS_PATH.exists():
        return ("plugins", "SKIP", "settings.json not found")
    try:
        data = json.loads(_SETTINGS_PATH.read_text())
        enabled = data.get("plugins", data.get("enabledPlugins", {}))
        if isinstance(enabled, dict):
            missing = [p for p in _REQUIRED_PLUGINS if not enabled.get(p, False)]
        else:
            missing = []
        if missing:
            return ("plugins", f"MISSING: {', '.join(missing)}", "enable via Claude Code settings")
        return ("plugins", "OK", "")
    except Exception:
        return ("plugins", "SKIP", "could not parse settings.json")


def _run_checks() -> list[tuple[str, str, str]]:
    return [
        _check_log_dir(),
        _check_git_identity(),
        _check_cao_server(),
        _check_plugins(),
    ]


def _format_table(checks: list[tuple[str, str, str]]) -> str:
    warnings = [(name, status, fix) for name, status, fix in checks if status not in ("OK", "SKIP")]
    if not warnings:
        return ""
    header = f"⚠️ CAO DOCTOR — {len(warnings)} warning(s)\n"
    header += "| Check | Status | Fix |\n|---|---|---|\n"
    rows = "\n".join(f"| {name} | {status} | {fix} |" for name, status, fix in warnings)
    return header + rows


@click.command(name="doctor")
@click.option(
    "--json-output",
    "json_output",
    is_flag=True,
    default=False,
    help="Emit JSON systemMessage for hook use.",
)
@click.option("--fix", is_flag=True, default=False, help="Auto-fix mkdir and env checks.")
def doctor(json_output: bool, fix: bool) -> None:
    """Run session startup health checks."""
    if fix:
        if not _REQUIRED_LOG_DIR.exists():
            _REQUIRED_LOG_DIR.mkdir(parents=True, exist_ok=True)
            click.echo(f"✓ Created {_REQUIRED_LOG_DIR}")

    checks = _run_checks()
    table = _format_table(checks)

    if json_output:
        if table:
            click.echo(json.dumps({"systemMessage": table}))
        # clean run: no output (hook prints nothing)
    else:
        if table:
            click.echo(table)
        else:
            rows = "\n".join(f"  {name}: {status}" for name, status, _ in checks)
            click.echo(f"✓ CAO Doctor — all checks passed\n{rows}")
