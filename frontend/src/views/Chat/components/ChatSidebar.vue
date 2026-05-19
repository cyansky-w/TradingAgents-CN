<script setup lang="ts">
import { computed } from 'vue'
import { useChatStore } from '@/stores/chat'
import { ElButton, ElPopconfirm } from 'element-plus'
import { Plus, Delete } from '@element-plus/icons-vue'

const chatStore = useChatStore()

const conversations = computed(() => chatStore.sortedConversations)
const activeId = computed(() => chatStore.activeConversationId)

async function handleNewChat() {
  await chatStore.createConversation()
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
    <div class="flex items-center justify-between p-4 border-b border-border">
      <h2 class="font-semibold text-sm">对话列表</h2>
      <ElButton :icon="Plus" size="small" type="primary" circle @click="handleNewChat" />
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
