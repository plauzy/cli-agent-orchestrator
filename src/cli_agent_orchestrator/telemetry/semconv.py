"""OpenTelemetry GenAI semantic-convention attribute keys used by CAO.

Frozen string constants for the OTel GenAI v1.37+ semantic conventions plus the
CAO-specific extensions. Importing these keys instead of inlining strings keeps
attribute drift out of call sites.

Spec: https://opentelemetry.io/docs/specs/semconv/gen-ai/
"""

from __future__ import annotations

from typing import Final

# --- OTel GenAI v1.37+ ---
GEN_AI_AGENT_ID: Final[str] = "gen_ai.agent.id"
GEN_AI_CONVERSATION_ID: Final[str] = "gen_ai.conversation.id"
GEN_AI_OPERATION_NAME: Final[str] = "gen_ai.operation.name"
GEN_AI_SYSTEM: Final[str] = "gen_ai.system"
GEN_AI_REQUEST_MODEL: Final[str] = "gen_ai.request.model"
GEN_AI_RESPONSE_MODEL: Final[str] = "gen_ai.response.model"
GEN_AI_RESPONSE_FINISH_REASONS: Final[str] = "gen_ai.response.finish_reasons"
GEN_AI_USAGE_INPUT_TOKENS: Final[str] = "gen_ai.usage.input_tokens"
GEN_AI_USAGE_OUTPUT_TOKENS: Final[str] = "gen_ai.usage.output_tokens"
GEN_AI_USAGE_CACHE_CREATION_INPUT_TOKENS: Final[str] = "gen_ai.usage.cache_creation.input_tokens"
GEN_AI_USAGE_CACHE_READ_INPUT_TOKENS: Final[str] = "gen_ai.usage.cache_read.input_tokens"

# Operation names per GenAI semconv
OPERATION_INVOKE_AGENT: Final[str] = "invoke_agent"
OPERATION_EXECUTE_TOOL: Final[str] = "execute_tool"
OPERATION_CHAT: Final[str] = "chat"

# --- CAO extensions (namespaced under cao.*) ---
CAO_TIER: Final[str] = "cao.tier"
CAO_TASK_CLASS: Final[str] = "cao.task_class"
CAO_TOPOLOGY_CHOICE: Final[str] = "cao.topology.choice"
CAO_TOPOLOGY_FEATURES_OMEGA: Final[str] = "cao.topology.features.omega"
CAO_TOPOLOGY_FEATURES_GAMMA: Final[str] = "cao.topology.features.gamma"
CAO_TOPOLOGY_FEATURES_DEPTH: Final[str] = "cao.topology.features.depth"
CAO_TOPOLOGY_FEATURES_K: Final[str] = "cao.topology.features.k"
CAO_REFINERY_POLICY_OUTCOME: Final[str] = "cao.refinery.policy.outcome"
CAO_REFINERY_ACTOR: Final[str] = "cao.refinery.actor"
CAO_REFINERY_ACTION: Final[str] = "cao.refinery.action"
CAO_BUDGET_PROJECTED_COST: Final[str] = "cao.budget.projected_cost"
CAO_BUDGET_REMAINING: Final[str] = "cao.budget.remaining"
CAO_ASI_SCORE: Final[str] = "cao.asi.score"
