"""Register command for CLI Agent Orchestrator CLI.

Registers an already-running tmux terminal with CAO so it can be
tracked, monitored, and receive messages via the inbox system.
"""

import click
import requests

from cli_agent_orchestrator.constants import PROVIDERS, SERVER_HOST, SERVER_PORT


@click.command()
@click.option("--session", required=True, help="Tmux session name containing the terminal")
@click.option("--window", required=True, help="Tmux window name to register")
@click.option("--provider", required=True, help="Provider type (e.g., kiro_cli, gemini_cli)")
@click.option("--agents", default=None, help="Agent profile name (optional)")
def register(session, window, provider, agents):
    """Register an existing tmux terminal with CAO."""
    if provider not in PROVIDERS:
        raise click.ClickException(
            f"Invalid provider '{provider}'. Available providers: {', '.join(PROVIDERS)}"
        )

    url = f"http://{SERVER_HOST}:{SERVER_PORT}/terminals/register"
    params = {
        "tmux_session": session,
        "tmux_window": window,
        "provider": provider,
    }
    if agents:
        params["agent_profile"] = agents

    try:
        response = requests.post(url, params=params, timeout=10)
        response.raise_for_status()
        terminal = response.json()
        click.echo(f"Registered terminal: {terminal['id']}")
        click.echo(f"  Session: {session}")
        click.echo(f"  Window:  {window}")
        click.echo(f"  Provider: {provider}")
        if agents:
            click.echo(f"  Profile: {agents}")
    except requests.exceptions.ConnectionError:
        raise click.ClickException(
            f"Failed to connect to cao-server: Is it running on {SERVER_HOST}:{SERVER_PORT}?"
        )
    except requests.exceptions.HTTPError as e:
        detail = ""
        try:
            detail = e.response.json().get("detail", "")
        except Exception:
            detail = e.response.text
        raise click.ClickException(f"Registration failed: {detail}")
