<script setup lang="ts">
import { computed } from 'vue'
import { useChatStore } from '@/stores/chat'
import type { ChatStatus } from 'ai'
import {
  PromptInput,
  PromptInputBody,
  PromptInputFooter,
  PromptInputSubmit,
  PromptInputTextarea,
  PromptInputTools,
  PromptInputButton,
} from '@/components/ai-elements/prompt-input'
import { PaperclipIcon } from 'lucide-vue-next'
import { ElButton } from 'element-plus'

const chatStore = useChatStore()

const status = computed<ChatStatus>(() => {
  if (chatStore.isStreaming) return 'streaming'
  if (chatStore.isSending) return 'submitted'
  return 'ready'
})

const isDisabled = computed(() => {
  return !chatStore.activeConversationId || chatStore.isStreaming
})

function handleSubmit({ text }: { text: string; files: any[] }) {
  if (!text.trim()) return
  chatStore.sendMessage(text)
}

function handleCancel() {
  chatStore.cancelStream()
}
</script>

<template>
  <div class="border-t border-border bg-background p-4">
    <PromptInput
      :initial-input="''"
      :global-drop="false"
      @submit="handleSubmit"
    >
      <PromptInputBody>
        <PromptInputTextarea
          :disabled="isDisabled"
          placeholder="输入您的消息... (Enter 发送, Shift+Enter 换行)"
        />
      </PromptInputBody>
      <PromptInputFooter>
        <PromptInputTools>
          <PromptInputButton
            :disabled="isDisabled"
            variant="ghost"
          >
            <PaperclipIcon class="size-4" />
          </PromptInputButton>
        </PromptInputTools>
        <PromptInputSubmit
          v-if="!chatStore.isStreaming"
          :status="status"
          :disabled="isDisabled"
        />
        <ElButton
          v-else
          type="danger"
          size="small"
          @click="handleCancel"
        >
          停止
        </ElButton>
      </PromptInputFooter>
    </PromptInput>
  </div>
</template>
