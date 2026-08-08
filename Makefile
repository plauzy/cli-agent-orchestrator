#!/usr/bin/env make -f
# CLI Agent Orchestrator — maintenance targets.
#
# Offline vendoring of the upstream MCP Apps builder skills
# (modelcontextprotocol/ext-apps). See skills/vendor/ext-apps/README.md.

.PHONY: refresh-ext-apps-skills check-ext-apps-skills

# Re-vendor the ext-apps builder skills from the pinned tag and rewrite NOTICE.
# To move to a newer upstream release, bump PINNED_REF/PINNED_SHA in
# scripts/vendor_ext_apps_skills.py first, then run this target.
refresh-ext-apps-skills:
	uv run python scripts/vendor_ext_apps_skills.py

# Verify the on-disk vendored copy still matches the pin (CI / pre-commit).
# Exit 0 = in sync, 1 = drift, 2 = network-gated (could not verify).
check-ext-apps-skills:
	uv run python scripts/vendor_ext_apps_skills.py --check


# -----------------------------------------------------------------------------
# Agent Plugins (agent-plugins.org) pinned JSON schemas.
#
# Agent Plugins 5.2 forbids retrieving a schema while loading a plugin, so CAO
# validates only against the vendored copies under
# src/cli_agent_orchestrator/schemas/agent_plugins/<version>/.
# See scripts/vendor_agent_plugins_schemas.py.
# -----------------------------------------------------------------------------

.PHONY: refresh-agent-plugins-schemas check-agent-plugins-schemas \
        check-agent-plugins-schemas-upstream

# Re-vendor the pinned schemas and rewrite PIN.json's hash manifest.
# To move to a newer upstream revision, bump PINNED_REF/PINNED_SHA in
# scripts/vendor_agent_plugins_schemas.py first, then run this target.
refresh-agent-plugins-schemas:
	uv run python scripts/vendor_agent_plugins_schemas.py

# Verify the vendored schema bytes still hash to PIN.json (CI / pre-commit).
# OFFLINE by design, so it is a real gate on every PR rather than one that
# degrades to "unverifiable" without network. Exit 0 = in sync, 1 = drift.
check-agent-plugins-schemas:
	uv run python scripts/vendor_agent_plugins_schemas.py --check

# Additionally re-clone the pin and compare bytes against upstream.
# Needs network. Exit 0 = in sync, 1 = drift, 2 = network-gated.
check-agent-plugins-schemas-upstream:
	uv run python scripts/vendor_agent_plugins_schemas.py --check-upstream
