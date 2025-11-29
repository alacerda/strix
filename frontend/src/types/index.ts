export type ScanStatus = 'running' | 'completed' | 'stopped' | 'failed' | 'created';

export type AgentStatus = 'running' | 'completed' | 'stopped' | 'failed' | 'waiting';

export type Severity = 'critical' | 'high' | 'medium' | 'low' | 'info';

export type ToolStatus = 'running' | 'completed' | 'failed';

export type ToolType =
  | 'terminal'
  | 'browser'
  | 'python'
  | 'file-edit'
  | 'proxy'
  | 'agents-graph'
  | 'thinking'
  | 'web-search'
  | 'finish'
  | 'reporting';

export interface TargetInfo {
  type: string;
  details: Record<string, unknown>;
  original: string;
}

export interface Scan {
  scan_id: string;
  run_name: string;
  status: ScanStatus;
  targets: TargetInfo[];
  user_instructions?: string;
  created_at?: string;
  container_status?: string;
}

export interface Agent {
  agent_id: string;
  name: string;
  task: string;
  status: AgentStatus;
  parent_id?: string | null;
  error_message?: string | null;
  created_at?: string;
}

export interface ChatMessage {
  message_id: number;
  role: 'user' | 'assistant' | 'system';
  content: string;
  agent_id?: string;
  timestamp: string;
  metadata?: Record<string, unknown>;
}

export interface ToolExecution {
  execution_id: number;
  tool_name: string;
  args: Record<string, unknown>;
  status: ToolStatus;
  result?: unknown;
  agent_id?: string;
  timestamp?: string;
  started_at?: string;
}

export interface Vulnerability {
  id: string;
  title: string;
  content: string;
  severity: Severity;
  timestamp?: string;
}

export interface LLMStats {
  input_tokens: number;
  output_tokens: number;
  cached_tokens: number;
  cost: number;
}

export interface Stats {
  agents: number;
  tools: number;
  vulnerabilities: number;
  llm_stats: LLMStats;
}

export interface CreateScanRequest {
  targets: string[];
  user_instructions?: string;
  run_name?: string;
  max_iterations?: number;
}

export interface MessageRequest {
  content: string;
}

export interface WebSocketMessage {
  type:
    | 'agent_created'
    | 'agent_updated'
    | 'message'
    | 'tool_execution'
    | 'vulnerability_found'
    | 'stats_updated'
    | 'scan_created'
    | 'scan_updated'
    | 'scan_deleted'
    | 'status_message'
    | 'initial_state'
    | 'ping';
  data: Record<string, unknown>;
  scan_id?: string;
  timestamp?: number;
}

export interface WebSocketSubscribeMessage {
  type: 'subscribe';
  scan_ids: string[];
}

export interface WebSocketUnsubscribeMessage {
  type: 'unsubscribe';
  scan_ids: string[];
}

