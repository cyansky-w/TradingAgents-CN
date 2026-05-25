<template>
  <div class="workflow-management">
    <div class="page-header">
      <h2>工作流管理</h2>
      <div class="header-actions">
        <el-input
          v-model="searchText"
          placeholder="搜索工作流..."
          prefix-icon="Search"
          clearable
          style="width: 200px"
          @input="handleSearch"
        />
        <el-select v-model="filterTag" placeholder="标签" clearable style="width: 120px" @change="loadWorkflows(true)">
          <el-option v-for="tag in allTags" :key="tag" :label="tag" :value="tag" />
        </el-select>
        <el-select v-model="filterEnabled" placeholder="状态" clearable style="width: 100px" @change="loadWorkflows(true)">
          <el-option label="已启用" :value="true" />
          <el-option label="已禁用" :value="false" />
        </el-select>
        <el-button type="primary" @click="showCreateDialog">
          <el-icon><Plus /></el-icon> 新建
        </el-button>
        <el-button @click="handleSeed" :loading="seedLoading">
          <el-icon><Refresh /></el-icon> 初始化工作流
        </el-button>
      </div>
    </div>

    <div v-if="listLoading" class="grid-loading">
      <el-icon class="is-loading"><Loading /></el-icon> 加载中...
    </div>

    <div v-else-if="workflows.length === 0" class="grid-empty">
      <el-empty description="暂无工作流，点击「初始化工作流」添加系统预设" />
    </div>

    <el-scrollbar v-else class="card-grid-wrap">
      <div class="card-grid">
        <WorkflowCard
          v-for="wf in workflows"
          :key="wf.id"
          :workflow="wf"
          @detail="selectWorkflow(wf)"
          @edit="openEditor(wf)"
          @run="selectAndRun(wf)"
          @toggle="handleToggle"
          @validate="selectAndValidate(wf)"
          @delete="selectAndDelete(wf)"
        />
      </div>
      <div v-if="workflows.length >= total" class="grid-end">已加载全部 {{ total }} 个工作流</div>
    </el-scrollbar>

    <!-- Detail Drawer -->
    <el-drawer
      v-model="drawerVisible"
      :title="selectedWf?.name || ''"
      size="520px"
      destroy-on-close
    >
      <template v-if="selectedWf" #default>
        <div class="drawer-body">
          <div class="section">
            <h4>基本信息</h4>
            <el-form label-width="100px" size="small">
              <el-form-item label="编码">
                <span class="mono">{{ selectedWf.code }}</span>
              </el-form-item>
              <el-form-item label="名称">
                <el-input v-if="editing" v-model="editForm.name" />
                <span v-else>{{ selectedWf.name }}</span>
              </el-form-item>
              <el-form-item label="描述">
                <el-input v-if="editing" v-model="editForm.description" type="textarea" :rows="2" />
                <span v-else>{{ selectedWf.description || '-' }}</span>
              </el-form-item>
              <el-form-item label="消息模板">
                <el-input v-if="editing" v-model="editForm.message_template" type="textarea" :rows="3" placeholder="支持 {{变量名}} 语法" />
                <span v-else class="mono">{{ selectedWf.message_template || '-' }}</span>
              </el-form-item>
              <el-form-item label="输出模板">
                <el-input v-if="editing" v-model="editForm.output_template" placeholder="如 {{summary.output}}" />
                <span v-else class="mono">{{ selectedWf.output_template || '-' }}</span>
              </el-form-item>
            </el-form>
          </div>

          <div class="section">
            <h4>触发方式</h4>
            <el-form label-width="100px" size="small">
              <el-form-item label="类型">
                <el-select v-if="editing" v-model="editForm.trigger.type">
                  <el-option label="手动" value="manual" />
                  <el-option label="定时" value="cron" />
                  <el-option label="事件" value="event" />
                </el-select>
                <span v-else>{{ triggerTypeLabel(selectedWf.trigger?.type) }}</span>
              </el-form-item>
              <el-form-item v-if="editForm.trigger?.type === 'cron' || selectedWf.trigger?.type === 'cron'" label="Cron 表达式">
                <el-input v-if="editing" v-model="editForm.trigger.cron" placeholder="0 9 * * 1-5" />
                <span v-else class="mono">{{ selectedWf.trigger?.cron || '-' }}</span>
              </el-form-item>
            </el-form>
          </div>

          <div class="section">
            <h4>节点 ({{ selectedWf.nodes.length }})</h4>
            <div class="node-list">
              <div v-for="node in selectedWf.nodes" :key="node.id" class="node-chip">
                <el-tag :type="nodeTypeColor(node.type)" size="small">{{ nodeTypeLabel(node.type) }}</el-tag>
                <span class="node-label">{{ node.label || node.id }}</span>
              </div>
              <span v-if="selectedWf.nodes.length === 0" class="text-muted">无节点</span>
            </div>
          </div>

          <WorkflowSettings :settings="editing ? editForm.settings : selectedWf.settings" :editing="editing" @update="(key: string, value: any) => { (editForm.settings as any)[key] = value }" />

          <div class="section">
            <h4>标签</h4>
            <el-select v-if="editing" v-model="editForm.tags" multiple filterable allow-create default-first-option style="width: 100%">
              <el-option v-for="tag in allTags" :key="tag" :label="tag" :value="tag" />
            </el-select>
            <div v-else>
              <el-tag v-for="tag in selectedWf.tags" :key="tag" class="tag-chip">{{ tag }}</el-tag>
              <span v-if="selectedWf.tags.length === 0" class="text-muted">无标签</span>
            </div>
          </div>

          <RunList
            :runs="runs"
            :loading="runsLoading"
            :run-loading="runLoading"
            @run="handleRun"
            @refresh="loadRuns"
            @view-run="viewRunDetail"
            @cancel-run="handleCancelRun"
          />

          <div class="section">
            <h4>统计</h4>
            <div class="text-muted">
              调用 {{ selectedWf.usage_count }} 次
              <span v-if="selectedWf.last_used_at"> · 最后调用 {{ formatTime(selectedWf.last_used_at) }}</span>
              <span> · 创建 {{ formatTime(selectedWf.created_at) }}</span>
            </div>
          </div>
        </div>
      </template>

      <template #footer>
        <div class="drawer-footer">
          <template v-if="editing">
            <el-button type="primary" @click="handleSave" :loading="saveLoading">保存</el-button>
            <el-button @click="cancelEdit">取消</el-button>
          </template>
          <template v-else>
            <el-button type="primary" @click="startEdit">编辑</el-button>
            <el-button @click="openEditor()">编辑器</el-button>
            <el-button @click="handleValidate" :loading="validateLoading">校验 DAG</el-button>
            <el-button type="danger" @click="handleDelete">删除</el-button>
          </template>
        </div>
      </template>
    </el-drawer>

    <!-- Create Dialog -->
    <el-dialog v-model="createVisible" title="新建工作流" width="640px" destroy-on-close>
      <el-form :model="createForm" label-width="100px" size="small">
        <el-form-item label="编码" required>
          <el-input v-model="createForm.code" placeholder="daily_market_report" />
          <span class="text-muted">仅小写字母/数字/下划线，创建后不可修改</span>
        </el-form-item>
        <el-form-item label="名称" required>
          <el-input v-model="createForm.name" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="createForm.description" type="textarea" :rows="2" />
        </el-form-item>
        <el-form-item label="消息模板">
          <el-input v-model="createForm.message_template" type="textarea" :rows="3" placeholder="支持 {{变量名}} 语法" />
        </el-form-item>
        <el-form-item label="标签">
          <el-select v-model="createForm.tags" multiple filterable allow-create default-first-option style="width: 100%">
            <el-option v-for="tag in allTags" :key="tag" :label="tag" :value="tag" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createVisible = false">取消</el-button>
        <el-button type="primary" @click="handleCreate" :loading="createLoading">创建</el-button>
      </template>
    </el-dialog>

    <!-- Run Input Dialog -->
    <el-dialog v-model="runDialogVisible" title="执行工作流" width="500px" destroy-on-close>
      <template v-if="runTemplateVars.length">
        <div class="run-section-label">模板参数</div>
        <el-form size="small" label-position="top">
          <el-form-item v-for="v in runTemplateVars" :key="v" :label="v">
            <el-input v-model="runForm[v]" :placeholder="`请输入 ${v}`" />
          </el-form-item>
        </el-form>
      </template>
      <template v-else>
        <div class="run-section-label">输入消息</div>
        <el-input v-model="runFreeText" type="textarea" :rows="5" placeholder="请输入要发送给工作流的消息" />
      </template>
      <template #footer>
        <el-button @click="runDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="doRun" :loading="runLoading">执行</el-button>
      </template>
    </el-dialog>

    <!-- Validation Result Dialog -->
    <el-dialog v-model="validateVisible" title="DAG 校验结果" width="500px">
      <el-result v-if="validationResult" :icon="validationResult.valid ? 'success' : 'error'" :title="validationResult.valid ? '校验通过' : '校验失败'">
        <template v-if="!validationResult.valid" #sub-title>
          <ul class="validation-errors">
            <li v-for="(err, i) in validationResult.errors" :key="i">
              <span v-if="err.node_id" class="mono" style="margin-right:4px">[{{ err.node_id }}]</span>
              {{ err.message }}
            </li>
          </ul>
        </template>
        <template v-if="validationResult?.warnings?.length" #extra>
          <div class="validation-warnings">
            <p style="margin:0 0 4px;font-weight:500">警告</p>
            <ul class="validation-errors" style="color:var(--el-color-warning)">
              <li v-for="(w, i) in validationResult.warnings" :key="'w'+i">
                <span v-if="w.node_id" class="mono" style="margin-right:4px">[{{ w.node_id }}]</span>
                {{ w.message }}
              </li>
            </ul>
          </div>
        </template>
      </el-result>
      <template #footer>
        <el-button @click="validateVisible = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Loading, Plus, Refresh } from '@element-plus/icons-vue'
