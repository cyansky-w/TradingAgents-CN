import { ApiClient } from './request'
import type { ApiResponse } from './request'

export interface ToolParameter {
  name: string
  type: string
  required: boolean
  default?: any
  description?: string
}

export interface Tool {
  id: string
  code: string
  name: string
  description: string
  type: 'builtin' | 'rpc' | 'remote' | 'workflow'
  handler?: string
  workflow_id?: string
  output_format?: 'full' | 'summary'
  endpoint_url?: string
  endpoint_method?: 'GET' | 'POST' | 'PUT' | 'DELETE'
  headers?: Record<string, string>
  auth_type?: 'none' | 'api_key' | 'bearer' | 'basic'
  auth_config?: Record<string, string>
  parameters: ToolParameter[]
  output_schema?: any
  timeout: number
  tags: string[]
  enabled: boolean
  is_system: boolean
  calls_llm: boolean
  estimated_tokens: number
  health_status: string
  last_health_check?: string
  health_check_url?: string
  agent_count: number
  created_at: string
  updated_at: string
}

export interface ToolListParams {
  type?: string
  enabled?: boolean
  tag?: string
  search?: string
  page?: number
  page_size?: number
}

export interface ToolListResult {
  items: Tool[]
  total: number
  page: number
  page_size: number
}

export interface ToolCreateDto {
  code: string
  name: string
  description: string
  type: 'rpc' | 'remote' | 'workflow'
  endpoint_url?: string
  endpoint_method?: 'GET' | 'POST' | 'PUT' | 'DELETE'
  headers?: Record<string, string>
  auth_type?: 'none' | 'api_key' | 'bearer' | 'basic'
  auth_config?: Record<string, string>
  parameters?: ToolParameter[]
  output_schema?: any
  timeout?: number
  tags?: string[]
  enabled?: boolean
  health_check_url?: string
  workflow_id?: string
  output_format?: 'full' | 'summary'
}

export interface ToolUpdateDto {
  name?: string
  description?: string
  tags?: string[]
  enabled?: boolean
  timeout?: number
  parameters?: ToolParameter[]
  output_schema?: any
  endpoint_url?: string
  endpoint_method?: 'GET' | 'POST' | 'PUT' | 'DELETE'
  headers?: Record<string, string>
  auth_type?: 'none' | 'api_key' | 'bearer' | 'basic'
  auth_config?: Record<string, string>
  health_check_url?: string
}

export const toolsApi = {
  async list(params?: ToolListParams): Promise<ApiResponse<ToolListResult>> {
    return await ApiClient.get<ToolListResult>('/api/tools/', params)
  },

  async get(id: string): Promise<ApiResponse<Tool>> {
    return await ApiClient.get<Tool>(`/api/tools/${id}`)
  },

  async create(payload: ToolCreateDto): Promise<ApiResponse<Tool>> {
    return await ApiClient.post<Tool>('/api/tools/', payload)
  },

  async update(id: string, payload: ToolUpdateDto): Promise<ApiResponse<{ id: string }>> {
    return await ApiClient.put<{ id: string }>(`/api/tools/${id}`, payload)
  },

  async remove(id: string): Promise<ApiResponse<{ id: string }>> {
    return await ApiClient.delete<{ id: string }>(`/api/tools/${id}`)
  },

  async toggle(id: string, enabled: boolean): Promise<ApiResponse<{ id: string; enabled: boolean }>> {
    return await ApiClient.put<{ id: string; enabled: boolean }>(`/api/tools/${id}/toggle`, { enabled })
  },

  async healthCheck(id: string): Promise<ApiResponse<{ id: string; health_status: string; details: string }>> {
    return await ApiClient.post<{ id: string; health_status: string; details: string }>(`/api/tools/${id}/health-check`)
  },

  async getAllTags(): Promise<ApiResponse<string[]>> {
    return await ApiClient.get<string[]>('/api/tools/tags')
  },

  async seed(): Promise<ApiResponse<{ created: number; updated: number; skipped: number; total: number }>> {
    return await ApiClient.post<{ created: number; updated: number; skipped: number; total: number }>('/api/tools/seed')
  }
}
