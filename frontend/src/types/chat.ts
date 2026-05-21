// Chat-related TypeScript interfaces

export interface Conversation {
  id: string
  title: string
  model_provider: string
  model_name: string
  message_count: number
  created_at: string
  updated_at: string
  is_archived: boolean
}

export interface ChatMessage {
  id: string
  conversation_id: string
  role: 'user' | 'assistant' | 'system' | 'tool'
  content: string
  tool_calls?: ToolCall[]
  token_usage?: TokenUsage | null
  created_at: string
}

export interface ToolCall {
  id?: string
  name: string
  args: Record<string, unknown>
  result?: string
}

export interface TokenUsage {
  prompt_tokens?: number
  completion_tokens?: number
  total_tokens?: number
}

export interface ChatRequest {
  conversation_id: string
  message: string
}

export interface ToolInfo {
  name: string
  description: string
  category: string
}

export interface ConversationCreate {
  title?: string
  model_provider?: string
  model_name?: string
}

export interface ConversationUpdate {
  title?: string
  is_archived?: boolean
}

export interface SSEEvent {
  event: 'connected' | 'token' | 'tool_call' | 'tool_result' | 'done' | 'error' | 'heartbeat'
  data: string
}
