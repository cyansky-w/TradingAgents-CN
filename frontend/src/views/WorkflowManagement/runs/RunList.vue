<script setup lang="ts">
import type { WorkflowRun } from '@/api/workflows'

defineProps<{
  runs: WorkflowRun[]
  loading: boolean
  runLoading: boolean
}>()

defineEmits<{
  run: []
  refresh: []
  viewRun: [runId: string]
  cancelRun: [runId: string]
}>()

function statusLabel(status: string) {
  const map: Record<string, string> = { pending: '等待', running: '运行中', completed: '完成', failed: '失败', cancelled: '已取消' }
  return map[status] || status
}

function statusType(status: string) {
  const map: Record<string, string> = { pending: 'info', running: 'warning', completed: 'success', failed: 'danger', cancelled: 'info' }
  return (map[status] || 'info') as any
}

function formatTime(value: string) {
  if (!value)
    return '-'
  try { return new Date(value).toLocaleString() } catch { return value }
}
</script>

<template>
  <div class="run-list-section">
    <div class="section-header">
      <h4>运行历史</h4>
      <div class="run-actions">
        <el-button size="small" type="primary" :loading="runLoading" @click="$emit('run')">
          手动执行
        </el-button>
        <el-button size="small" :loading="loading" @click="$emit('refresh')">
          刷新
        </el-button>
      </div>
    </div>
    <el-table v-if="runs.length" :data="runs" size="small" stripe style="margin-top: 8px">
      <el-table-column prop="id" label="ID" width="100">
        <template #default="{ row }">
          <el-button size="small" text type="primary" class="mono" @click="$emit('viewRun', row.id)">
            {{ row.id.slice(-6) }}
          </el-button>
        </template>
      </el-table-column>
      <el-table-column prop="status" label="状态" width="100">
        <template #default="{ row }">
          <el-tag :type="statusType(row.status)" size="small">
            {{ statusLabel(row.status) }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="trigger_type" label="触发" width="80">
        <template #default="{ row }">
          {{ row.trigger_type }}
        </template>
      </el-table-column>
      <el-table-column prop="started_at" label="开始时间" width="160">
        <template #default="{ row }">
          {{ formatTime(row.started_at) }}
        </template>
      </el-table-column>
      <el-table-column prop="completed_at" label="完成时间" width="160">
        <template #default="{ row }">
          {{ formatTime(row.completed_at) }}
        </template>
      </el-table-column>
      <el-table-column label="操作" width="80">
        <template #default="{ row }">
          <el-button v-if="row.status === 'running'" size="small" text type="danger" @click="$emit('cancelRun', row.id)">
            取消
          </el-button>
        </template>
      </el-table-column>
    </el-table>
    <div v-else class="text-muted">
      暂无运行记录
    </div>
  </div>
</template>

<style scoped>
.run-list-section { margin-bottom: 20px; }
.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-bottom: 1px solid var(--el-border-color-lighter);
  padding-bottom: 6px;
  margin-bottom: 12px;
}
.section-header h4 {
  margin: 0;
  font-size: 14px;
  color: var(--el-text-color-secondary);
}
.run-actions {
  display: flex;
  gap: 8px;
}
.mono { font-family: monospace; font-size: 13px; }
.text-muted { color: var(--el-text-color-placeholder); font-size: 13px; }
</style>
