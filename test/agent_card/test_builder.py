"""Tests for the Agent Card builder."""

from __future__ import annotations

from cli_agent_orchestrator.agent_card.builder import (
    _DECLARED_MCP_TOOLS,
    _PROVIDER_BINARIES,
    build_agent_card,
)


class TestBuilderDefaults:
    def test_returns_a2a_v1_schema_url(self):
        card = build_agent_card()
        assert card["$schema"] == "https://a2aproject.org/schemas/v1.0/agent-card.json"

    def test_includes_all_four_mcp_tools(self):
        card = build_agent_card()
        assert card["capabilities"]["tools"] == _DECLARED_MCP_TOOLS

    def test_includes_every_known_provider(self):
        card = build_agent_card()
        names = {p["name"] for p in card["providers"]}
        assert names == set(_PROVIDER_BINARIES.keys())

    def test_provider_entries_have_installed_flag(self):
        card = build_agent_card()
        for entry in card["providers"]:
            assert "installed" in entry
            assert isinstance(entry["installed"], bool)

    def test_default_endpoints_are_none_in_phase_1(self):
        # Full A2A transport surface arrives in Phase 5.
        card = build_agent_card()
        assert card["endpoints"]["rpc"] is None
        assert card["endpoints"]["stream"] is None
        assert card["endpoints"]["tasks"] is None


class TestBuilderMetadataMerge:
    def test_operator_metadata_overrides_defaults(self):
        card = build_agent_card(
            {
                "agent_id": "cao-prod-01",
                "name": "Production CAO",
                "description": "Customer-facing orchestrator",
                "organization": "flowclaw.local",
                "vendor": "Flowclaw",
                "contact": "ops@flowclaw.local",
            }
        )
        assert card["agentId"] == "cao-prod-01"
        assert card["name"] == "Production CAO"
        assert card["description"] == "Customer-facing orchestrator"
        assert card["organization"] == "flowclaw.local"
        assert card["vendor"] == "Flowclaw"
        assert card["contact"] == "ops@flowclaw.local"

    def test_explicit_endpoint_overrides(self):
        card = build_agent_card(
            None,
            rpc_endpoint="https://cao.example/a2a/v1/rpc",
            stream_endpoint="https://cao.example/a2a/v1/stream",
            tasks_endpoint="https://cao.example/a2a/v1/tasks",
        )
        assert card["endpoints"]["rpc"] == "https://cao.example/a2a/v1/rpc"
        assert card["endpoints"]["stream"] == "https://cao.example/a2a/v1/stream"
        assert card["endpoints"]["tasks"] == "https://cao.example/a2a/v1/tasks"


class TestBuilderHasNoSignatureField:
    def test_unsigned_card_does_not_carry_signature(self):
        # Signing is the router's responsibility — the builder must produce
        # a card with no AgentCardSignature so signing remains stable
        # (no risk of accidentally signing over a stale signature).
        card = build_agent_card()
        assert "AgentCardSignature" not in card