import { workflowsApi } from '@/api/workflows'
import WorkflowCard from './components/WorkflowCard.vue'
import WorkflowSettings from './configs/WorkflowSettings.vue'
import RunList from './runs/RunList.vue'
import type { Workflow, WorkflowCreateDto, WorkflowValidationResult, WorkflowRun } from '@/api/workflows'

const workflows = ref<Workflow[]>([])
const selectedWf = ref<Workflow | null>(null)
const allTags = ref<string[]>([])
const runs = ref<WorkflowRun[]>([])

const total = ref(0)
const listLoading = ref(false)
const saveLoading = ref(false)
const createLoading = ref(false)
const runLoading = ref(false)
const runsLoading = ref(false)
const validateLoading = ref(false)
const seedLoading = ref(false)

const router = useRouter()

const drawerVisible = ref(false)
const editing = ref(false)
const createVisible = ref(false)
const runDialogVisible = ref(false)
const validateVisible = ref(false)
const validationResult = ref<WorkflowValidationResult | null>(null)

const searchText = ref('')
const filterTag = ref('')
const filterEnabled = ref<boolean | string>('')
const runForm = ref<Record<string, string>>({})
const runFreeText = ref('')

const runTemplateVars = computed<string[]>(() => {
  const tpl = selectedWf.value?.message_template || ''
  const matches = tpl.match(/\{\{(\w+)\}\}/g)
  if (!matches) return []
  return [...new Set(matches.map(m => m.replace(/\{\{|\}\}/g, '')))]
})

