<template>
  <div class="editor-canvas" @drop="onDrop" @dragover.prevent>
    <VueFlow
      :nodes="nodes"
      :edges="edges"
      :node-types="nodeTypes"
      fit-view-on-init
      @node-click="(payload: any) => $emit('nodeClick', payload)"
      @nodes-change="() => $emit('nodesChange')"
      @connect="(params: any) => $emit('connect', params)"
    >
      <Background />
      <Controls />
      <MiniMap />
    </VueFlow>
  </div>
</template>

<script setup lang="ts">
import { VueFlow } from '@vue-flow/core'
import { Background } from '@vue-flow/background'
import { Controls } from '@vue-flow/controls'
import { MiniMap } from '@vue-flow/minimap'

defineProps<{
  nodes: any[]
  edges: any[]
  nodeTypes: Record<string, any>
}>()

const emit = defineEmits<{
  nodeClick: [payload: any]
  nodesChange: []
  connect: [params: any]
  drop: [type: string, x: number, y: number]
}>()

function onDrop(event: DragEvent) {
  const type = event.dataTransfer?.getData('application/vueflow')
  if (!type) return
  const bounds = (event.currentTarget as HTMLElement).getBoundingClientRect()
  const x = event.clientX - bounds.left
  const y = event.clientY - bounds.top
  emit('drop', type, x, y)
}
</script>

<style scoped>
.editor-canvas {
  flex: 1;
  height: 100%;
}
</style>
