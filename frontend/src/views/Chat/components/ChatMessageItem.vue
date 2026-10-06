<script setup lang="ts">
import type { UIMessage } from 'ai'
import type { ChatMessage } from '@/types/chat'
import { computed } from 'vue'
import { Message, MessageContent, MessageResponse } from '@/components/ai-elements/message'

const props = defineProps<{
  message: ChatMessage
}>()

const role = computed<UIMessage['role']>(() =>
  props.message.role === 'tool' ? 'assistant' : props.message.role as UIMessage['role']
)
</script>

<template>
  <Message :from="role">
    <MessageContent>
      <MessageResponse :content="message.content" />
    </MessageContent>
  </Message>
</template>