let searchTimer: ReturnType<typeof setTimeout>

const editForm = reactive({
  name: '',
  description: '',
  message_template: '',
  output_template: '',
  trigger: { type: 'manual' as string, cron: '', event: '' },
  settings: { timeout: 3600, on_failure: 'notify', retry_count: 0 },
  tags: [] as string[]
})

const createForm = reactive({
  code: '',
  name: '',
  description: '',
  message_template: '',
  tags: [] as string[]
})

function triggerTypeLabel(type?: string) {
  const map: Record<string, string> = { manual: '手动', cron: '定时', event: '事件' }
  return map[type || 'manual'] || type || '手动'
}

function nodeTypeLabel(type: string) {
  const map: Record<string, string> = { agent: 'Agent', subflow: '子流程', io: 'IO' }
  return map[type] || type
}

function nodeTypeColor(type: string) {
  const map: Record<string, string> = { agent: 'primary', subflow: 'warning', io: 'success' }
  return (map[type] || 'info') as any
}

function formatTime(value: string) {
  if (!value) return '-'
  try { return new Date(value).toLocaleString() } catch { return value }
}

async function loadWorkflows(_reset = true) {
  listLoading.value = true
  try {
    const res = await workflowsApi.list({
      search: searchText.value || undefined,
      tag: filterTag.value || undefined,
      enabled: filterEnabled.value === '' ? undefined : Boolean(filterEnabled.value),
      page: 1,
      page_size: 100
    })
    if (!res.success) return
    workflows.value = res.data.items
    total.value = res.data.total
  } catch (err: any) {
    ElMessage.error(err?.response?.data?.detail || '加载工作流列表失败')
  } finally {
    listLoading.value = false
  }
}

async function loadTags() {
  const res = await workflowsApi.getTags()
  if (res.success) allTags.value = res.data
}

async function loadRuns() {
  if (!selectedWf.value) return
  runsLoading.value = true
  try {
    const res = await workflowsApi.listRuns(selectedWf.value.id)
    if (res.success) runs.value = res.data.items
  } catch {
    ElMessage.error('加载运行历史失败')
  } finally {
    runsLoading.value = false
  }
}

