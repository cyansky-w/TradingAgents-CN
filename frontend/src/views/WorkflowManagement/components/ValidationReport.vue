<template>
  <el-dialog :model-value="visible" title="校验结果" width="500px" @update:model-value="$emit('update:visible', $event)">
    <el-result v-if="errors.length === 0" icon="success" title="校验通过" />
    <div v-else>
      <p>{{ errorCount }} 个错误, {{ warningCount }} 个警告</p>
      <div v-for="(err, i) in errors" :key="i" class="validation-item" :class="`validation-${err.level}`">
        <span>{{ err.level === 'error' ? '❌' : '⚠️' }}</span>
        <span>{{ err.message }}</span>
        <el-button v-if="err.nodeId" size="small" text @click="$emit('focusNode', err.nodeId!)">定位</el-button>
      </div>
    </div>
    <template #footer>
      <el-button @click="$emit('update:visible', false)">关闭</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { ValidationError } from '../composables/useWorkflowValidation'

const props = defineProps<{
  visible: boolean
  errors: ValidationError[]
}>()

defineEmits<{
  'update:visible': [value: boolean]
  focusNode: [nodeId: string]
}>()

const errorCount = computed(() => props.errors.filter(e => e.level === 'error').length)
const warningCount = computed(() => props.errors.filter(e => e.level === 'warning').length)
</script>

<style scoped>
.validation-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 0;
  border-bottom: 1px solid var(--el-border-color-lighter);
  font-size: 13px;
}
.validation-error { color: var(--el-color-danger); }
.validation-warning { color: var(--el-color-warning); }
</style>
