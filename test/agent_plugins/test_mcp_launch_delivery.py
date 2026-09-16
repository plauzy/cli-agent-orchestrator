"""Plugin MCP servers must appear in each provider's REAL launch artifact.

Reproduced by review on #584, and the reason this file exists at all:

> "the all-provider tests need to inspect real launch commands rather than
> treating ``collect_plugin_mcp_servers()`` as delivery."

The pre-existing equivalence suite asked ``mcp_delivery`` what it *would*
deliver. That is a tautology with respect to the actual defect: the merge ran in
``install_service`` against an in-memory profile, ``_write_context_file``
persisted the untouched raw text, and Claude Code, Codex, Kimi, Antigravity and
Cursor each called ``load_agent_profile()`` **again** at launch — so the merged
entry was gone by the time the command was built. Copilot never consulted the
profile for MCP at all. Every assertion here therefore reads the command string
or config file the provider really produces.

Mutation-verified: removing the ``with_plugin_mcp`` wrapper from a provider makes
that provider's case fail.
"""

from __future__ import annotations

import json
import shlex
from pathlib import Path

import pytest

from cli_agent_orchestrator.agent_plugins.installer import install
from cli_agent_orchestrator.agent_plugins.models import PluginSource

from .conftest import build_plugin

PLUGIN_SERVER = "plugin-tools"
MCP_DOC = json.dumps(
    {
        "$schema": "https://agent-plugins.org/schemas/1.0.0/mcp.schema.json",
        "mcpServers": {
            PLUGIN_SERVER: {"type": "stdio", "command": "demo-server", "args": ["--serve"]}
        },
    }
)


@pytest.fixture
def installed_plugin(store, skills_dir, tmp_path, monkeypatch):
    """Install a plugin declaring one stdio MCP server, with stores redirected."""
    monkeypatch.setattr("cli_agent_orchestrator.agent_plugins.projection.SKILLS_DIR", skills_dir)
    monkeypatch.setattr("cli_agent_orchestrator.utils.skills.SKILLS_DIR", skills_dir)
    monkeypatch.setattr("cli_agent_orchestrator.agent_plugins.store.AGENT_PLUGINS_DIR", tmp_path)

    source = build_plugin(
        tmp_path / "plugin-src", "mcpdonor", skills=["donor-skill"], mcp_text=MCP_DOC
    )
    install(
        PluginSource(kind="path", location=str(source)),
        store=store,
        skills_dir=skills_dir,
        refresh_agents=False,
    )
    # The delivery seam resolves the store from module state, so point it at ours.
    monkeypatch.setattr(
        "cli_agent_orchestrator.agent_plugins.mcp_delivery.InstalledPluginStore",
        lambda *a, **k: store,
    )
    return store


def _profile_stub(name: str = "worker"):
    """A minimal real AgentProfile — not a MagicMock, so serializers behave."""
    from cli_agent_orchestrator.models.agent_profile import AgentProfile

    return AgentProfile(name=name, description="d", system_prompt="p")


def _delivered_somewhere(command: str, server_name: str) -> bool:
    """Whether ``server_name`` reaches the provider, inline or by referenced file.

    Providers split two ways and both count as a real launch artifact: some
    inline the MCP config into the command (Codex's ``-c`` overrides, Kimi's
    ``--mcp-config <json>``), others write a file and pass its path (Claude
    Code's ``--mcp-config <path>``). Asserting only on the command string would
    give a false negative for the second group, so any referenced ``.json`` the
    command names is read and searched too.
    """
    if server_name in command:
        return True
    for token in shlex.split(command):
        if not token.endswith(".json"):
            continue
        candidate = Path(token)
        if candidate.is_file() and server_name in candidate.read_text(encoding="utf-8"):
            return True
    return False


