import { ApiClient } from './request'
import type { ApiResponse } from './request'

export type PromptBlockType = 'text' | 'messages_placeholder'
export type PromptType = 'chat' | 'workflow'

export interface PromptBlock {
  type: PromptBlockType
  label: string
  content?: string
}

export interface Prompt {
  id: string
  code: string
  name: string
  description: string
  prompt_type: PromptType
  blocks: PromptBlock[]
  bind_tools: string[]
  tags: string[]
  enabled: boolean
  is_system: boolean
  is_active: boolean
  version: number
  agent_count: number
  created_at: string
  updated_at: string
}

export interface PromptListParams {
  search?: string
  prompt_type?: PromptType
  tag?: string
  enabled?: boolean
  page?: number
  page_size?: number
  all_versions?: boolean
  code?: string
}

export interface PromptListResult {
  items: Prompt[]
  total: number
  page: number
  page_size: number
}

export interface PromptCreateDto {
  code: string
  name: string
  description?: string
  prompt_type?: PromptType
  blocks?: PromptBlock[]
  bind_tools?: string[]
  tags?: string[]
  enabled?: boolean
}

export interface PromptUpdateDto {
  name?: string
  description?: string
  prompt_type?: PromptType
  blocks?: PromptBlock[]
  bind_tools?: string[]
  tags?: string[]
  enabled?: boolean
}

export interface DerivedVariable {
  name: string
  description: string
  source_tool: string
}

export interface DerivedVariablesResult {
  tool_params: DerivedVariable[]
  tool_outputs: DerivedVariable[]
}

export interface RenderRequest {
  variables?: Record<string, string>
}

export interface RenderResult {
  id: string
  code: string
  name: string
  rendered_blocks: PromptBlock[]
  unresolved_variables: string[]
}

export interface SeedResult {
  created: number
  skipped: number
  failed: string[]
  total: number
}

export const promptsApi = {
  async list(params?: PromptListParams): Promise<ApiResponse<PromptListResult>> {
    return await ApiClient.get<PromptListResult>('/api/prompts/', params)
  },

  async get(id: string): Promise<ApiResponse<Prompt>> {
    return await ApiClient.get<Prompt>(`/api/prompts/${id}`)
  },

  async getByCode(code: string): Promise<ApiResponse<Prompt>> {
    return await ApiClient.get<Prompt>(`/api/prompts/code/${code}`)
  },

  async getVersions(code: string): Promise<ApiResponse<Prompt[]>> {
    return await ApiClient.get<Prompt[]>(`/api/prompts/code/${code}/versions`)
  },

  async create(payload: PromptCreateDto): Promise<ApiResponse<Prompt>> {
    return await ApiClient.post<Prompt>('/api/prompts/', payload)
  },

  async update(id: string, payload: PromptUpdateDto): Promise<ApiResponse<Prompt>> {
    return await ApiClient.put<Prompt>(`/api/prompts/${id}`, payload)
  },

  async saveNewVersion(id: string, payload: PromptUpdateDto): Promise<ApiResponse<Prompt>> {
    return await ApiClient.post<Prompt>(`/api/prompts/${id}/new-version`, payload)
  },

  async activate(id: string): Promise<ApiResponse<Prompt>> {
    return await ApiClient.put<Prompt>(`/api/prompts/${id}/activate`)
  },

  async remove(id: string): Promise<ApiResponse<{ id: string }>> {
    return await ApiClient.delete<{ id: string }>(`/api/prompts/${id}`)
  },

  async removeByCode(code: string): Promise<ApiResponse<{ code: string }>> {
    return await ApiClient.delete<{ code: string }>(`/api/prompts/code/${code}`)
  },

  async toggle(id: string, enabled: boolean): Promise<ApiResponse<{ id: string; enabled: boolean }>> {
    return await ApiClient.put<{ id: string; enabled: boolean }>(`/api/prompts/${id}/toggle`, { enabled })
  },

  async render(id: string, payload: RenderRequest): Promise<ApiResponse<RenderResult>> {
    return await ApiClient.post<RenderResult>(`/api/prompts/${id}/render`, payload)
  },

  async deriveVariables(toolNames: string[]): Promise<ApiResponse<DerivedVariablesResult>> {
    return await ApiClient.get<DerivedVariablesResult>('/api/prompts/variables', {
      tools: toolNames.join(',')
    })
  },

  async getAllTags(): Promise<ApiResponse<string[]>> {
    return await ApiClient.get<string[]>('/api/prompts/tags')
  },

  async seed(): Promise<ApiResponse<SeedResult>> {
    return await ApiClient.post<SeedResult>('/api/prompts/seed')
  }
}

export const VARIABLE_REGEX = /\{\{\s*([A-Za-z_][\w.-]*)\s*\}\}/g

export function extractVariables(blocks: PromptBlock[]): string[] {
  const set = new Set<string>()
  for (const block of blocks) {
    if (block.type !== 'text' || !block.content) continue
    let match: RegExpExecArray | null
    const re = new RegExp(VARIABLE_REGEX.source, 'g')
    while ((match = re.exec(block.content)) !== null) {
      set.add(match[1])
    }
  }
  return Array.from(set).sort()
}
