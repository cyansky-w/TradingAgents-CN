<template>
  <div class="custom-node io-node" :class="[`io-node--${data.io_direction}`]">
    <div class="node-header">
      <el-icon size="14"><Coin /></el-icon>
      <span class="node-title">{{ data.label || (data.io_direction === 'input' ? '输入' : '输出') }}</span>
    </div>
    <Handle type="source" :position="Position.Right" v-if="data.io_direction === 'input'" />
    <Handle type="target" :position="Position.Left" v-if="data.io_direction === 'output'" />
  </div>
</template>

<script setup lang="ts">
import { Handle, Position } from '@vue-flow/core'
import { Coin } from '@element-plus/icons-vue'

defineProps<{ data: Record<string, any> }>()
</script>

<style scoped>
.custom-node {
  background: var(--el-bg-color);
  border: 2px solid var(--el-color-success-light-5);
  border-radius: 8px;
  padding: 0;
  min-width: 120px;
  font-size: 12px;
}
.io-node--output { border-color: var(--el-color-danger-light-5); }
.node-header {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 10px;
  background: var(--el-color-success-light-9);
  border-radius: 6px;
  font-weight: 500;
  color: var(--el-color-success-dark-2);
}
.io-node--output .node-header {
  background: var(--el-color-danger-light-9);
  color: var(--el-color-danger-dark-2);
}
.node-title { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
</style>