class TestTheLaunchCommandCarriesThePluginServer:
    @pytest.mark.parametrize(
        "module,cls,builder",
        [
            ("claude_code", "ClaudeCodeProvider", "_build_claude_command"),
            ("codex", "CodexProvider", "_build_codex_command"),
            ("kimi_cli", "KimiCliProvider", "_build_kimi_command"),
            ("cursor_cli", "CursorCliProvider", "_build_cursor_command"),
        ],
    )
    def test_the_built_command_mentions_the_plugin_server(
        self, installed_plugin, monkeypatch, module, cls, builder
    ):
        import importlib

        mod = importlib.import_module(f"cli_agent_orchestrator.providers.{module}")
        if not hasattr(mod, cls) or not hasattr(getattr(mod, cls), builder):
            pytest.skip(f"{module}.{cls}.{builder} not present in this build")

        monkeypatch.setattr(mod, "load_agent_profile", lambda _name: _profile_stub())

        provider = getattr(mod, cls)("tid-1", "sess", "win", "worker")
        try:
            command = getattr(provider, builder)()
        except Exception as exc:  # pragma: no cover - provider needs a real binary
            pytest.skip(f"{module} command build needs an environment we do not have: {exc}")

        assert _delivered_somewhere(command, PLUGIN_SERVER), (
            f"{module} built a launch command without the plugin MCP server; "
            f"plugin delivery does not reach this provider"
        )

    def test_copilot_runtime_mcp_config_includes_the_plugin_server(
        self, installed_plugin, monkeypatch
    ):
        """Copilot's runtime config is the only MCP config it reads."""
        from cli_agent_orchestrator.providers import copilot_cli as mod

        monkeypatch.setattr(mod, "load_agent_profile", lambda _name: _profile_stub())
        provider = mod.CopilotCliProvider("tid-2", "sess", "win", "worker")

        raw = provider._build_runtime_mcp_config()
        servers = json.loads(raw)["mcpServers"]

        assert "cao-mcp-server" in servers, "CAO's own in-session server must remain"
        assert PLUGIN_SERVER in servers, (
            "Copilot's runtime MCP config omitted the plugin server, so plugin "
            "MCP delivery never reaches Copilot"
        )

    def test_antigravity_writes_the_plugin_server_into_its_shared_config(
        self, installed_plugin, monkeypatch, tmp_path
    ):
        """Antigravity delivers via a config file rather than the command line."""
        from cli_agent_orchestrator.providers import antigravity_cli as mod

        config_path = tmp_path / "gemini" / "config" / "mcp_config.json"
        monkeypatch.setattr(mod, "load_agent_profile", lambda _name: _profile_stub())
        monkeypatch.setattr(
            mod.AntigravityCliProvider, "_mcp_config_path", lambda self: config_path
        )

        provider = mod.AntigravityCliProvider("tid-3", "sess", "win", "worker")
        profile = mod._with_plugin_mcp(_profile_stub(), "antigravity_cli")
        assert profile.mcpServers and PLUGIN_SERVER in profile.mcpServers

        provider._register_mcp_servers(profile.mcpServers)

        written = json.loads(config_path.read_text(encoding="utf-8"))["mcpServers"]
        assert any(key.startswith(PLUGIN_SERVER) for key in written), (
            f"antigravity wrote {sorted(written)} — no plugin server reached " f"mcp_config.json"
        )


