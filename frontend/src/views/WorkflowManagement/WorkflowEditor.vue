<template>
  <div class="workflow-editor">
    <WorkflowToolbar
      :workflow-name="workflowName"
      :error-count="validationErrors.filter(e => e.level === 'error').length"
      :saving="sync.saving.value"
      @back="goBack"
      @validate="handleValidate"
      @save="handleSave"
      @run="handleRun"
    />

    <div class="editor-body">
      <NodePalette />

      <FlowCanvas
        :nodes="flowNodes"
        :edges="flowEdges"
        :node-types="nodeTypes"
        @node-click="onNodeClick"
        @nodes-change="onNodesChange"
        @connect="onConnect"
        @drop="onDrop"
      />

      <NodeConfigPanel
        :selected-node="selectedNode"
        :agent-options="agentOptions"
        :workflow-options="workflowOptions"
        :current-workflow-id="workflowId"
        @change="markDirty"
        @delete-node="deleteSelectedNode"
      />
    </div>

    <ValidationReport
      :visible="validateVisible"
      :errors="validationErrors"
      @update:visible="validateVisible = $event"
      @focus-node="focusNode"
    />

    <!-- Run Dialog -->
    <el-dialog v-model="runDialogVisible" title="执行工作流" width="560px" destroy-on-close>
      <div class="run-dialog-body">
        <template v-if="templateVars.length">
          <div class="run-section-label">模板参数</div>
          <el-form size="small" label-position="top">
            <el-form-item v-for="v in templateVars" :key="v" :label="v">
              <el-input v-model="runForm[v]" :placeholder="`请输入 ${v}`" />
            </el-form-item>
          </el-form>
          <el-divider content-position="left">消息预览</el-divider>
          <div class="run-preview">{{ renderedMessage }}</div>
        </template>
        <template v-else>
          <div class="run-section-label">输入消息</div>
          <el-input v-model="runFreeText" type="textarea" :rows="6" placeholder="请输入要发送给工作流的消息" />
        </template>
      </div>
      <template #footer>
        <el-button @click="runDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="doRun" :loading="runLoading">执行</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, markRaw, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import '@vue-flow/core/dist/style.css'
import '@vue-flow/core/dist/theme-default.css'
import '@vue-flow/controls/dist/style.css'
import '@vue-flow/minimap/dist/style.css'

import WorkflowToolbar from './components/WorkflowToolbar.vue'
import NodePalette from './components/NodePalette.vue'
import FlowCanvas from './components/FlowCanvas.vue'
import NodeConfigPanel from './components/NodeConfigPanel.vue'
import ValidationReport from './components/ValidationReport.vue'

import AgentNode from './nodes/AgentNode.vue'
import SubflowNode from './nodes/SubflowNode.vue'
import IONode from './nodes/IONode.vue'

import {
  useWorkflowSync,
  toFlowNodes,
  toFlowEdges,
  autoLayoutIfNeeded,
  createNode,
  type FlowNode,
} from './composables/useWorkflowSync'
import { validateDag, type ValidationError } from './composables/useWorkflowValidation'
import { workflowsApi, type Workflow } from '@/api/workflows'
import { agentsApi, type Agent } from '@/api/agents'

const nodeTypes: Record<string, any> = {
  agent: markRaw(AgentNode),
  subflow: markRaw(SubflowNode),
  io: markRaw(IONode),
}

const route = useRoute()
const router = useRouter()
const workflowId = route.params.id as string
const workflowName = ref('')

const sync = useWorkflowSync()

const flowNodes = ref<FlowNode[]>([])
const flowEdges = ref<any[]>([])
const selectedNode = ref<FlowNode | null>(null)

const agentOptions = ref<Agent[]>([])
const workflowOptions = ref<Workflow[]>([])

const validationErrors = ref<ValidationError[]>([])
const validateVisible = ref(false)
const runDialogVisible = ref(false)
const runLoading = ref(false)
const runFreeText = ref('')
const runForm = ref<Record<string, string>>({})
const messageTemplate = ref('')

const templateVars = computed<string[]>(() => {
  const matches = messageTemplate.value.match(/\{\{(\w+)\}\}/g)
  if (!matches) return []
  return [...new Set(matches.map(m => m.replace(/\{\{|\}\}/g, '')))]
})

const renderedMessage = computed(() => {
  let msg = messageTemplate.value
  for (const v of templateVars.value) {
    msg = msg.replace(new RegExp(`\\{\\{${v}\\}\\}`, 'g'), runForm.value[v] || `{{${v}}}`)
  }
  return msg
})

let dirty = false

function markDirty() { dirty = true }

function goBack() {
  if (dirty) {
    if (!confirm('有未保存的更改，确认返回？')) return
  }
  router.push('/workflows')
}