async function selectWorkflow(wf: Workflow) {
  if (editing.value) cancelEdit()
  selectedWf.value = wf
  fillEditForm(wf)
  runs.value = []
  drawerVisible.value = true
  loadRuns()
}

function fillEditForm(wf: Workflow) {
  editForm.name = wf.name
  editForm.description = wf.description
  editForm.message_template = wf.message_template || ''
  editForm.output_template = wf.output_template || ''
  editForm.trigger = {
    type: wf.trigger?.type || 'manual',
    cron: wf.trigger?.cron || '',
    event: wf.trigger?.event || ''
  }
  editForm.settings = {
    timeout: wf.settings?.timeout ?? 3600,
    on_failure: wf.settings?.on_failure || 'notify',
    retry_count: wf.settings?.retry_count ?? 0
  }
  editForm.tags = [...wf.tags]
}

function handleSearch() {
  clearTimeout(searchTimer)
  searchTimer = setTimeout(() => loadWorkflows(true), 300)
}

function startEdit() {
  if (!selectedWf.value) return
  fillEditForm(selectedWf.value)
  editing.value = true
}

function cancelEdit() {
  editing.value = false
  if (selectedWf.value) fillEditForm(selectedWf.value)
}

function showCreateDialog() {
  createForm.code = ''
  createForm.name = ''
  createForm.description = ''
  createForm.message_template = ''
  createForm.tags = []
  createVisible.value = true
}

async function handleCreate() {
  if (!createForm.code || !createForm.name) {
    ElMessage.warning('请填写编码和名称')
    return
  }
  createLoading.value = true
  try {
    const payload: WorkflowCreateDto = {
      ...createForm,
      nodes: [
        { id: 'start', type: 'io', label: '输入', config: { io_direction: 'input' } },
        { id: 'end', type: 'io', label: '输出', config: { io_direction: 'output' } }
      ],
      edges: [{ id: 'e1', source: 'start', target: 'end' }]
    }
    const res = await workflowsApi.create(payload)
    if (res.success) {
      ElMessage.success('创建成功')
      createVisible.value = false
      await loadWorkflows(true)
      await loadTags()
      await selectWorkflow(res.data)
    }
  } catch (err: any) {
    ElMessage.error(err?.response?.data?.detail || '创建失败')
  } finally {
    createLoading.value = false
  }
}

async function handleSave() {
  if (!selectedWf.value) return
  saveLoading.value = true
  try {
    const res = await workflowsApi.update(selectedWf.value.id, {
      name: editForm.name,
      description: editForm.description,
      message_template: editForm.message_template,
      output_template: editForm.output_template,
      trigger: editForm.trigger as any,
      settings: editForm.settings,
      tags: editForm.tags
    })
    if (res.success) {
      ElMessage.success('保存成功')
      selectedWf.value = res.data
      fillEditForm(res.data)
      editing.value = false
      await loadWorkflows(true)
      await loadTags()
    }
  } catch (err: any) {
    ElMessage.error(err?.response?.data?.detail || '保存失败')
  } finally {
    saveLoading.value = false
  }
}

async function handleToggle(wf: Workflow, enabled: boolean) {
  try {
    const res = await workflowsApi.toggle(wf.id, enabled)
    if (res.success) wf.enabled = enabled
  } catch (err: any) {
    ElMessage.error(err?.response?.data?.detail || '操作失败')
  }
}

async function handleDelete() {
  if (!selectedWf.value) return
  try {
    await ElMessageBox.confirm(`确认删除工作流「${selectedWf.value.name}」？`, '删除确认', { type: 'warning' })
    await workflowsApi.remove(selectedWf.value.id)
    ElMessage.success('删除成功')
    selectedWf.value = null
    drawerVisible.value = false
    await loadWorkflows(true)
  } catch (err: any) {
    if (err === 'cancel' || err === 'close') return
    ElMessage.error(err?.response?.data?.detail || '删除失败')
  }
}

async function selectAndValidate(wf: Workflow) {
  selectedWf.value = wf
  fillEditForm(wf)
  validateLoading.value = true
  try {
    const res = await workflowsApi.validate(wf.id)
    if (res.success) {
      validationResult.value = res.data
      validateVisible.value = true
    }
  } catch (err: any) {
    ElMessage.error(err?.response?.data?.detail || '校验失败')
  } finally {
    validateLoading.value = false
  }
}