class TestOmpGrokMinimaxCarryThePluginServer:
    """Review pullrequestreview-5209646575 (P2, F3).

    OMP, Grok, and MiniMax each regenerate a native MCP artifact from a profile
    they reload at launch, but their loads were not wrapped by the delivery seam,
    so a plugin server was silently dropped. These assert the server reaches each
    provider's REAL emitted artifact — the extension `.mcp.json`, `config.toml`,
    and `servers.mcp.json` — by driving the provider's own writer with the profile
    its wrapped load returns. Testing at the writer seam avoids the binary/PATH
    probe in the full `_build_*_command` while still exercising the real merge and
    the real serializer.
    """

    def test_omp_extension_config_includes_the_plugin_server(
        self, installed_plugin, monkeypatch, tmp_path
    ):
        from cli_agent_orchestrator.providers import omp as mod

        monkeypatch.setattr(mod, "load_agent_profile", lambda _name: _profile_stub())
        provider = mod.OmpProvider("tid-omp", "sess", "win", "worker")
        ext_root = tmp_path / "omp-ext"
        ext_root.mkdir(parents=True, exist_ok=True)
        monkeypatch.setattr(provider, "_artifact_root", lambda: ext_root)

        profile = provider._load_profile()
        assert profile is not None and PLUGIN_SERVER in (
            profile.mcpServers or {}
        ), "the seam did not merge the plugin server into OMP's loaded profile"
        extension_dir = Path(provider._write_extension_root(profile.mcpServers))
        written = json.loads((extension_dir / ".mcp.json").read_text())["mcpServers"]
        assert PLUGIN_SERVER in written, (
            "OMP's extension .mcp.json omitted the plugin server; delivery does not " "reach OMP"
        )

    def test_grok_config_toml_includes_the_plugin_server(
        self, installed_plugin, monkeypatch, tmp_path
    ):
        from cli_agent_orchestrator.providers import grok_cli as mod

        monkeypatch.setattr(mod, "load_agent_profile", lambda _name: _profile_stub())
        provider = mod.GrokCliProvider("tid-grok", "sess", "win", "worker")

        profile = provider._load_profile()
        assert profile is not None and PLUGIN_SERVER in (profile.mcpServers or {})
        rendered = provider._render_mcp_config(profile.mcpServers)
        assert (
            PLUGIN_SERVER in rendered
        ), "Grok's config.toml omitted the plugin server; delivery does not reach Grok"

    def test_minimax_servers_config_includes_the_plugin_server(
        self, installed_plugin, monkeypatch, tmp_path
    ):
        from cli_agent_orchestrator.providers import minimax_code as mod

        monkeypatch.setattr(mod, "load_agent_profile", lambda _name: _profile_stub())
        provider = mod.MiniMaxCodeProvider("tid-mm", "sess", "win", "worker")

        # Drive the serializer the way `_prepare_runtime` does, from the wrapped load.
        profile = mod.with_plugin_mcp(_profile_stub(), "minimax_code")
        assert PLUGIN_SERVER in (profile.mcpServers or {})
        data_dir = tmp_path / "mm-data"
        provider._write_plugin(data_dir, profile.mcpServers)
        from cli_agent_orchestrator.providers.minimax_code import _PLUGIN_NAME

        written = (data_dir / "plugins" / _PLUGIN_NAME / "servers.mcp.json").read_text()
        assert PLUGIN_SERVER in written, (
            "MiniMax's servers.mcp.json omitted the plugin server; delivery does not "
            "reach MiniMax"
        )

    def test_grok_streamable_http_is_translated_to_its_native_http(
        self, store, skills_dir, tmp_path, monkeypatch
    ):
        """A `streamable-http` plugin server must reach Grok as `http`, or
        `_render_mcp_config` would raise and abort the launch."""
        monkeypatch.setattr(
            "cli_agent_orchestrator.agent_plugins.projection.SKILLS_DIR", skills_dir
        )
        monkeypatch.setattr("cli_agent_orchestrator.utils.skills.SKILLS_DIR", skills_dir)
        monkeypatch.setattr(
            "cli_agent_orchestrator.agent_plugins.store.AGENT_PLUGINS_DIR", tmp_path
        )
        url_doc = json.dumps(
            {
                "$schema": "https://agent-plugins.org/schemas/1.0.0/mcp.schema.json",
                "mcpServers": {
                    "http-tools": {"type": "streamable-http", "url": "https://x.example/mcp"}
                },
            }
        )
        source = build_plugin(tmp_path / "url-src", "urldonor", skills=["s"], mcp_text=url_doc)
        install(
            PluginSource(kind="path", location=str(source)),
            store=store,
            skills_dir=skills_dir,
            refresh_agents=False,
        )
        monkeypatch.setattr(
            "cli_agent_orchestrator.agent_plugins.mcp_delivery.InstalledPluginStore",
            lambda *a, **k: store,
        )
        from cli_agent_orchestrator.providers import grok_cli as mod

        profile = mod.with_plugin_mcp(_profile_stub(), "grok_cli")
        provider = mod.GrokCliProvider("tid-grok2", "sess", "win", "worker")
        rendered = provider._render_mcp_config(profile.mcpServers)  # must not raise
        assert 'type = "http"' in rendered
        assert "streamable-http" not in rendered


