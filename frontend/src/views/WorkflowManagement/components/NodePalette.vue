<template>
  <div class="editor-palette">
    <h5>节点</h5>
    <div
      class="palette-item"
      draggable="true"
      @dragstart="(e) => onDragStart(e, 'agent')"
    >
      <el-icon><UserFilled /></el-icon>
      <span>Agent</span>
    </div>
    <div
      class="palette-item"
      draggable="true"
      @dragstart="(e) => onDragStart(e, 'subflow')"
    >
      <el-icon><Share /></el-icon>
      <span>子流程</span>
    </div>
    <div
      class="palette-item"
      draggable="true"
      @dragstart="(e) => onDragStart(e, 'io')"
    >
      <el-icon><Coin /></el-icon>
      <span>IO 节点</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { UserFilled, Share, Coin } from '@element-plus/icons-vue'

function onDragStart(event: DragEvent, type: string) {
  event.dataTransfer!.setData('application/vueflow', type)
  event.dataTransfer!.effectAllowed = 'move'
}
</script>

<style scoped>
.editor-palette {
  width: 180px;
  padding: 12px;
  border-right: 1px solid var(--el-border-color-lighter);
  background: var(--el-bg-color);
}
.editor-palette h5 {
  margin: 0 0 12px;
  font-size: 13px;
  color: var(--el-text-color-secondary);
}
.palette-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 10px;
  margin-bottom: 4px;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 6px;
  cursor: grab;
  font-size: 13px;
  transition: background 0.2s;
}
.palette-item:hover {
  background: var(--el-fill-color-light);
}
.palette-item:active {
  cursor: grabbing;
}
</style>
