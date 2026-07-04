// Types mirrored from cao_mcp_apps/src/shared/types.ts. We duplicate
// for the v1 PR; npm-workspace extraction is a v2 chore per the RFC.

export interface CaoInstance {
  id: string;
  url: string;
  label: string;
  added_at: string;
}

export interface CaoEvent {
  // Original CAO event-log entry shape.
  id: string;
  kind: string;
  terminal_id: string | null;
  session_name: string | null;
  timestamp: string;
  detail: Record<string, unknown>;
}

export interface AGUIEvent {
  // Parsed AG-UI typed event from the SSE stream.
  type: string;
  data: Record<string, unknown>;
}

export interface SessionSummary {
  name: string;
  active_terminals: Set<string>;
}

export interface TerminalSummary {
  id: string;
  agent_name: string | null;
  provider: string | null;
  status: "running" | "terminated";
}
