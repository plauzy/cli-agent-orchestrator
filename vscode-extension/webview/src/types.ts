export interface Session {
  id: string;
  name: string;
  created_at: string;
}

export interface Terminal {
  id: string;
  session_id: string;
  agent_profile: string;
  status: 'IDLE' | 'BUSY' | 'COMPLETED' | 'ERROR';
  created_at: string;
  updated_at: string;
}

export interface InboxMessage {
  id: string;
  terminal_id: string;
  sender_id: string;
  message: string;
  status: 'PENDING' | 'DELIVERED' | 'FAILED';
  created_at: string;
}

export interface Flow {
  id: string;
  name: string;
  schedule: string;
  agent_profile: string;
  enabled: boolean;
  next_run: string | null;
}

export interface VSCodeMessage {
  command: string;
  [key: string]: any;
}
