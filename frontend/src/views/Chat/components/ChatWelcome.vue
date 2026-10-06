<script setup lang="ts">
import { MessageCircleIcon } from 'lucide-vue-next'
import { ConversationEmptyState } from '@/components/ai-elements/conversation'
</script>

<template>
  <ConversationEmptyState
    title="AI 助手"
    description="选择一个对话或创建新对话开始交流"
  >
    <template #icon>
      <MessageCircleIcon class="size-12" />
    </template>
  </ConversationEmptyState>
</template>
