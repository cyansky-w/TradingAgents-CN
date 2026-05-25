<template>
  <div class="config-panel" v-if="node">
    <h4>{{ node!.data.io_direction === 'output' ? '输出' : '输入' }}节点配置</h4>
    <el-form label-width="80px" size="small">
      <el-form-item label="标签">
        <el-input :model-value="node!.label" @update:model-value="(v: string) => { node!.label = v; emitChange() }" />
      </el-form-item>
      <el-form-item label="方向">
        <el-select :model-value="node!.data.io_direction" @update:model-value="(v: string) => { node!.data.io_direction = v; emitChange() }">
          <el-option label="输入" value="input" />
          <el-option label="输出" value="output" />
        </el-select>
      </el-form-item>
    </el-form>
  </div>
</template>

<script setup lang="ts">
import type { FlowNode } from '../composables/useWorkflowSync'

defineProps<{ node: FlowNode | null }>()
const emit = defineEmits<{ change: [] }>()

function emitChange() { emit('change') }
</script>

<style scoped>
.config-panel { padding: 12px; }
.config-panel h4 { margin: 0 0 12px; font-size: 14px; color: var(--el-text-color-secondary); }
</style>
