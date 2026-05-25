import { ApiClient } from './request'
import type { ApiResponse } from './request'

export interface WorkflowNode {
  id: string
  type: 'agent' | 'subflow' | 'io'
  label?: string
  position?: { x: number; y: number }
  config?: Record<string, any>
}

export interface WorkflowEdge {
  id: string
  source: string
  target: string
}


export interface TriggerConfig {
  type: 'manual' | 'cron' | 'event'
  cron?: string
  event?: string
}

export interface WorkflowSettings {
  timeout?: number
  on_failure?: string
  retry_count?: number
}

export interface Workflow {
  id: string
  code: string
  name: string
  description: string
  version: number
  trigger: TriggerConfig
  message_template: string
  output_template?: string
  nodes: WorkflowNode[]
  edges: WorkflowEdge[]
  settings: WorkflowSettings
  tags: string[]
  enabled: boolean
  usage_count: number
  last_used_at?: string
  created_at: string
  updated_at: string
}

export interface WorkflowListParams {
  search?: string
  tag?: string
  enabled?: boolean
  page?: number
  page_size?: number
}

export interface WorkflowListResult {
  items: Workflow[]
  total: number
  page: number
  page_size: number
}

export interface WorkflowCreateDto {
  code: string
  name: string
  description?: string
  version?: number
  trigger?: TriggerConfig
  message_template?: string
  output_template?: string
  nodes: WorkflowNode[]
  edges: WorkflowEdge[]
  settings?: WorkflowSettings
  tags?: string[]
  enabled?: boolean
}

export interface WorkflowUpdateDto {
  name?: string
  description?: string
  version?: number
  trigger?: TriggerConfig
  message_template?: string
  output_template?: string
  nodes?: WorkflowNode[]
  edges?: WorkflowEdge[]
  settings?: WorkflowSettings
  tags?: string[]
  enabled?: boolean
}

export interface ValidationIssue {
  level: 'error' | 'warning'
  node_id?: string
  message: string
  type: string
}

export interface WorkflowValidationResult {
  valid: boolean
  errors: ValidationIssue[]
  warnings?: ValidationIssue[]
}

export interface WorkflowRun {
  id: string
  workflow_id: string
  workflow_name: string
  status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled'
  trigger_type: string
  input: Record<string, any>
  output?: any
  node_executions: Array<{ node_id: string; status: string; output: any }>
  parent_run_id?: string | null
  started_at: string
  completed_at: string
  error?: string | null
  created_at: string
}

export interface WorkflowRunListResult {
  items: WorkflowRun[]
  total: number
  page: number
  page_size: number
}

export const workflowsApi = {
  async list(params?: WorkflowListParams): Promise<ApiResponse<WorkflowListResult>> {
    return await ApiClient.get<WorkflowListResult>('/api/workflows/', params)
  },

  async get(id: string): Promise<ApiResponse<Workflow>> {
    return await ApiClient.get<Workflow>(`/api/workflows/${id}`)
  },

  async create(payload: WorkflowCreateDto): Promise<ApiResponse<Workflow>> {
    return await ApiClient.post<Workflow>('/api/workflows/', payload)
  },

  async update(id: string, payload: WorkflowUpdateDto): Promise<ApiResponse<Workflow>> {
    return await ApiClient.put<Workflow>(`/api/workflows/${id}`, payload)
  },

  async remove(id: string): Promise<ApiResponse<{ id: string }>> {
    return await ApiClient.delete<{ id: string }>(`/api/workflows/${id}`)
  },

  async toggle(id: string, enabled: boolean): Promise<ApiResponse<{ id: string; enabled: boolean }>> {
    return await ApiClient.put<{ id: string; enabled: boolean }>(`/api/workflows/${id}/toggle`, { enabled })
  },

  async getTags(): Promise<ApiResponse<string[]>> {
    return await ApiClient.get<string[]>('/api/workflows/tags')
  },

  async validate(id: string): Promise<ApiResponse<WorkflowValidationResult>> {
    return await ApiClient.post<WorkflowValidationResult>(`/api/workflows/${id}/validate`)
  },

  async run(id: string, input_data?: Record<string, any>): Promise<ApiResponse<{ run_id: string; output: any }>> {
    return await ApiClient.post<{ run_id: string; output: any }>(`/api/workflows/${id}/run`, { input: input_data || {} })
  },

  async listRuns(workflowId: string, page = 1, pageSize = 20): Promise<ApiResponse<WorkflowRunListResult>> {
    return await ApiClient.get<WorkflowRunListResult>(`/api/workflows/${workflowId}/runs`, { page, page_size: pageSize })
  },

  async getRun(runId: string): Promise<ApiResponse<WorkflowRun>> {
    return await ApiClient.get<WorkflowRun>(`/api/workflows/runs/${runId}`)
  },

  async cancelRun(runId: string): Promise<ApiResponse<{ run_id: string; status: string }>> {
    return await ApiClient.post<{ run_id: string; status: string }>(`/api/workflows/runs/${runId}/cancel`)
  },

  async seed(): Promise<ApiResponse<{ created: number; skipped: number; failed: string[]; total: number }>> {
    return await ApiClient.post<{ created: number; skipped: number; failed: string[]; total: number }>('/api/workflows/seed')
  }
}
