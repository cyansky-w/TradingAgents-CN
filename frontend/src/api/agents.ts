import { ApiClient } from './request'
import type { ApiResponse } from './request'

export interface AgentModelConfig {
  provider?: string | null
  model?: string | null
  temperature?: number
  max_tokens?: number
}

export interface AgentParameters {
  max_tool_calls: number
  timeout: number
  retry_on_failure: boolean
}

export interface Agent {
  id: string
  code: string
  name: string
  description: string
  prompt_id: string
  model_config?: AgentModelConfig | null
  parameters: AgentParameters
  tags: string[]
  is_chat: boolean
  is_system: boolean
  enabled: boolean
  usage_count: number
  last_used_at?: string
  created_at: string
  updated_at: string
}

export interface AgentListParams {
  search?: string
  tag?: string
  enabled?: boolean
  is_chat?: boolean
  page?: number
  page_size?: number
}

export interface AgentListResult {
  items: Agent[]
  total: number
  page: number
  page_size: number
}

export interface AgentCreateDto {
  code: string
  name: string
  description?: string
  prompt_id: string
  model_config?: AgentModelConfig | null
  parameters?: Partial<AgentParameters>
  tags?: string[]
  is_chat?: boolean
  enabled?: boolean
}

export interface AgentUpdateDto {
  name?: string
  description?: string
  prompt_id?: string
  model_config?: AgentModelConfig | null
  parameters?: Partial<AgentParameters>
  tags?: string[]
  is_chat?: boolean
  enabled?: boolean
}

export interface AgentSeedResult {
  created: number
  skipped: number
  failed: string[]
  total: number
}

export interface AgentModelProvider {
  name: string
  display_name: string
  default_base_url: string
  default_models: string[]
  has_api_key: boolean
}

export const agentsApi = {
  async list(params?: AgentListParams): Promise<ApiResponse<AgentListResult>> {
    return await ApiClient.get<AgentListResult>('/api/agents/', params)
  },

  async get(id: string): Promise<ApiResponse<Agent>> {
    return await ApiClient.get<Agent>(`/api/agents/${id}`)
  },

  async create(payload: AgentCreateDto): Promise<ApiResponse<Agent>> {
    return await ApiClient.post<Agent>('/api/agents/', payload)
  },

  async update(id: string, payload: AgentUpdateDto): Promise<ApiResponse<Agent>> {
    return await ApiClient.put<Agent>(`/api/agents/${id}`, payload)
  },

  async remove(id: string): Promise<ApiResponse<{ id: string }>> {
    return await ApiClient.delete<{ id: string }>(`/api/agents/${id}`)
  },

  async toggle(id: string, enabled: boolean): Promise<ApiResponse<{ id: string; enabled: boolean }>> {
    return await ApiClient.put<{ id: string; enabled: boolean }>(`/api/agents/${id}/toggle`, { enabled })
  },

  async getTags(): Promise<ApiResponse<string[]>> {
    return await ApiClient.get<string[]>('/api/agents/tags')
  },

  async getModels(): Promise<ApiResponse<AgentModelProvider[]>> {
    return await ApiClient.get<AgentModelProvider[]>('/api/agents/models')
  },

  async seed(): Promise<ApiResponse<AgentSeedResult>> {
    return await ApiClient.post<AgentSeedResult>('/api/agents/seed')
  }
}
