<template>
  <div class="config-panel">
    <h4>执行设置</h4>
    <el-form label-width="100px" size="small">
      <el-form-item label="超时秒数">
        <el-input-number v-if="editing" :model-value="settings.timeout" :min="1" controls-position="right" @update:model-value="(v: number | undefined) => update('timeout', v ?? 1)" />
        <span v-else>{{ settings.timeout }}</span>
      </el-form-item>
      <el-form-item label="失败策略">
        <el-select v-if="editing" :model-value="settings.on_failure || 'notify'" @update:model-value="(v: string) => update('on_failure', v)">
          <el-option label="通知" value="notify" />
          <el-option label="停止" value="stop" />
          <el-option label="继续" value="continue" />
        </el-select>
        <span v-else>{{ onFailureLabel }}</span>
      </el-form-item>
      <el-form-item label="失败重试">
        <el-input-number v-if="editing" :model-value="settings.retry_count" :min="0" :max="5" controls-position="right" @update:model-value="(v: number | undefined) => update('retry_count', v ?? 0)" />
        <span v-else>{{ settings.retry_count }}</span>
      </el-form-item>
    </el-form>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  settings: { timeout?: number; on_failure?: string; retry_count?: number }
  editing: boolean
}>()

const emit = defineEmits<{
  update: [key: string, value: any]
}>()

const onFailureLabel = computed(() => {
  const val = props.settings.on_failure || 'notify'
  const map: Record<string, string> = { notify: '通知', stop: '停止', continue: '继续' }
  return map[val] || val
})

function update(key: string, value: any) {
  emit('update', key, value)
}
</script>

<style scoped>
.config-panel { margin-bottom: 20px; }
.config-panel h4 {
  margin: 0 0 12px;
  font-size: 14px;
  color: var(--el-text-color-secondary);
  border-bottom: 1px solid var(--el-border-color-lighter);
  padding-bottom: 6px;
}
</style>
