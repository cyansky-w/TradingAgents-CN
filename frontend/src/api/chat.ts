import { ApiClient } from './request'
import type { Conversation, ConversationCreate, ConversationUpdate, ChatMessage, ChatRequest, ToolInfo } from '@/types/chat'

export const chatApi = {
  listConversations(archived?: boolean, limit?: number) {
    return ApiClient.get<Conversation[]>('/api/chat/conversations', { archived, limit })
  },

  createConversation(data?: ConversationCreate) {
    return ApiClient.post<Conversation>('/api/chat/conversations', data || {})
  },

  getConversation(id: string) {
    return ApiClient.get<Conversation>(`/api/chat/conversations/${id}`)
  },

  updateConversation(id: string, data: ConversationUpdate) {
    return ApiClient.patch<Conversation>(`/api/chat/conversations/${id}`, data)
  },

  deleteConversation(id: string) {
    return ApiClient.delete(`/api/chat/conversations/${id}`)
  },

  getMessages(convId: string, limit?: number) {
    return ApiClient.get<ChatMessage[]>(`/api/chat/conversations/${convId}/messages`, { limit })
  },

  sendMessage(data: ChatRequest) {
    return ApiClient.post<ChatMessage>('/api/chat/send', data)
  },

  listTools() {
    return ApiClient.get<ToolInfo[]>('/api/chat/tools')
  },
}

export function streamChat(
  convId: string,
  message: string,
  signal?: AbortSignal,
): Promise<Response> {
  const baseUrl = import.meta.env.VITE_API_BASE_URL || ''
  const token = localStorage.getItem('auth-token')

  const url = `${baseUrl}/api/chat/stream/${encodeURIComponent(convId)}?message=${encodeURIComponent(message)}`

  return fetch(url, {
    method: 'GET',
    headers: {
      'Authorization': `Bearer ${token}`,
      'Accept': 'text/event-stream',
      'Cache-Control': 'no-cache',
    },
    signal,
  })
}