async function handleValidate() {
  if (!selectedWf.value) return
  validateLoading.value = true
  try {
    const res = await workflowsApi.validate(selectedWf.value.id)
    if (res.success) {
      validationResult.value = res.data
      validateVisible.value = true
    }
  } catch (err: any) {
    ElMessage.error(err?.response?.data?.detail || '校验失败')
  } finally {
    validateLoading.value = false
  }
}

function selectAndRun(wf: Workflow) {
  selectedWf.value = wf
  fillEditForm(wf)
  runForm.value = {}
  for (const v of runTemplateVars.value) runForm.value[v] = ''
  runFreeText.value = ''
  runDialogVisible.value = true
}

function handleRun() {
  runForm.value = {}
  for (const v of runTemplateVars.value) runForm.value[v] = ''
  runFreeText.value = ''
  runDialogVisible.value = true
}

async function doRun() {
  if (!selectedWf.value) return
  let input: Record<string, any> = {}
  if (runTemplateVars.value.length) {
    const missing = runTemplateVars.value.find(v => !runForm.value[v]?.trim())
    if (missing) { ElMessage.error(`参数 "${missing}" 未填写`); return }
    for (const v of runTemplateVars.value) input[v] = runForm.value[v]
  } else {
    if (!runFreeText.value.trim()) { ElMessage.error('请输入消息'); return }
    input = { message: runFreeText.value }
  }
  runLoading.value = true
  try {
    const res = await workflowsApi.run(selectedWf.value.id, input)
    if (res.success) {
      ElMessage.success('执行完成')
      runDialogVisible.value = false
      await loadRuns()
    }
  } catch (err: any) {
    ElMessage.error(err?.response?.data?.detail || '执行失败')
  } finally {
    runLoading.value = false
  }
}

async function handleCancelRun(runId: string) {
  try {
    const res = await workflowsApi.cancelRun(runId)
    if (res.success) {
      ElMessage.success('已取消')
      await loadRuns()
    }
  } catch (err: any) {
    ElMessage.error(err?.response?.data?.detail || '取消失败')
  }
}

async function selectAndDelete(wf: Workflow) {
  selectedWf.value = wf
  await handleDelete()
}

async function handleSeed() {
  seedLoading.value = true
  try {
    const res = await workflowsApi.seed()
    if (res.success) {
      ElMessage.success(`初始化完成: 新增${res.data.created} 跳过${res.data.skipped}`)
      await loadWorkflows(true)
      await loadTags()
    }
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '初始化失败')
  } finally {
    seedLoading.value = false
  }
}

function openEditor(wf?: Workflow) {
  const id = wf?.id || selectedWf.value?.id
  if (id) router.push(`/workflows/${id}/edit`)
}

function viewRunDetail(runId: string) {
  router.push(`/workflows/runs/${runId}`)
}

onMounted(async () => {
  await loadTags()
  await loadWorkflows(true)
})
</script>

<style scoped>
.workflow-management {
  padding: 20px;
  height: 100%;
  display: flex;
  flex-direction: column;
}
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
  flex-wrap: wrap;
  gap: 12px;
}
.page-header h2 { margin: 0; }
.header-actions {
  display: flex;
  gap: 8px;
  align-items: center;
  flex-wrap: wrap;
}
.card-grid-wrap {
  flex: 1;
  overflow: auto;
}
.card-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 16px;
}
.grid-loading,
.grid-empty {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--el-text-color-secondary);
}
.grid-end {
  text-align: center;
  padding: 16px;
  color: var(--el-text-color-placeholder);
  font-size: 12px;
}
.drawer-body {
  padding: 0 4px;
}
.section { margin-bottom: 20px; }
.section > h4 {
  margin: 0 0 12px 0;
  font-size: 14px;
  color: var(--el-text-color-secondary);
  border-bottom: 1px solid var(--el-border-color-lighter);
  padding-bottom: 6px;
}
.mono { font-family: monospace; font-size: 13px; }
.text-muted { color: var(--el-text-color-placeholder); font-size: 13px; }
.tag-chip { margin-right: 6px; margin-bottom: 4px; }
.node-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.node-chip {
  display: flex;
  align-items: center;
  gap: 4px;
}
.node-label { font-size: 13px; }
.drawer-footer {
  display: flex;
  gap: 8px;
  justify-content: flex-end;
}
.validation-errors {
  list-style: disc;
  padding-left: 20px;
  text-align: left;
  color: var(--el-color-danger);
}
.run-section-label {
  font-size: 13px;
  font-weight: 500;
  color: var(--el-text-color-secondary);
  margin-bottom: 8px;
}
</style>
