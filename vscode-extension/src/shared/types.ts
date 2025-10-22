// Shared types between extension and webview, mirroring the Python models

export enum TerminalStatus {
  IDLE = 'IDLE',
  PROCESSING = 'PROCESSING',
  COMPLETED = 'COMPLETED',
  WAITING_PERMISSION = 'WAITING_PERMISSION',
  WAITING_USER_ANSWER = 'WAITING_USER_ANSWER',
  ERROR = 'ERROR'
}

export enum SessionStatus {
  ACTIVE = 'ACTIVE',
  DETACHED = 'DETACHED',
  TERMINATED = 'TERMINATED'
}

export enum MessageStatus {
  PENDING = 'PENDING',
  DELIVERED = 'DELIVERED',
  FAILED = 'FAILED'
}

export enum ProviderType {
  Q_CLI = 'q_cli',
  CLAUDE_CODE = 'claude_code'
}

export interface Terminal {
  id: string;
  name: string;
  provider: ProviderType;
  session_name: string;
  agent_profile?: string;
  status?: TerminalStatus;
  created_at?: string;
}

export interface Session {
  id: string;
  name: string;
  status: SessionStatus;
  terminals?: Terminal[];
  created_at?: string;
}

export interface InboxMessage {
  id: number;
  sender_id: string;
  receiver_id: string;
  message: string;
  status: MessageStatus;
  created_at: string;
  delivered_at?: string;
}

export interface Flow {
  name: string;
  file_path: string;
  schedule: string;
  agent_profile: string;
  script?: string;
  last_run?: string;
  next_run?: string;
  enabled: boolean;
}

export interface AgentProfile {
  name: string;
  description: string;
  system_prompt?: string;
  mcpServers?: Record<string, any>;
  model?: string;
  allowedTools?: string[];
}

export interface CreateSessionRequest {
  provider: ProviderType;
  agent_profile?: string;
  session_name?: string;
  headless?: boolean;
}

export interface CreateTerminalRequest {
  provider: ProviderType;
  agent_profile?: string;
  window_name?: string;
}

export interface TerminalOutputResponse {
  output: string;
  mode: 'full' | 'last';
}

export interface SendMessageRequest {
  sender_id: string;
  message: string;
}

export interface ApiResponse<T = any> {
  success: boolean;
  data?: T;
  error?: string;
}

// Message types for extension <-> webview communication
export type MessageToWebview =
  | { type: 'updateSessions'; sessions: Session[] }
  | { type: 'updateTerminals'; terminals: Terminal[] }
  | { type: 'updateMessages'; messages: InboxMessage[] }
  | { type: 'updateFlows'; flows: Flow[] }
  | { type: 'updateTerminalOutput'; terminalId: string; output: string }
  | { type: 'error'; message: string }
  | { type: 'success'; message: string };

export type MessageFromWebview =
  | { type: 'getSessions' }
  | { type: 'getTerminals'; sessionName: string }
  | { type: 'createSession'; request: CreateSessionRequest }
  | { type: 'createTerminal'; sessionName: string; request: CreateTerminalRequest }
  | { type: 'deleteSession'; sessionName: string }
  | { type: 'deleteTerminal'; terminalId: string }
  | { type: 'sendInput'; terminalId: string; message: string }
  | { type: 'getOutput'; terminalId: string; mode: 'full' | 'last' }
  | { type: 'sendMessage'; receiverId: string; request: SendMessageRequest }
  | { type: 'getMessages'; terminalId?: string }
  | { type: 'getFlows' }
  | { type: 'enableFlow'; flowName: string }
  | { type: 'disableFlow'; flowName: string }
  | { type: 'runFlow'; flowName: string };