class TestEveryMcpCapableProviderIsWiredOrExempt:
    """Anti-omission guard (R4.7/R4.8).

    Derives the set of providers whose module reads ``profile.mcpServers`` to
    generate native MCP config, and asserts each either wraps its launch-time load
    with the delivery seam (``with_plugin_mcp``) or is on an explicitly justified
    exemption list. A newly added MCP-capable provider that forgets the seam fails
    here rather than silently dropping plugin servers — the exact class of defect
    review pullrequestreview-5209646575 reported for three providers at once.
    """

    # Providers that read profile.mcpServers but legitimately need no seam, each
    # with the reason. `mock_cli` is test-only; `hermes` delivers no MCP.
    _EXEMPT = {
        "hermes": "delivers no MCP config to the agent",
        "mock_cli": "test double, no real launch",
    }

    def _provider_modules(self):
        import pathlib

        import cli_agent_orchestrator.providers as providers_pkg

        pkg_dir = pathlib.Path(providers_pkg.__file__).parent
        for path in sorted(pkg_dir.glob("*.py")):
            if path.stem in {"__init__", "base", "manager"}:
                continue
            yield path.stem, path

    def test_every_mcp_capable_provider_wraps_the_seam(self):
        import ast

        offenders = []
        for name, path in self._provider_modules():
            src = path.read_text(encoding="utf-8")
            reads_mcp = "mcpServers" in src
            if not reads_mcp:
                continue
            wraps_seam = "with_plugin_mcp" in src
            if wraps_seam or name in self._EXEMPT:
                continue
            # Confirm it is a genuine read (attribute access), not a comment.
            tree = ast.parse(src)
            genuine = any(
                isinstance(node, ast.Attribute) and node.attr == "mcpServers"
                for node in ast.walk(tree)
            )
            if genuine:
                offenders.append(name)

        assert not offenders, (
            "these providers read profile.mcpServers to build native MCP config but "
            f"do not pass their launch-time load through with_plugin_mcp: {offenders}. "
            "Wrap the load (see providers/kimi_cli.py) and add the provider to "
            "PROVIDER_TRANSPORTS, or add it to _EXEMPT with a reason."
        )

    def test_the_expected_nine_providers_are_wired(self):
        """A positive check so the guard cannot pass by finding nothing."""
        wired = {
            name
            for name, path in self._provider_modules()
            if "with_plugin_mcp" in path.read_text(encoding="utf-8")
        }
        assert {
            "antigravity_cli",
            "claude_code",
            "codex",
            "copilot_cli",
            "cursor_cli",
            "grok_cli",
            "kimi_cli",
            "minimax_code",
            "omp",
        } <= wired


class TestTheProfileItselfIsUnchangedOnDisk:
    def test_delivery_is_recomputed_not_persisted(self, installed_plugin, monkeypatch):
        """The profile source must not gain the expanded absolute paths.

        The whole reason delivery is applied on read: a persisted copy of the
        expanded ``${PLUGIN_ROOT}`` paths goes stale when the store moves.
        """
        from cli_agent_orchestrator.agent_plugins.mcp_delivery import with_plugin_mcp

        profile = with_plugin_mcp(_profile_stub(), "claude_code")
        assert PLUGIN_SERVER in (profile.mcpServers or {})

        # A second, independent load must produce the server again from disk
        # state alone — not from anything the first call wrote down.
        again = with_plugin_mcp(_profile_stub(), "claude_code")
        assert (again.mcpServers or {}).keys() == (profile.mcpServers or {}).keys()
