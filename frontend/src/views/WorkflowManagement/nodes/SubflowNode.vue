<template>
  <div class="custom-node subflow-node">
    <div class="node-header">
      <el-icon size="14"><Share /></el-icon>
      <span class="node-title">{{ data.label || '子流程' }}</span>
    </div>
    <div class="node-body">
      <div v-if="data.workflowName" class="node-meta">{{ data.workflowName }}</div>
      <div v-else class="node-meta node-meta--empty">未绑定工作流</div>
    </div>
    <Handle type="target" :position="Position.Left" />
    <Handle type="source" :position="Position.Right" />
  </div>
</template>

<script setup lang="ts">
import { Handle, Position } from '@vue-flow/core'
import { Share } from '@element-plus/icons-vue'

defineProps<{ data: Record<string, any> }>()
</script>

<style scoped>
.custom-node {
  background: var(--el-bg-color);
  border: 2px solid var(--el-color-warning-light-5);
  border-radius: 8px;
  padding: 0;
  min-width: 160px;
  font-size: 12px;
}
.subflow-node { border-color: var(--el-color-warning-light-5); }
.node-header {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 10px;
  background: var(--el-color-warning-light-9);
  border-radius: 6px 6px 0 0;
  font-weight: 500;
  color: var(--el-color-warning-dark-2);
}
.node-body { padding: 6px 10px; }
.node-meta { color: var(--el-text-color-secondary); font-size: 11px; }
.node-meta--empty { color: var(--el-color-danger-light-3); font-style: italic; }
.node-title { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
</style>
