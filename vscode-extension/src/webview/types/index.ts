export interface Session {
  session_id: string;
  name: string;
  created_at: string;
  terminals: Terminal[];
}

export interface Terminal {
  terminal_id: string;
  session_id: string;
  agent_profile: string;
  status: 'IDLE' | 'BUSY' | 'COMPLETED' | 'ERROR';
  created_at: string;
  inbox: InboxMessage[];
}

export interface InboxMessage {
  id: string;
  from_terminal_id: string;
  to_terminal_id: string;
  message: string;
  timestamp: string;
  read: boolean;
}

export interface AgentProfile {
  name: string;
  description?: string;
  path: string;
}

export interface Flow {
  name: string;
  schedule: string;
  agent_profile: string;
  script?: string;
  prompt: string;
  enabled: boolean;
  next_run?: string;
}

export interface OrchestrationRequest {
  mode: 'handoff' | 'assign' | 'send_message';
  agent_profile?: string;
  terminal_id?: string;
  message: string;
}

export interface ServerHealth {
  status: 'ok' | 'error';
  timestamp: string;
}
