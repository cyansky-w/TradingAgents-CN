<script setup lang="ts">
import { UserFilled } from '@element-plus/icons-vue'
import { Handle, Position } from '@vue-flow/core'

defineProps<{ data: Record<string, any> }>()
</script>

<template>
  <div class="custom-node agent-node">
    <div class="node-header">
      <el-icon size="14">
        <UserFilled />
      </el-icon>
      <span class="node-title">{{ data.label || 'Agent' }}</span>
    </div>
    <div class="node-body">
      <div v-if="data.agentName" class="node-meta">
        {{ data.agentName }}
      </div>
      <div v-else class="node-meta node-meta--empty">
        未绑定 Agent
      </div>
      <div v-if="data.loop_over" class="node-badge">
        <el-tag size="small" type="warning">
          循环
        </el-tag>
      </div>
    </div>
    <Handle type="target" :position="Position.Left" />
    <Handle type="source" :position="Position.Right" />
  </div>
</template>

<style scoped>
.custom-node {
  background: var(--el-bg-color);
  border: 2px solid var(--el-color-primary-light-5);
  border-radius: 8px;
  padding: 0;
  min-width: 160px;
  font-size: 12px;
}
.agent-node { border-color: var(--el-color-primary-light-5); }
.node-header {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 10px;
  background: var(--el-color-primary-light-9);
  border-radius: 6px 6px 0 0;
  font-weight: 500;
  color: var(--el-color-primary);
}
.node-body {
  padding: 6px 10px;
}
.node-meta {
  color: var(--el-text-color-secondary);
  font-size: 11px;
}
.node-meta--empty {
  color: var(--el-color-danger-light-3);
  font-style: italic;
}
.node-badge {
  margin-top: 4px;
}
.node-title {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
