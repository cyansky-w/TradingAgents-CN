import type { ApiResponse } from '@/api/request'
import type { ChatMessage, Conversation, ConversationCreate, ToolInfo } from '@/types/chat'
import { ElMessage } from 'element-plus'
import { defineStore } from 'pinia'
import { chatApi, streamChat } from '@/api/chat'

function unwrap<T>(res: any): T {
  if (Array.isArray(res))
    return res as T
  if (res && typeof res === 'object' && 'success' in res)
    return (res as ApiResponse<T>).data as T
  return res as T
}

export interface ChatState {
  conversations: Conversation[]
  activeConversationId: string | null
  messages: ChatMessage[]
  streamingContent: string
  isStreaming: boolean
  isSending: boolean
  abortController: AbortController | null
  tools: ToolInfo[]
  toolsLoaded: boolean
}

export const useChatStore = defineStore('chat', {
  state: (): ChatState => ({
    conversations: [],
    activeConversationId: null,
    messages: [],
    streamingContent: '',
    isStreaming: false,
    isSending: false,
    abortController: null,
    tools: [],
    toolsLoaded: false
  }),

  getters: {
    activeConversation(): Conversation | undefined {
      return this.conversations.find(c => c.id === this.activeConversationId)
    },

    sortedConversations(): Conversation[] {
      return [...this.conversations].sort(
        (a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime()
      )
    }
  },

  actions: {
    async loadConversations() {
      try {
        const res: any = await chatApi.listConversations()
        this.conversations = unwrap<Conversation[]>(res)
      } catch (e) {
        console.error('Failed to load conversations:', e)
      }
    },

    async createConversation(payload?: string | ConversationCreate) {
      try {
        const request = typeof payload === 'string' ? { title: payload } : (payload || {})
        const res: any = await chatApi.createConversation(request)
        const data = unwrap<Conversation>(res)
        if (data && data.id) {
          this.conversations.unshift(data)
          this.activeConversationId = data.id
          this.messages = []
          return data
        }
      } catch (e) {
        console.error('Failed to create conversation:', e)
        ElMessage.error('创建对话失败')
      }
      return null
    },

    async selectConversation(id: string) {
      this.activeConversationId = id
      this.messages = []
      this.streamingContent = ''
      await this.loadMessages(id)
    },

    async loadMessages(convId?: string) {
      const id = convId || this.activeConversationId
      if (!id)
        return

      try {
        const res: any = await chatApi.getMessages(id)
        this.messages = unwrap<ChatMessage[]>(res)
      } catch (e) {
        console.error('Failed to load messages:', e)
      }
    },

    async sendMessage(content: string) {
      const convId = this.activeConversationId
      if (!convId || !content.trim())
        return

      if (this.isStreaming) {
        ElMessage.warning('正在接收回复中，请稍候')
        return
      }

      this.isSending = true
      this.streamingContent = ''
      this.isStreaming = true

      this.messages.push({
        id: `temp-${Date.now()}`,
        conversation_id: convId,
        role: 'user',
        content: content.trim(),
        created_at: new Date().toISOString()
      })

      try {
        this.abortController = new AbortController()

        const response = await streamChat(convId, content.trim(), this.abortController.signal)

        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`)
        }

        const reader = response.body?.getReader()
        if (!reader)
          throw new Error('No response body')

        const decoder = new TextDecoder()
        let buffer = ''
        let currentEvent = ''

        while (true) {
          const { done, value } = await reader.read()
          if (done)
            break

          buffer += decoder.decode(value, { stream: true })
          const lines = buffer.split('\n')
          buffer = lines.pop() || ''

          for (const line of lines) {
            if (line.startsWith('event: ')) {
              currentEvent = line.slice(7).trim()
              continue
            }
            if (!line.startsWith('data: '))
              continue
            const jsonStr = line.slice(6).trim()
            if (!jsonStr) { currentEvent = ''; continue }

            try {
              const payload = JSON.parse(jsonStr)
              switch (currentEvent) {
                case 'token':
                  this.streamingContent += payload.content || payload.token || ''
                  break
                case 'done':
                  if (payload.message_id) {
                    this.messages.push({
                      id: payload.message_id,
                      conversation_id: convId,
                      role: 'assistant',
                      content: payload.content || this.streamingContent,
                      created_at: new Date().toISOString()
                    })
                  }
                  break
                case 'tool_call':
                  this.messages.push({
                    id: `tool-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
                    conversation_id: convId,
                    role: 'tool',
                    content: `🔧 Calling: ${payload.name}(${JSON.stringify(payload.args)})`,
                    tool_calls: [{ name: payload.name, args: payload.args, id: payload.id }],
                    created_at: new Date().toISOString()
                  })
                  break
                case 'tool_result':
                  this.messages.push({
                    id: `tool-res-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
                    conversation_id: convId,
                    role: 'tool',
                    content: payload.content || '',
                    created_at: new Date().toISOString()
                  })
                  break
                case 'error':
                  ElMessage.error(payload.error || '流式响应出错')
                  break
              }
              currentEvent = ''
            } catch {
              currentEvent = ''
            }
          }
        }

        if (this.streamingContent && this.messages.length > 0) {
          const lastMsg = this.messages[this.messages.length - 1]
          if (lastMsg.role !== 'assistant') {
            this.messages.push({
              id: `stream-${Date.now()}`,
              conversation_id: convId,
              role: 'assistant',
              content: this.streamingContent,
              created_at: new Date().toISOString()
            })
          }
        }
      } catch (e: any) {
        if (e.name !== 'AbortError') {
          console.error('Stream error:', e)
          ElMessage.error('消息发送失败')
        }
      } finally {
        this.isSending = false
        this.isStreaming = false
        this.streamingContent = ''
        this.abortController = null
        await this.loadConversations()
      }
    },

    cancelStream() {
      if (this.abortController) {
        this.abortController.abort()
        this.isStreaming = false
        this.isSending = false
      }
    },

    async deleteConversation(id: string) {
      try {
        await chatApi.deleteConversation(id)
        this.conversations = this.conversations.filter(c => c.id !== id)
        if (this.activeConversationId === id) {
          this.activeConversationId = null
          this.messages = []
        }
        ElMessage.success('对话已删除')
      } catch (e) {
        console.error('Failed to delete conversation:', e)
        ElMessage.error('删除对话失败')
      }
    },

    async updateConversationTitle(id: string, title: string) {
      try {
        const res: any = await chatApi.updateConversation(id, { title })
        const data = unwrap<Conversation>(res)
        if (data && data.id) {
          const conv = this.conversations.find(c => c.id === id)
          if (conv)
            conv.title = title
        }
      } catch (e) {
        console.error('Failed to update conversation title:', e)
      }
    },

    async loadTools() {
      if (this.toolsLoaded)
        return
      try {
        const res: any = await chatApi.listTools()
        this.tools = unwrap<ToolInfo[]>(res)
        this.toolsLoaded = true
      } catch (e) {
        console.error('Failed to load tools:', e)
      }
    }
  }
})