async function loadWorkflow() {
  const wf = await sync.load(workflowId)
  if (!wf) {
    ElMessage.error('工作流不存在')
    router.push('/workflows')
    return
  }
  workflowName.value = wf.name
  messageTemplate.value = wf.message_template || ''
  flowNodes.value = toFlowNodes(wf.nodes)
  flowEdges.value = toFlowEdges(wf.edges)
  autoLayoutIfNeeded(flowNodes.value, flowEdges.value)
}

async function loadOptions() {
  const [agentRes, wfRes] = await Promise.all([
    agentsApi.list({ page: 1, page_size: 100 }),
    workflowsApi.list({ page: 1, page_size: 100 }),
  ])
  if (agentRes.success) agentOptions.value = agentRes.data.items
  if (wfRes.success) workflowOptions.value = wfRes.data.items.filter(w => w.id !== workflowId)
  resolveNodeNames()
}

function resolveNodeNames() {
  for (const node of flowNodes.value) {
    if (node.type === 'agent' && node.data.agent_id && !node.data.agentName) {
      const agent = agentOptions.value.find(a => a.id === node.data.agent_id)
      if (agent) node.data.agentName = agent.name
    }
    if (node.type === 'subflow' && node.data.workflow_id && !node.data.workflowName) {
      const wf = workflowOptions.value.find(w => w.id === node.data.workflow_id)
      if (wf) node.data.workflowName = wf.name
    }
  }
}

function onNodeClick({ node }: { node: any }) {
  selectedNode.value = flowNodes.value.find(n => n.id === node.id) || null
}

function onNodesChange() {
  dirty = true
}

function onConnect(params: any) {
  const id = `e_${params.source}_${params.target}`
  if (!flowEdges.value.find((e: any) => e.source === params.source && e.target === params.target)) {
    flowEdges.value = [...flowEdges.value, { id, source: params.source, target: params.target }]
    dirty = true
  }
}

function onDrop(type: string, x: number, y: number) {
  const node = createNode(type, x, y)
  flowNodes.value = [...flowNodes.value, node]
  dirty = true
}

function deleteSelectedNode() {
  if (!selectedNode.value) return
  const nodeId = selectedNode.value.id
  flowNodes.value = flowNodes.value.filter(n => n.id !== nodeId)
  flowEdges.value = flowEdges.value.filter((e: any) => e.source !== nodeId && e.target !== nodeId)
  selectedNode.value = null
  dirty = true
}

function focusNode(nodeId: string) {
  const node = flowNodes.value.find(n => n.id === nodeId)
  if (node) selectedNode.value = node
  validateVisible.value = false
}

function handleValidate() {
  validationErrors.value = validateDag(flowNodes.value, flowEdges.value, workflowId)
  validateVisible.value = true
}

async function handleSave() {
  const errors = validateDag(flowNodes.value, flowEdges.value)
  const hasErrors = errors.some(e => e.level === 'error')
  if (hasErrors) {
    validationErrors.value = errors
    validateVisible.value = true
    return
  }

  const result = await sync.save(workflowId, flowNodes.value, flowEdges.value)
  if (result) {
    ElMessage.success('保存成功')
    dirty = false
  }
}

function handleRun() {
  runForm.value = {}
  for (const v of templateVars.value) {
    runForm.value[v] = ''
  }
  runFreeText.value = ''
  runDialogVisible.value = true
}

async function doRun() {
  let input: Record<string, any>
  if (templateVars.value.length) {
    const missing = templateVars.value.find(v => !runForm.value[v]?.trim())
    if (missing) {
      ElMessage.error(`参数 "${missing}" 未填写`)
      return
    }
    input = {}
    for (const v of templateVars.value) {
      input[v] = runForm.value[v]
    }
  } else {
    if (!runFreeText.value.trim()) {
      ElMessage.error('请输入消息')
      return
    }
    input = { message: runFreeText.value }
  }
  runLoading.value = true
  try {
    const res = await workflowsApi.run(workflowId, input)
    if (res.success) {
      ElMessage.success('执行完成')
      runDialogVisible.value = false
    }
  } catch (err: any) {
    ElMessage.error(err?.response?.data?.detail || '执行失败')
  } finally {
    runLoading.value = false
  }
}

onMounted(async () => {
  await Promise.all([loadWorkflow(), loadOptions()])
})
</script>

<style scoped>
.workflow-editor {
  height: 100%;
  display: flex;
  flex-direction: column;
}
.editor-body {
  flex: 1;
  display: flex;
  overflow: hidden;
}
.run-dialog-body {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.run-section-label {
  font-size: 13px;
  font-weight: 500;
  color: var(--el-text-color-secondary);
}
.run-preview {
  background: var(--el-fill-color-lighter);
  border-radius: 6px;
  padding: 10px 12px;
  font-size: 13px;
  line-height: 1.6;
  color: var(--el-text-color-primary);
  white-space: pre-wrap;
}
</style>
