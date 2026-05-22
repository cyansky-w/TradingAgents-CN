<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage, ElButton, ElPopconfirm } from 'element-plus'
import { useChatStore } from '@/stores/chat'
import { agentsApi } from '@/api/agents'
import type { Agent } from '@/api/agents'
import { Plus, Delete } from '@element-plus/icons-vue'

const chatStore = useChatStore()

const conversations = computed(() => chatStore.sortedConversations)
const activeId = computed(() => chatStore.activeConversationId)
const chatAgents = ref<Agent[]>([])
const selectedAgentId = ref('')
const agentsLoading = ref(false)

onMounted(async () => {
  await loadChatAgents()
})

async function loadChatAgents() {
  agentsLoading.value = true
  try {
    const res = await agentsApi.list({ enabled: true, is_chat: true, page: 1, page_size: 100 })
    if (res.success) {
      chatAgents.value = res.data.items
    }
  } catch (error) {
    console.error('Failed to load chat agents:', error)
    ElMessage.error('加载 Agent 失败')
  } finally {
    agentsLoading.value = false
  }
}

async function handleNewChat() {
  await chatStore.createConversation({
    agent_id: selectedAgentId.value || undefined,
  })
}

function handleSelect(id: string) {
  chatStore.selectConversation(id)
}

async function handleDelete(id: string) {
  await chatStore.deleteConversation(id)
}
</script>

<template>
  <div class="flex flex-col h-full border-r border-border bg-background">
    <!-- Header -->
    <div class="p-4 border-b border-border space-y-3">
      <div class="flex items-center justify-between">
        <h2 class="font-semibold text-sm">对话列表</h2>
        <ElButton :icon="Plus" size="small" type="primary" circle @click="handleNewChat" />
      </div>
      <el-select
        v-model="selectedAgentId"
        clearable
        filterable
        placeholder="选择 Agent"
        class="w-full"
        :loading="agentsLoading"
      >
        <el-option
          v-for="agent in chatAgents"
          :key="agent.id"
          :label="agent.name"
          :value="agent.id"
        />
      </el-select>
    </div>

    <!-- Conversations -->
    <div class="flex-1 overflow-y-auto p-2">
      <div
        v-for="conv in conversations"
        :key="conv.id"
        :class="[
          'group flex items-center gap-2 px-3 py-2.5 rounded-md cursor-pointer text-sm transition-colors',
          conv.id === activeId
            ? 'bg-accent text-accent-foreground'
            : 'hover:bg-muted text-foreground'
        ]"
        @click="handleSelect(conv.id)"
      >
        <span class="flex-1 truncate">
          {{ conv.title || '新对话' }}
        </span>
        <ElPopconfirm
          title="确定删除？"
          @confirm="handleDelete(conv.id)"
        >
          <template #reference>
            <span
              class="hidden group-hover:inline-flex text-muted-foreground hover:text-destructive cursor-pointer"
              @click.stop
            >
              <el-icon><Delete /></el-icon>
            </span>
          </template>
        </ElPopconfirm>
      </div>

      <div
        v-if="conversations.length === 0"
        class="text-muted-foreground text-sm text-center py-8"
      >
        暂无对话
      </div>
    </div>
  </div>
</template>
