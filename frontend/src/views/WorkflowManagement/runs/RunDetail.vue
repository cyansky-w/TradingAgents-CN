<script setup lang="ts">
import type { WorkflowRun } from '@/api/workflows'
import { ArrowLeft, Loading } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { workflowsApi } from '@/api/workflows'
import { useAuthStore } from '@/stores/auth'

const route = useRoute()
const router = useRouter()
const runId = route.params.runId as string

const run = ref<Partial<WorkflowRun>>({
  id: '',
  workflow_id: '',
  workflow_name: '',
  status: 'pending',
  trigger_type: '',
  input: {},
  node_executions: [],
  started_at: '',
  completed_at: ''
})

const sseConnected = ref(false)
const sseError = ref(false)
const sseEvents = ref<Array<{ time: string, type: string, summary: string }>>([])
let eventSource: EventSource | null = null

function runStatusLabel(status?: string) {
  const map: Record<string, string> = { pending: '等待', running: '运行中', completed: '完成', failed: '失败', cancelled: '已取消' }
  return map[status || ''] || status || '-'
}

function runStatusType(status?: string) {
  const map: Record<string, string> = { pending: 'info', running: 'warning', completed: 'success', failed: 'danger', cancelled: 'info' }
  return (map[status || ''] || 'info') as any
}

function nodeStatusType(status?: string) {
  const map: Record<string, string> = { completed: 'success', running: 'warning', failed: 'danger', pending: 'info' }
  return (map[status || ''] || 'info') as any
}

function formatTime(value?: string) {
  if (!value)
    return '-'
  try { return new Date(value).toLocaleString() } catch { return value }
}

function formatOutput(output: any) {
  if (!output)
    return '-'
  if (typeof output === 'string')
    return output.length > 500 ? `${output.slice(0, 500)}...` : output
  try {
    const json = JSON.stringify(output, null, 2)
    return json.length > 500 ? `${json.slice(0, 500)}...` : json
  } catch {
    return String(output)
  }
}

function goBack() {
  router.back()
}

async function loadRun() {
  try {
    const res = await workflowsApi.getRun(runId)
    if (res.success) {
      run.value = res.data
      return res.data
    }
  } catch (err: any) {
    ElMessage.error('加载运行详情失败')
  }
  return null
}

async function handleCancel() {
  try {
    const res = await workflowsApi.cancelRun(runId)
    if (res.success) {
      ElMessage.success('已取消')
      disconnectSSE()
      await loadRun()
    }
  } catch (err: any) {
    ElMessage.error(err?.response?.data?.detail || '取消失败')
  }
}

function connectSSE() {
  disconnectSSE()
  sseError.value = false

  const authStore = useAuthStore()
  const token = authStore.token || localStorage.getItem('auth-token') || ''
  const url = `/api/workflows/runs/${runId}/stream?token=${encodeURIComponent(token)}`

  eventSource = new EventSource(url)
  sseConnected.value = true

  eventSource.addEventListener('status', (e: MessageEvent) => {
    try {
      const data = JSON.parse(e.data)
      run.value = { ...run.value, ...data }
      addSseEvent('status', `状态: ${data.status}`)
    } catch { /* ignore */ }
  })

  eventSource.addEventListener('error', () => {
    addSseEvent('error', '连接错误')
  })

  eventSource.addEventListener('done', () => {
    addSseEvent('done', '执行结束')
    disconnectSSE()
    loadRun()
  })

  eventSource.onerror = () => {
    sseConnected.value = false
    sseError.value = true
    eventSource?.close()
    eventSource = null
    // Final refresh
    loadRun()
  }
}

function disconnectSSE() {
  if (eventSource) {
    eventSource.close()
    eventSource = null
  }
  sseConnected.value = false
}

function addSseEvent(type: string, summary: string) {
  sseEvents.value.push({
    time: new Date().toLocaleTimeString(),
    type,
    summary
  })
}

onMounted(async () => {
  const data = await loadRun()
  if (data && data.status === 'running') {
    connectSSE()
  }
})

onBeforeUnmount(() => {
  disconnectSSE()
})
</script>

