"""``cao zellij`` — install + launch + tail for the CAO v2.5 Phase 2 TUI.

Three subcommands:

  * ``cao zellij install`` — copies the vendored layout + status-bar
    plugin into ``~/.config/zellij/`` (or ``$XDG_CONFIG_HOME/zellij``).
  * ``cao zellij start`` — launches Zellij with the ``cao`` layout and
    sets ``CAO_ZELLIJ_ENABLED=true`` so the FastAPI lifespan brings up
    the hook bridge (services/zellij_bridge.py).
  * ``cao zellij tail`` — streams ``/events`` SSE from the local CAO
    server and pretty-prints each event. Used by the Trace pane in the
    Zellij layout; safe to run standalone for any operator log tailing.

Assets are resolved via ``importlib.resources`` against the
``cli_agent_orchestrator.zellij_assets`` package (Hatch
``force-include`` mirrors them in the wheel). Editable installs fall
back to the repo-root ``zellij/`` directory.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from importlib import resources
from pathlib import Path
from typing import Any, Iterator, Optional

import click
import requests  # type: ignore[import-untyped]

_ASSET_PACKAGE = "cli_agent_orchestrator.zellij_assets"
_LAYOUT_RELPATH = "layouts/cao.kdl"
_PLUGIN_RELPATH = "zellaude.wasm"


def _xdg_config_home() -> Path:
    raw = os.environ.get("XDG_CONFIG_HOME")
    if raw:
        return Path(raw)
    return Path.home() / ".config"


def _zellij_config_dir() -> Path:
    return _xdg_config_home() / "zellij"


def _editable_repo_root() -> Optional[Path]:
    """Locate the repo-root ``zellij/`` directory in editable installs.

    Returns ``None`` when running from a wheel (the package files live
    inside site-packages and the repo-root layout doesn't exist).
    """
    here = Path(__file__).resolve()
    # src/cli_agent_orchestrator/cli/commands/zellij.py → repo root is parents[4]
    candidate = here.parents[4] / "zellij"
    if (candidate / _LAYOUT_RELPATH).is_file() and (candidate / _PLUGIN_RELPATH).is_file():
        return candidate
    return None


def _resolve_asset(relpath: str) -> Path:
    """Return a filesystem path for a vendored asset.

    Tries the packaged ``zellij_assets`` first, falling back to the
    repo-root ``zellij/`` directory for editable installs. Raises
    ``click.ClickException`` if neither is found.
    """
    try:
        package_root = resources.files(_ASSET_PACKAGE)
        candidate = package_root.joinpath(relpath)
        if candidate.is_file():
            # ``Traversable`` is path-compatible at this point because
            # the package is on the regular filesystem after install.
            return Path(str(candidate))
    except (ModuleNotFoundError, FileNotFoundError):
        pass

    repo_root = _editable_repo_root()
    if repo_root is not None:
        return repo_root / relpath

    raise click.ClickException(
        f"Could not locate Zellij asset {relpath!r} — reinstall the package or "
        f"rebuild the .wasm via `cd zellij && cargo build --target wasm32-wasip1 --release`."
    )


@click.group()
def zellij() -> None:
    """Manage the CAO v2.5 Zellij TUI (install / start / tail)."""


@zellij.command("install")
def install_cmd() -> None:
    """Copy the CAO layout + zellaude plugin into ~/.config/zellij/."""
    if sys.platform == "win32":
        raise click.ClickException(
            "Zellij is not supported on Windows. Use the tmux compatibility path: `cao launch`."
        )
    config_dir = _zellij_config_dir()
    layouts_dir = config_dir / "layouts"
    plugins_dir = config_dir / "plugins"
    layouts_dir.mkdir(parents=True, exist_ok=True)
    plugins_dir.mkdir(parents=True, exist_ok=True)

    layout_src = _resolve_asset(_LAYOUT_RELPATH)
    plugin_src = _resolve_asset(_PLUGIN_RELPATH)

    layout_dst = layouts_dir / "cao.kdl"
    plugin_dst = plugins_dir / "zellaude.wasm"
    shutil.copyfile(layout_src, layout_dst)
    shutil.copyfile(plugin_src, plugin_dst)

    click.echo(f"Installed layout  → {layout_dst}")
    click.echo(f"Installed plugin  → {plugin_dst}")
    click.echo("Run `cao zellij start` to launch the three-pane TUI.")


@zellij.command("start")
@click.option(
    "--layout",
    "layout_name",
    default="cao",
    show_default=True,
    help="Zellij layout name. Must already exist under ~/.config/zellij/layouts/.",
)
def start_cmd(layout_name: str) -> None:
    """Launch Zellij with the CAO layout and bring up the hook bridge."""
    if sys.platform == "win32":
        raise click.ClickException(
            "Zellij is not supported on Windows. Use the tmux compatibility path: `cao launch`."
        )
    if shutil.which("zellij") is None:
        raise click.ClickException(
            "`zellij` binary not found on PATH. Install from https://zellij.dev/ then retry."
        )
    layout_path = _zellij_config_dir() / "layouts" / f"{layout_name}.kdl"
    if not layout_path.is_file():
        raise click.ClickException(
            f"Layout not installed at {layout_path}. Run `cao zellij install` first."
        )

    env = {**os.environ, "CAO_ZELLIJ_ENABLED": "true"}
    click.echo(f"Launching zellij with layout {layout_path} …")
    # Replace the current process so signal handling matches `tmux attach`.
    raise SystemExit(subprocess.call(["zellij", "--layout", str(layout_path)], env=env))


@zellij.command("tail")
@click.option(
    "--api",
    "api_base",
    default=None,
    help="CAO server base URL (default: $CAO_API_URL or http://127.0.0.1:9889).",
)
@click.option(
    "--max-events",
    type=int,
    default=0,
    help="Stop after N events (0 = stream forever, default).",
)
def tail_cmd(api_base: Optional[str], max_events: int) -> None:
    """Pretty-print live events from the CAO SSE bus.

    Used by the Trace pane in the Zellij layout, but useful standalone
    too. Reconnects with exponential backoff (1s → 30s) when the stream
    drops, so a transient server restart doesn't kill the pane.
    """
    base = api_base or os.environ.get("CAO_API_URL", "http://127.0.0.1:9889")
    url = f"{base.rstrip('/')}/events"
    backoff = 1.0
    seen = 0
    while True:
        try:
            for event in _stream_events(url):
                _print_event(event)
                seen += 1
                if max_events and seen >= max_events:
                    return
                backoff = 1.0  # reset on first successful event
        except KeyboardInterrupt:
            return
        except Exception as exc:  # noqa: BLE001
            click.echo(f"[zellij tail] stream error: {exc}; retrying in {backoff:.0f}s", err=True)
            time.sleep(backoff)
            backoff = min(backoff * 2, 30.0)


def _stream_events(url: str) -> Iterator[dict[str, Any]]:
    response = requests.get(url, stream=True, timeout=(5, None))
    response.raise_for_status()
    for raw in response.iter_lines(decode_unicode=True):
        if not raw:
            continue
        if not raw.startswith("data:"):
            continue
        payload = raw[len("data:") :].strip()
        if not payload:
            continue
        try:
            event = json.loads(payload)
        except json.JSONDecodeError:
            continue
        if isinstance(event, dict):
            yield event


_SEVERITY_COLORS = {
    "kill": "\x1b[1;31m",  # bold red
    "mitigate": "\x1b[1;33m",  # bold yellow
    "warn": "\x1b[33m",  # yellow
    "recover": "\x1b[32m",  # green
}
_RESET = "\x1b[0m"


def _print_event(event: dict[str, Any]) -> None:
    ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
    kind = str(event.get("type", "?"))
    severity = event.get("severity")
    color = _SEVERITY_COLORS.get(severity, "") if isinstance(severity, str) else ""
    summary_keys = ("session_name", "terminal_id", "task_class", "overall", "severity")
    summary = " ".join(f"{k}={event[k]}" for k in summary_keys if k in event)
    click.echo(f"{ts} {color}{kind:<24}{_RESET} {summary}")
