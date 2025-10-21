// Terminal and Agent Types
export interface Terminal {
  id: string
  session_id: string
  status: TerminalStatus
  provider: string
  agent_profile?: string
  created_at: string
  updated_at: string
}

export enum TerminalStatus {
  IDLE = 'IDLE',
  BUSY = 'BUSY',
  COMPLETED = 'COMPLETED',
  ERROR = 'ERROR'
}

export interface Session {
  id: string
  name: string
  created_at: string
  terminals: Terminal[]
}

// Multi-Agent Workflow Types
export interface AgentProfile {
  name: string
  role: string
  expertise: string[]
  tools: Tool[]
  description: string
  type: 'coordinator' | 'specialist'
}

export interface Tool {
  name: string
  description: string
  design_type: 'ui-centric' | 'api-centric'
  parameters: ToolParameter[]
  returns: string
  average_calls_per_task?: number
}

export interface ToolParameter {
  name: string
  type: string
  description: string
  required: boolean
}

// Orchestration Pattern Types
export enum OrchestrationMode {
  HANDOFF = 'handoff',
  ASSIGN = 'assign',
  SEND_MESSAGE = 'send_message'
}

export interface OrchestrationTask {
  id: string
  mode: OrchestrationMode
  agent_profile: string
  message: string
  context: TaskContext
  status: 'pending' | 'in_progress' | 'completed' | 'failed'
  created_at: string
  completed_at?: string
  result?: string
}

export interface TaskContext {
  overall_objective: string
  overall_context: string
  task_description: string
  task_priority: 'high' | 'medium' | 'low'
  available_tools: string[]
  input_data: Record<string, unknown>
  constraints: Record<string, unknown>
  expected_output_format: string
  success_criteria: string[]
  deadline?: string
  depends_on: string[]
  blocks: string[]
}

// Workflow Pattern Types
export interface WorkflowPattern {
  name: string
  type: 'coordinator-specialist' | 'parallel-mapreduce' | 'test-time-compute'
  description: string
  use_cases: string[]
  architecture: PatternArchitecture
  metrics?: WorkflowMetrics
}

export interface PatternArchitecture {
  coordinator?: string
  specialists?: string[]
  workers?: string[]
  evaluator?: string
}

export interface WorkflowMetrics {
  average_tool_calls: number
  completion_time_seconds: number
  success_rate: number
  coordination_overhead_percent: number
}

// Best Practices Types
export interface BestPractice {
  id: string
  category: 'architecture' | 'tool-design' | 'context' | 'communication'
  commandment: string
  description: string
  examples: {
    good: string
    bad: string
  }
  checklist: string[]
}

// Message Types
export interface InboxMessage {
  id: string
  sender_id: string
  receiver_id: string
  message: string
  status: 'PENDING' | 'DELIVERED' | 'FAILED'
  created_at: string
  delivered_at?: string
}