<template>
  <div class="run-detail">
    <div class="run-header">
      <el-button text @click="goBack">
        <el-icon><ArrowLeft /></el-icon> 返回
      </el-button>
      <span class="run-title">运行详情</span>
      <el-tag :type="runStatusType(run.status)" size="large">
        {{ runStatusLabel(run.status) }}
      </el-tag>
      <div class="run-header-actions">
        <el-button v-if="run.status === 'running'" size="small" type="danger" @click="handleCancel">
          取消运行
        </el-button>
      </div>
    </div>

    <el-row :gutter="20">
      <el-col :span="16">
        <div class="run-info-card">
          <h4>基本信息</h4>
          <el-descriptions :column="2" size="small" border>
            <el-descriptions-item label="运行 ID">
              {{ run.id }}
            </el-descriptions-item>
            <el-descriptions-item label="工作流">
              {{ run.workflow_name }}
            </el-descriptions-item>
            <el-descriptions-item label="触发方式">
              {{ run.trigger_type }}
            </el-descriptions-item>
            <el-descriptions-item label="状态">
              {{ runStatusLabel(run.status) }}
            </el-descriptions-item>
            <el-descriptions-item label="开始时间">
              {{ formatTime(run.started_at) }}
            </el-descriptions-item>
            <el-descriptions-item label="完成时间">
              {{ formatTime(run.completed_at) }}
            </el-descriptions-item>
          </el-descriptions>
        </div>

        <div class="run-info-card">
          <h4>节点执行状态</h4>
          <el-table v-if="run.node_executions?.length" :data="run.node_executions" size="small" stripe>
            <el-table-column prop="node_id" label="节点" width="160">
              <template #default="{ row }">
                <span class="mono">{{ row.node_id }}</span>
              </template>
            </el-table-column>
            <el-table-column prop="status" label="状态" width="100">
              <template #default="{ row }">
                <el-tag :type="nodeStatusType(row.status)" size="small">
                  {{ row.status }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="output" label="输出">
              <template #default="{ row }">
                <div class="node-output mono">
                  {{ formatOutput(row.output) }}
                </div>
              </template>
            </el-table-column>
          </el-table>
          <div v-else-if="run.status === 'running'" class="loading-placeholder">
            <el-icon class="is-loading">
              <Loading />
            </el-icon> 等待节点状态...
          </div>
          <div v-else class="text-muted">
            无节点执行记录
          </div>
        </div>

        <div v-if="run.error" class="run-info-card run-error-card">
          <h4>错误信息</h4>
          <pre class="error-text">{{ run.error }}</pre>
        </div>

        <div v-if="run.output" class="run-info-card">
          <h4>输出</h4>
          <pre class="output-text">{{ formatOutput(run.output) }}</pre>
        </div>
      </el-col>

      <el-col :span="8">
        <div class="run-info-card">
          <h4>输入数据</h4>
          <pre class="output-text">{{ JSON.stringify(run.input || {}, null, 2) }}</pre>
        </div>

        <div class="run-info-card">
          <h4>SSE 连接状态</h4>
          <div class="sse-status">
            <el-tag :type="sseConnected ? 'success' : sseError ? 'danger' : 'info'" size="small">
              {{ sseConnected ? '已连接' : sseError ? '断开' : '未连接' }}
            </el-tag>
            <el-button v-if="run.status === 'running' && !sseConnected" size="small" text @click="connectSSE">
              重连
            </el-button>
          </div>
          <div v-if="sseEvents.length" class="sse-events">
            <div v-for="(evt, i) in sseEvents.slice(-10)" :key="i" class="sse-event">
              <span class="sse-event-time">{{ evt.time }}</span>
              <el-tag :type="evt.type === 'status' ? 'primary' : evt.type === 'error' ? 'danger' : 'info'" size="small">
                {{ evt.type }}
              </el-tag>
              <span class="sse-event-data">{{ evt.summary }}</span>
            </div>
          </div>
        </div>
      </el-col>
    </el-row>
  </div>
</template>

<style scoped>
.run-detail { padding: 20px; height: 100%; }
.run-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 20px;
}
.run-title { font-size: 18px; font-weight: 600; flex: 1; }
.run-header-actions { display: flex; gap: 8px; }
.run-info-card {
  background: var(--el-bg-color);
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 8px;
  padding: 16px;
  margin-bottom: 16px;
}
.run-info-card h4 {
  margin: 0 0 12px;
  font-size: 14px;
  color: var(--el-text-color-secondary);
  border-bottom: 1px solid var(--el-border-color-lighter);
  padding-bottom: 6px;
}
.run-error-card { border-color: var(--el-color-danger-light-7); }
.error-text {
  color: var(--el-color-danger);
  font-size: 12px;
  white-space: pre-wrap;
  word-break: break-all;
  margin: 0;
  max-height: 200px;
  overflow: auto;
}
.output-text {
  font-size: 12px;
  white-space: pre-wrap;
  word-break: break-all;
  margin: 0;
  max-height: 300px;
  overflow: auto;
  color: var(--el-text-color-regular);
}
.node-output {
  font-size: 11px;
  white-space: pre-wrap;
  word-break: break-all;
  max-height: 120px;
  overflow: auto;
}
.mono { font-family: monospace; }
.text-muted { color: var(--el-text-color-placeholder); font-size: 13px; }
.loading-placeholder {
  text-align: center;
  padding: 24px;
  color: var(--el-text-color-placeholder);
}
.sse-status {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}
.sse-events {
  max-height: 200px;
  overflow: auto;
}
.sse-event {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 0;
  font-size: 12px;
  border-bottom: 1px solid var(--el-border-color-extra-light);
}
.sse-event-time {
  color: var(--el-text-color-placeholder);
  font-family: monospace;
  font-size: 11px;
}
.sse-event-data {
  font-size: 12px;
}
</style>
