<script setup lang="ts">
import { computed, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import {
  Conversation,
  ConversationContent,
  ConversationScrollButton
} from '@/components/ai-elements/conversation'
import { useChatStore } from '@/stores/chat'
import ChatInputArea from './components/ChatInputArea.vue'
import ChatMessageItem from './components/ChatMessageItem.vue'
import ChatSidebar from './components/ChatSidebar.vue'
import ChatWelcome from './components/ChatWelcome.vue'

const route = useRoute()
const chatStore = useChatStore()

const hasMessages = computed(() => chatStore.messages.length > 0 || chatStore.streamingContent)
const activeTitle = computed(() => chatStore.activeConversation?.title || 'AI 助手')

onMounted(async () => {
  await chatStore.loadConversations()

  const convId = route.params.id as string
  if (convId) {
    await chatStore.selectConversation(convId)
  }
})

watch(() => route.params.id, async newId => {
  if (newId && typeof newId === 'string') {
    await chatStore.selectConversation(newId)
  }
})
</script>

<template>
  <div class="flex h-full w-full overflow-hidden">
    <!-- Sidebar -->
    <div class="w-[300px] flex-shrink-0">
      <ChatSidebar />
    </div>

    <!-- Chat Area -->
    <div class="flex flex-1 flex-col min-w-0">
      <!-- Header -->
      <header class="flex items-center h-12 px-4 border-b border-border shrink-0">
        <h1 class="font-semibold text-sm truncate">
          {{ activeTitle }}
        </h1>
      </header>

      <!-- Messages -->
      <Conversation
        v-if="hasMessages"
        class="flex-1"
        anchor="auto"
      >
        <ConversationContent>
          <ChatMessageItem
            v-for="msg in chatStore.messages"
            :key="msg.id"
            :message="msg"
          />

          <!-- Streaming content -->
          <div
            v-if="chatStore.streamingContent"
            class="group flex w-full max-w-[80%] gap-2 is-assistant"
          >
            <div class="flex w-fit flex-col gap-2 overflow-hidden text-sm text-foreground">
              <div
                class="whitespace-pre-wrap text-sm"
                v-text="chatStore.streamingContent"
              />
            </div>
          </div>
        </ConversationContent>
        <ConversationScrollButton />
      </Conversation>

      <!-- Welcome -->
      <ChatWelcome v-else />

      <!-- Input -->
      <ChatInputArea />
    </div>
  </div>
</template>
