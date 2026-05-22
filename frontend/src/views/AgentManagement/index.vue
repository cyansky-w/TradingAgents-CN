<template>
  <div class="agent-management">
    <div class="page-header">
      <h2>Agent 管理</h2>
      <div class="header-actions">
        <el-button type="primary" @click="showCreateDialog">
          <el-icon><Plus /></el-icon> 新建
        </el-button>
        <el-button @click="handleSeed" :loading="seedLoading">
          <el-icon><Refresh /></el-icon> 初始化种子
        </el-button>
      </div>
    </div>

    <el-row :gutter="20" class="flex-1">
      <el-col :span="7">
        <div class="filter-section">
          <el-input
            v-model="searchText"
            placeholder="搜索 Agent..."
            prefix-icon="Search"
            clearable
            @input="handleSearch"
          />
          <div class="filter-row">
            <el-select v-model="filterTag" placeholder="标签" clearable @change="loadAgents(true)">
              <el-option v-for="tag in allTags" :key="tag" :label="tag" :value="tag" />
            </el-select>
            <el-select v-model="filterEnabled" placeholder="状态" clearable @change="loadAgents(true)">
              <el-option label="已启用" :value="true" />
              <el-option label="已禁用" :value="false" />
            </el-select>
          </div>
          <div class="filter-row">
            <el-select v-model="filterIsChat" placeholder="类型" clearable @change="loadAgents(true)">
              <el-option label="工作流 Agent" :value="false" />
              <el-option label="聊天助手" :value="true" />
            </el-select>
          </div>
        </div>

        <el-scrollbar class="agent-list">
          <div
            v-for="agent in agents"
            :key="agent.id"
            class="agent-item"
            :class="{ active: selectedAgent?.id === agent.id }"
            @click="selectAgent(agent)"
          >
            <div class="agent-item-header">
              <span class="agent-name">{{ agent.name }}</span>
              <el-switch
                :model-value="agent.enabled"
                size="small"
                @click.stop
                @change="(val: any) => handleToggle(agent, !!val)"
              />
            </div>
            <div class="agent-item-meta">
              <el-tag size="small" :type="agent.is_chat ? 'success' : 'primary'">
                {{ agent.is_chat ? '聊天助手' : '工作流' }}
              </el-tag>
              <el-tag v-if="agent.is_system" size="small" type="info">系统</el-tag>
            </div>
            <div class="agent-code mono">{{ agent.code }}</div>
            <div class="agent-item-tags">
              <el-tag
                v-for="tag in agent.tags.slice(0, 3)"
                :key="tag"
                size="small"
                type="info"
                class="mini-tag"
              >
                {{ tag }}
              </el-tag>
            </div>
          </div>
          <el-empty v-if="agents.length === 0 && !listLoading" description="暂无 Agent" />
          <div v-if="listLoading" class="list-loading">
            <el-icon class="is-loading"><Loading /></el-icon> 加载中...
          </div>
          <div v-if="!listLoading && agents.length > 0 && agents.length >= total" class="list-end">
            已加载全部 {{ total }} 个 Agent
          </div>
        </el-scrollbar>
      </el-col>

      <el-col :span="17">
        <div v-if="selectedAgent" class="detail-panel">
          <div class="detail-header">
            <div class="detail-title-row">
              <el-input v-if="editing" v-model="editForm.name" class="edit-name-input" />
              <h3 v-else>{{ selectedAgent.name }}</h3>
              <div class="detail-badges">
                <el-tag :type="selectedAgent.is_chat ? 'success' : 'primary'">
                  {{ selectedAgent.is_chat ? '聊天助手' : '工作流 Agent' }}
                </el-tag>
                <el-tag v-if="selectedAgent.is_system" type="info">系统 Agent</el-tag>
              </div>
            </div>
          </div>

          <div class="detail-body">
            <div class="section">
              <h4>基本信息</h4>
              <el-form label-width="100px" size="small">
                <el-form-item label="编码">
                  <span class="mono">{{ selectedAgent.code }}</span>
                </el-form-item>
                <el-form-item label="名称">
                  <el-input v-if="editing" v-model="editForm.name" />
                  <span v-else>{{ selectedAgent.name }}</span>
                </el-form-item>
                <el-form-item label="描述">
                  <el-input v-if="editing" v-model="editForm.description" type="textarea" :rows="2" />
                  <span v-else>{{ selectedAgent.description || '-' }}</span>
                </el-form-item>
                <el-form-item label="聊天助手">
                  <el-switch v-if="editing" v-model="editForm.is_chat" />
                  <span v-else>{{ selectedAgent.is_chat ? '是' : '否' }}</span>
                </el-form-item>
              </el-form>
            </div>
            <div class="section">
              <div class="section-title-row">
                <h4>提示词绑定</h4>
                <el-button
                  size="small"
                  text
                  type="primary"
                  :disabled="!selectedPrompt"
                  @click="openPromptDetail()"
                >
                  查看
                </el-button>
              </div>
              <el-select
                v-if="editing"
                v-model="editForm.prompt_id"
                filterable
                placeholder="选择提示词"
                style="width: 100%"
              >
                <el-option
                  v-for="prompt in promptOptions"
                  :key="prompt.id"
                  :label="`${prompt.name} v${prompt.version}`"
                  :value="prompt.id"
                />
              </el-select>
              <span v-else>{{ currentPromptName }}</span>
            </div>

            <div class="section">
              <h4>提示词规格概览</h4>
              <el-collapse>
                <el-collapse-item title="绑定工具" name="tools">
                  <template v-if="selectedPrompt && selectedPrompt.bind_tools.length > 0">
                    <el-tag
                      v-for="toolCode in selectedPrompt.bind_tools"
                      :key="toolCode"
                      class="tag-chip"
                      :type="toolCallsLlm(toolCode) ? 'warning' : 'info'"
                    >
                      {{ toolCode }}
                      <span v-if="toolCallsLlm(toolCode)" class="ml-4">⚡</span>
                    </el-tag>
                    <div class="text-muted mt-8" v-if="hasLlmTool">
                      ⚡ 标记的工具内部调用大模型，可能产生额外消耗
                    </div>
                  </template>
                  <span v-else class="text-muted">未绑定工具</span>
                </el-collapse-item>
                <el-collapse-item title="变量概览" name="variables">
                  <div class="variables-overview">
                    <div class="variables-group">
                      <div class="variables-group-title">提示词文本变量</div>
                      <div v-if="promptTextVariables.length" class="variable-chip-list">
                        <el-tag v-for="variable in promptTextVariables" :key="variable" class="tag-chip" effect="plain">
                          {{ formatPromptVariable(variable) }}
                        </el-tag>
                      </div>
                      <span v-else class="text-muted">未发现文本变量</span>
                    </div>
                    <div class="variables-group">
                      <div class="variables-group-title">工具入参变量</div>
                      <div v-if="toolInputVariables.length" class="variable-chip-list">
                        <el-tag v-for="variable in toolInputVariables" :key="variable" class="tag-chip" type="success" effect="plain">
                          {{ variable }}
                        </el-tag>
                      </div>
                      <span v-else class="text-muted">未发现工具入参变量</span>
                    </div>
                  </div>
                </el-collapse-item>
                <el-collapse-item title="工作流输出" name="output">
                  <div>输出名：<span class="mono">{{ selectedAgent.code }}</span></div>
                  <div class="text-muted">
                    Agent 执行后的完整 LLM 输出文本会以该名称传递给工作流下游节点。
                  </div>
                </el-collapse-item>
              </el-collapse>
            </div>
            <div class="section">
              <h4>模型配置</h4>
              <el-switch v-if="editing" v-model="useDefaultModel" active-text="使用系统默认" />
              <span v-else>{{ selectedAgent.model_config ? '自定义模型' : '系统默认' }}</span>
              <div v-if="editing && !useDefaultModel" class="model-grid">
                <el-select v-model="editForm.model_config.provider" placeholder="provider" filterable @change="onProviderChange">
                  <el-option
                    v-for="provider in modelProviders"
                    :key="provider.name"
                    :label="provider.display_name"
                    :value="provider.name"
                  />
                </el-select>
                <el-select v-model="editForm.model_config.model" placeholder="model" filterable allow-create>
                  <el-option
                    v-for="modelName in providerModels"
                    :key="modelName"
                    :label="modelName"
                    :value="modelName"
                  />
                </el-select>
                <el-input-number
                  v-model="editForm.model_config.temperature"
                  :min="0"
                  :max="2"
                  :step="0.1"
                  controls-position="right"
                />
                <el-input-number
                  v-model="editForm.model_config.max_tokens"
                  :min="1"
                  controls-position="right"
                />
              </div>
              <div v-else-if="!editing && selectedAgent.model_config" class="model-summary">
                <span>{{ selectedAgent.model_config.provider || '默认' }}</span>
                <span style="margin-left: 8px">{{ selectedAgent.model_config.model || '默认' }}</span>
                <span style="margin-left: 8px" class="text-muted">温度 {{ selectedAgent.model_config.temperature }}</span>
                <span style="margin-left: 8px" class="text-muted">tokens {{ selectedAgent.model_config.max_tokens }}</span>
              </div>
            </div>
            <div class="section">
              <h4>运行参数</h4>
              <el-form label-width="100px" size="small">
                <el-form-item label="最大工具调用">
                  <el-input-number
                    v-if="editing"
                    v-model="editForm.parameters.max_tool_calls"
                    :min="1"
                    controls-position="right"
                  />
                  <span v-else>{{ selectedAgent.parameters.max_tool_calls }}</span>
                </el-form-item>
                <el-form-item label="超时秒数">
                  <el-input-number
                    v-if="editing"
                    v-model="editForm.parameters.timeout"
                    :min="1"
                    controls-position="right"
                  />
                  <span v-else>{{ selectedAgent.parameters.timeout }}</span>
                </el-form-item>
                <el-form-item label="失败重试">
                  <el-switch v-if="editing" v-model="editForm.parameters.retry_on_failure" />
                  <span v-else>{{ selectedAgent.parameters.retry_on_failure ? '是' : '否' }}</span>
                </el-form-item>
              </el-form>
            </div>
            <div class="section">
              <h4>标签</h4>
              <el-select
                v-if="editing"
                v-model="editForm.tags"
                multiple
                filterable
                allow-create
                default-first-option
                style="width: 100%"
              >
                <el-option v-for="tag in allTags" :key="tag" :label="tag" :value="tag" />
              </el-select>
              <div v-else>
                <el-tag v-for="tag in selectedAgent.tags" :key="tag" class="tag-chip">
                  {{ tag }}
                </el-tag>
                <span v-if="selectedAgent.tags.length === 0" class="text-muted">无标签</span>
              </div>
            </div>

            <div class="section">
              <h4>统计</h4>
              <div class="text-muted">
                调用 {{ selectedAgent.usage_count }} 次
                <span v-if="selectedAgent.last_used_at"> · 最后调用 {{ formatTime(selectedAgent.last_used_at) }}</span>
                <span> · 创建 {{ formatTime(selectedAgent.created_at) }}</span>
              </div>
            </div>
          </div>

          <div class="detail-footer">
            <template v-if="editing">
              <el-button type="primary" @click="handleSave" :loading="saveLoading">保存</el-button>
              <el-button @click="cancelEdit">取消</el-button>
            </template>
            <template v-else>
              <el-button type="primary" @click="startEdit">编辑</el-button>
              <el-button type="success" @click="showTestDialog">测试运行</el-button>
              <el-button v-if="!selectedAgent.is_system" type="danger" @click="handleDelete">
                删除
              </el-button>
            </template>
          </div>
        </div>
        <el-empty v-else description="选择左侧 Agent 查看详情" />
      </el-col>
    </el-row>

    <el-dialog v-model="createVisible" title="新建 Agent" width="640px" destroy-on-close>
      <el-form :model="createForm" label-width="100px" size="small">
        <el-form-item label="编码" required>
          <el-input v-model="createForm.code" placeholder="market_analyst" />
          <span class="text-muted">仅小写字母/数字/下划线，创建后不可修改</span>
        </el-form-item>
        <el-form-item label="名称" required>
          <el-input v-model="createForm.name" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="createForm.description" type="textarea" :rows="2" />
        </el-form-item>
        <el-form-item label="提示词" required>
          <div class="prompt-select-row">
            <el-select
              v-model="createForm.prompt_id"
              filterable
              placeholder="选择提示词"
              style="width: 100%"
            >
              <el-option
                v-for="prompt in promptOptions"
                :key="prompt.id"
                :label="`${prompt.name} v${prompt.version}`"
                :value="prompt.id"
              />
            </el-select>
            <el-button
              size="small"
              text
              type="primary"
              :disabled="!createSelectedPrompt"
              @click="openPromptDetail(createSelectedPrompt)"
            >
              查看
            </el-button>
          </div>
        </el-form-item>
        <el-form-item label="聊天助手">
          <el-switch v-model="createForm.is_chat" />
        </el-form-item>
        <el-form-item label="模型配置">
          <div class="create-model-section">
            <el-switch v-model="createUseDefaultModel" active-text="使用系统默认" />
            <div v-if="!createUseDefaultModel" class="model-grid">
              <el-select
                v-model="createForm.model_config!.provider"
                placeholder="provider"
                filterable
                @change="onCreateProviderChange"
              >
                <el-option
                  v-for="provider in modelProviders"
                  :key="provider.name"
                  :label="provider.display_name"
                  :value="provider.name"
                />
              </el-select>
              <el-select v-model="createForm.model_config!.model" placeholder="model" filterable allow-create>
                <el-option
                  v-for="modelName in createProviderModels"
                  :key="modelName"
                  :label="modelName"
                  :value="modelName"
                />
              </el-select>
              <el-input-number
                v-model="createForm.model_config!.temperature"
                :min="0"
                :max="2"
                :step="0.1"
                controls-position="right"
              />
              <el-input-number
                v-model="createForm.model_config!.max_tokens"
                :min="1"
                controls-position="right"
              />
            </div>
          </div>
        </el-form-item>
        <el-form-item label="标签">
          <el-select
            v-model="createForm.tags"
            multiple
            filterable
            allow-create
            default-first-option
            style="width: 100%"
          >
            <el-option v-for="tag in allTags" :key="tag" :label="tag" :value="tag" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createVisible = false">取消</el-button>
        <el-button type="primary" @click="handleCreate" :loading="createLoading">创建</el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="testVisible"
      :title="`测试运行: ${selectedAgent?.name || ''}`"
      width="760px"
      destroy-on-close
      @closed="handleStopTestRun"
    >
      <el-input
        v-model="testMessage"
        type="textarea"
        :rows="4"
        placeholder="请输入测试消息，例如：分析 000001 今天的走势"
      />
      <div class="test-actions">
        <el-button type="primary" @click="handleTestRun" :loading="testLoading">发送</el-button>
        <el-button @click="handleStopTestRun" :disabled="!testLoading">停止</el-button>
        <el-button @click="clearTestOutput" :disabled="!testEntries.length && !testOutput">清空输出</el-button>
      </div>
      <div class="test-output">
        <template v-if="testEntries.length">
          <template v-if="!hasNonTokenEntries">
            <div class="test-entry test-entry--token">{{ testOutput || '等待输出…' }}</div>
          </template>
          <template v-else>
            <div v-if="testOutput" class="test-entry test-entry--token">
              <div class="test-entry-label">输出</div>
              <div class="test-entry-content">{{ testOutput }}</div>
            </div>
            <div
              v-for="entry in nonTokenEntries"
              :key="entry.id"
              class="test-entry"
              :class="`test-entry--${entry.event}`"
            >
              <div class="test-entry-label">{{ getTestEntryLabel(entry) }}</div>
              <div class="test-entry-content mono">{{ getTestEntryContent(entry) }}</div>
            </div>
          </template>
          <div v-if="testDoneEntry" class="test-entry test-entry--done">
            <div class="test-entry-label">完成</div>
            <div class="test-entry-content mono">{{ testDoneLabel }}</div>
          </div>
        </template>
        <div v-else class="test-output-empty">等待输出…</div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Loading, Plus, Refresh } from '@element-plus/icons-vue'
import { useAuthStore } from '@/stores/auth'
import { agentsApi } from '@/api/agents'
import type { Agent, AgentCreateDto, AgentModelProvider } from '@/api/agents'
import { promptsApi, extractVariables } from '@/api/prompts'
import type { Prompt } from '@/api/prompts'
import { toolsApi } from '@/api/tools'
import type { Tool } from '@/api/tools'

type TestRunEventType = 'token' | 'tool_call' | 'tool_result' | 'error' | 'done'

type TestRunEntry = {
  id: string
  event: TestRunEventType
  payload: Record<string, any>
}

const agents = ref<Agent[]>([])
const selectedAgent = ref<Agent | null>(null)
const selectedPrompt = ref<Prompt | null>(null)
const promptOptions = ref<Prompt[]>([])
const toolMetaMap = ref<Record<string, Tool>>({})
const allTags = ref<string[]>([])
const modelProviders = ref<AgentModelProvider[]>([])

const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const listLoading = ref(false)
const saveLoading = ref(false)
const createLoading = ref(false)
const seedLoading = ref(false)
const testLoading = ref(false)

const editing = ref(false)
const createVisible = ref(false)
const testVisible = ref(false)
const useDefaultModel = ref(true)
const createUseDefaultModel = ref(true)

const searchText = ref('')
const filterTag = ref('')
const filterEnabled = ref<boolean | string>('')
const filterIsChat = ref<boolean | string>('')
const testMessage = ref('')
const testOutput = ref('')
const testEntries = ref<TestRunEntry[]>([])
let testAbortController: AbortController | null = null
let testEntrySeed = 0
let searchTimer: ReturnType<typeof setTimeout>
let agentListRequestSeq = 0

const editForm = reactive({
  name: '',
  description: '',
  prompt_id: '',
  model_config: { provider: '', model: '', temperature: 0.7, max_tokens: 4096 },
  parameters: { max_tool_calls: 10, timeout: 300, retry_on_failure: false },
  tags: [] as string[],
  is_chat: false,
  enabled: true
})
const createForm = reactive<AgentCreateDto>({
  code: '',
  name: '',
  description: '',
  prompt_id: '',
  model_config: { provider: '', model: '', temperature: 0.7, max_tokens: 4096 },
  parameters: { max_tool_calls: 10, timeout: 300, retry_on_failure: false },
  tags: [],
  is_chat: false,
  enabled: true
})

const currentPromptName = computed(() =>
  selectedPrompt.value ? `${selectedPrompt.value.name} v${selectedPrompt.value.version}` : '-'
)

const providerModels = computed(() => {
  const provider = editForm.model_config.provider
  if (!provider) return [] as string[]
  return modelProviders.value.find(p => p.name === provider)?.default_models ?? []
})

const createProviderModels = computed(() => {
  const provider = createForm.model_config?.provider
  if (!provider) return [] as string[]
  return modelProviders.value.find(p => p.name === provider)?.default_models ?? []
})

const createSelectedPrompt = computed(() =>
  promptOptions.value.find(prompt => prompt.id === createForm.prompt_id) || null
)

const promptTextVariables = computed(() => extractVariables(selectedPrompt.value?.blocks ?? []))

const toolInputVariables = computed(() => {
  const names = new Set<string>()
  for (const code of selectedPrompt.value?.bind_tools ?? []) {
    for (const param of toolMetaMap.value[code]?.parameters ?? []) {
      names.add(param.name)
    }
  }
  return Array.from(names).sort()
})

const hasLlmTool = computed(() =>
  (selectedPrompt.value?.bind_tools ?? []).some(code => toolCallsLlm(code))
)
const nonTokenEntries = computed(() =>
  testEntries.value.filter(entry => entry.event !== 'token' && entry.event !== 'done')
)
const hasNonTokenEntries = computed(() => nonTokenEntries.value.length > 0)
const testDoneEntry = computed(() => {
  for (let index = testEntries.value.length - 1; index >= 0; index -= 1) {
    const entry = testEntries.value[index]
    if (entry.event === 'done') return entry
  }
  return null
})
const testDoneLabel = computed(() => {
  const payload = testDoneEntry.value?.payload || {}
  return payload.agent_code || '测试运行完成'
})

function toolCallsLlm(code: string): boolean {
  return Boolean(toolMetaMap.value[code]?.calls_llm)
}

function formatPromptVariable(variable: string): string {
  return `{{${variable}}}`
}

function formatTime(value: string): string {
  if (!value) return '-'
  try {
    return new Date(value).toLocaleString()
  } catch {
    return value
  }
}

async function resolvePromptById(
  promptId: string,
  shouldAssign: () => boolean = () => editForm.prompt_id === promptId
) {
  if (!promptId) {
    selectedPrompt.value = null
    return
  }

  const promptFromOptions = promptOptions.value.find(prompt => prompt.id === promptId) || null
  if (promptFromOptions) {
    selectedPrompt.value = promptFromOptions
    return
  }

  selectedPrompt.value = null
  try {
    const res = await promptsApi.get(promptId)
    if (res.success && shouldAssign()) {
      selectedPrompt.value = res.data
    }
  } catch (err) {
    console.warn('Failed to load prompt', err)
  }
}

async function resolveAgentPrompt(agent: Agent) {
  if (selectedPrompt.value?.id === agent.prompt_id) return

  await resolvePromptById(
    agent.prompt_id,
    () => selectedAgent.value?.id === agent.id && selectedAgent.value.prompt_id === agent.prompt_id
  )
}

async function loadAgents(reset = true) {
  if (!reset && listLoading.value) return

  const nextPage = reset ? 1 : page.value + 1
  const requestSeq = ++agentListRequestSeq
  listLoading.value = true
  try {
    const res = await agentsApi.list({
      search: searchText.value || undefined,
      tag: filterTag.value || undefined,
      enabled: filterEnabled.value === '' ? undefined : Boolean(filterEnabled.value),
      is_chat: filterIsChat.value === '' ? undefined : Boolean(filterIsChat.value),
      page: nextPage,
      page_size: pageSize.value
    })
    if (!res.success || requestSeq !== agentListRequestSeq) return

    const previousSelectionId = selectedAgent.value?.id || null
    page.value = res.data.page
    total.value = res.data.total

    if (reset) {
      agents.value = res.data.items
    } else {
      const agentMap = new Map<string, Agent>()
      for (const agent of agents.value) {
        agentMap.set(agent.id, agent)
      }
      for (const agent of res.data.items) {
        agentMap.set(agent.id, agent)
      }
      agents.value = Array.from(agentMap.values())
    }

    const matchedSelectedAgent = previousSelectionId
      ? agents.value.find(agent => agent.id === previousSelectionId) || null
      : null

    if (matchedSelectedAgent) {
      selectedAgent.value = matchedSelectedAgent
      if (!editing.value) {
        fillEditForm(matchedSelectedAgent)
      }
      await resolveAgentPrompt(matchedSelectedAgent)
    } else if (selectedAgent.value && reset) {
      selectedAgent.value = null
      selectedPrompt.value = null
    }

    if (!selectedAgent.value && agents.value.length > 0) {
      await selectAgent(agents.value[0])
    }
  } catch (err: any) {
    if (requestSeq === agentListRequestSeq) {
      ElMessage.error(err?.response?.data?.detail || '加载 Agent 列表失败')
    }
  } finally {
    if (requestSeq === agentListRequestSeq) {
      listLoading.value = false
    }
  }
}
async function loadPrompts() {
  const res = await promptsApi.list({ enabled: true, page: 1, page_size: 100 })
  if (res.success) promptOptions.value = res.data.items
}

async function loadTags() {
  const res = await agentsApi.getTags()
  if (res.success) allTags.value = res.data
}

async function loadModelProviders() {
  try {
    const res = await agentsApi.getModels()
    if (res.success) modelProviders.value = res.data
  } catch (err) {
    console.warn('Failed to load model providers', err)
  }
}

async function loadToolMeta() {
  const res = await toolsApi.list({ page: 1, page_size: 100 })
  if (res.success) {
    const map: Record<string, Tool> = {}
    for (const tool of res.data.items) {
      map[tool.code] = tool
    }
    toolMetaMap.value = map
  }
}

async function selectAgent(agent: Agent) {
  if (editing.value) cancelEdit()
  selectedAgent.value = agent
  fillEditForm(agent)
  await resolveAgentPrompt(agent)
}

function fillEditForm(agent: Agent) {
  editForm.name = agent.name
  editForm.description = agent.description
  editForm.prompt_id = agent.prompt_id
  editForm.parameters = { ...agent.parameters }
  editForm.tags = [...agent.tags]
  editForm.is_chat = agent.is_chat
  editForm.enabled = agent.enabled
  useDefaultModel.value = !agent.model_config
  editForm.model_config = agent.model_config
    ? {
        provider: agent.model_config.provider || '',
        model: agent.model_config.model || '',
        temperature: agent.model_config.temperature ?? 0.7,
        max_tokens: agent.model_config.max_tokens ?? 4096
      }
    : { provider: '', model: '', temperature: 0.7, max_tokens: 4096 }
}
function handleSearch() {
  clearTimeout(searchTimer)
  searchTimer = setTimeout(() => loadAgents(true), 300)
}

function startEdit() {
  if (!selectedAgent.value) return
  fillEditForm(selectedAgent.value)
  editing.value = true
}

function cancelEdit() {
  editing.value = false
  if (selectedAgent.value) fillEditForm(selectedAgent.value)
}

function resetCreateModelConfig() {
  createForm.model_config = { provider: '', model: '', temperature: 0.7, max_tokens: 4096 }
}

function resetCreateParameters() {
  createForm.parameters = { max_tool_calls: 10, timeout: 300, retry_on_failure: false }
}

function showCreateDialog() {
  createForm.code = ''
  createForm.name = ''
  createForm.description = ''
  createForm.prompt_id = ''
  createForm.tags = []
  createForm.is_chat = false
  createForm.enabled = true
  createUseDefaultModel.value = true
  resetCreateModelConfig()
  resetCreateParameters()
  createVisible.value = true
}

function onProviderChange() {
  editForm.model_config.model = ''
}

function onCreateProviderChange() {
  if (createForm.model_config) {
    createForm.model_config.model = ''
  }
}

function openPromptDetail(prompt: Prompt | null = selectedPrompt.value) {
  if (!prompt?.id) return
  window.open(`/prompts?prompt_id=${encodeURIComponent(prompt.id)}`, '_blank')
}

async function handleCreate() {
  if (!createForm.code || !createForm.name || !createForm.prompt_id) {
    ElMessage.warning('请填写编码、名称和提示词')
    return
  }
  createLoading.value = true
  try {
    const payload: AgentCreateDto = {
      ...createForm,
      model_config: createUseDefaultModel.value ? null : createForm.model_config
    }
    const res = await agentsApi.create(payload)
    if (res.success) {
      ElMessage.success('创建成功')
      createVisible.value = false
      await loadAgents(true)
      await loadTags()
      await selectAgent(res.data)
    }
  } catch (err: any) {
    ElMessage.error(err?.response?.data?.detail || '创建失败')
  } finally {
    createLoading.value = false
  }
}
async function handleSave() {
  if (!selectedAgent.value) return
  saveLoading.value = true
  try {
    const res = await agentsApi.update(selectedAgent.value.id, {
      name: editForm.name,
      description: editForm.description,
      prompt_id: editForm.prompt_id,
      model_config: useDefaultModel.value ? null : editForm.model_config,
      parameters: editForm.parameters,
      tags: editForm.tags,
      is_chat: editForm.is_chat,
      enabled: editForm.enabled
    })
    if (res.success) {
      ElMessage.success('保存成功')
      selectedAgent.value = res.data
      fillEditForm(res.data)
      editing.value = false
      await loadAgents(true)
      await loadTags()
    }
  } catch (err: any) {
    ElMessage.error(err?.response?.data?.detail || '保存失败')
  } finally {
    saveLoading.value = false
  }
}

async function handleToggle(agent: Agent, enabled: boolean) {
  try {
    const res = await agentsApi.toggle(agent.id, enabled)
    if (res.success) agent.enabled = enabled
  } catch (err: any) {
    ElMessage.error(err?.response?.data?.detail || '操作失败')
  }
}

async function handleDelete() {
  if (!selectedAgent.value) return
  try {
    await ElMessageBox.confirm(`确认删除 Agent「${selectedAgent.value.name}」？`, '删除确认', {
      type: 'warning'
    })
    await agentsApi.remove(selectedAgent.value.id)
    ElMessage.success('删除成功')
    selectedAgent.value = null
    selectedPrompt.value = null
    await loadAgents(true)
  } catch (err: any) {
    if (err === 'cancel' || err === 'close') return
    ElMessage.error(err?.response?.data?.detail || '删除失败')
  }
}
async function handleSeed() {
  seedLoading.value = true
  try {
    const res = await agentsApi.seed()
    if (res.success) {
      const { created, skipped, failed } = res.data
      const summary = `创建 ${created} 个，跳过 ${skipped} 个`
      if (failed && failed.length > 0) {
        ElMessage.warning(`${summary}，失败 ${failed.length} 个`)
      } else {
        ElMessage.success(summary)
      }
      await loadAgents(true)
      await loadTags()
    }
  } catch (err: any) {
    ElMessage.error(err?.response?.data?.detail || '初始化失败')
  } finally {
    seedLoading.value = false
  }
}

function pushTestEntry(event: TestRunEventType, payload: Record<string, any>) {
  testEntrySeed += 1
  testEntries.value.push({
    id: `test-entry-${testEntrySeed}`,
    event,
    payload
  })
}

function clearTestOutput() {
  testOutput.value = ''
  testEntries.value = []
}

function handleStopTestRun() {
  const controller = testAbortController
  if (controller) {
    controller.abort()
    if (testAbortController === controller) {
      testAbortController = null
    }
  }
  testLoading.value = false
}

function applyTestRunEvent(event: TestRunEventType, payload: Record<string, any>) {
  if (event === 'token') {
    const content = payload.content || payload.token || ''
    if (content) {
      testOutput.value += content
      pushTestEntry('token', { content })
    }
    return
  }

  pushTestEntry(event, payload)

  if (event === 'error' && payload.message) {
    ElMessage.error(payload.message)
  }
}

function parseSseBuffer(buffer: string): { remaining: string; events: Array<{ event: TestRunEventType; payload: Record<string, any> }> } {
  const events: Array<{ event: TestRunEventType; payload: Record<string, any> }> = []
  const normalized = buffer.replace(/\r\n/g, '\n')
  const blocks = normalized.split('\n\n')
  const remaining = blocks.pop() ?? ''

  for (const block of blocks) {
    const lines = block.split('\n')
    let event = ''
    const dataLines: string[] = []

    for (const line of lines) {
      if (line.startsWith('event:')) {
        event = line.slice(6).trim()
        continue
      }
      if (line.startsWith('data:')) {
        dataLines.push(line.slice(5).trim())
      }
    }

    if (!event || dataLines.length === 0) continue
    if (!['token', 'tool_call', 'tool_result', 'error', 'done'].includes(event)) continue

    try {
      events.push({
        event: event as TestRunEventType,
        payload: JSON.parse(dataLines.join('\n'))
      })
    } catch {
      continue
    }
  }

  return { remaining, events }
}

function getTestEntryLabel(entry: TestRunEntry): string {
  switch (entry.event) {
    case 'tool_call':
      return '工具调用'
    case 'tool_result':
      return '工具结果'
    case 'error':
      return '错误'
    case 'done':
      return '完成'
    default:
      return '输出'
  }
}

function getTestEntryContent(entry: TestRunEntry): string {
  const payload = entry.payload || {}
  switch (entry.event) {
    case 'tool_call':
      return `${payload.name || 'unknown'}(${JSON.stringify(payload.args || {}, null, 2)})`
    case 'tool_result':
      return `${payload.name || 'unknown'}\n${payload.content || ''}`
    case 'error':
      return payload.message || '测试运行失败'
    case 'done':
      return payload.agent_code || '测试运行完成'
    case 'token':
    default:
      return payload.content || ''
  }
}

function showTestDialog() {
  handleStopTestRun()
  testMessage.value = ''
  clearTestOutput()
  testVisible.value = true
}

async function handleTestRun() {
  if (!selectedAgent.value || !testMessage.value.trim()) return
  handleStopTestRun()
  testLoading.value = true
  clearTestOutput()
  const controller = new AbortController()
  testAbortController = controller
  try {
    const authStore = useAuthStore()
    const token = authStore.token || localStorage.getItem('auth-token') || ''
    const response = await fetch(`/api/agents/${selectedAgent.value.id}/test-run`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {})
      },
      body: JSON.stringify({ message: testMessage.value, variables: {} }),
      signal: controller.signal
    })
    if (!response.ok) throw new Error(`HTTP ${response.status}`)
    const reader = response.body?.getReader()
    if (!reader) throw new Error('当前浏览器不支持流式响应')
    const decoder = new TextDecoder()
    let buffer = ''
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const parsed = parseSseBuffer(buffer)
      buffer = parsed.remaining
      for (const event of parsed.events) {
        applyTestRunEvent(event.event, event.payload)
      }
    }

    buffer += decoder.decode()
    const parsed = parseSseBuffer(buffer)
    for (const event of parsed.events) {
      applyTestRunEvent(event.event, event.payload)
    }
  } catch (err: any) {
    if (err?.name !== 'AbortError') {
      ElMessage.error(err?.message || '测试运行失败')
    }
  } finally {
    if (testAbortController === controller) {
      testAbortController = null
      testLoading.value = false
    }
  }
}
watch(
  () => editForm.prompt_id,
  (promptId) => {
    void resolvePromptById(promptId)
  }
)

onBeforeUnmount(() => {
  handleStopTestRun()
})

onMounted(async () => {
  await Promise.all([loadPrompts(), loadTags(), loadModelProviders(), loadToolMeta()])
  await loadAgents(true)
})
</script>

<style scoped>
.agent-management {
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
}
.page-header h2 {
  margin: 0;
}
.header-actions,
.filter-row,
.detail-badges {
  display: flex;
  gap: 8px;
  align-items: center;
}
.filter-section {
  margin-bottom: 12px;
}
.filter-section .el-input,
.filter-row {
  margin-bottom: 8px;
}
.filter-row .el-select {
  flex: 1;
}
.agent-list {
  max-height: calc(100vh - 390px);
}
.agent-item {
  padding: 10px 12px;
  border-radius: 6px;
  cursor: pointer;
  margin-bottom: 4px;
  border: 1px solid transparent;
  transition: all 0.2s;
}
.agent-item:hover {
  background: var(--el-fill-color-light);
}
.agent-item.active {
  background: var(--el-color-primary-light-9);
  border-color: var(--el-color-primary-light-7);
}
.agent-item-header,
.detail-title-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.agent-name {
  font-weight: 500;
  font-size: 13px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.agent-item-meta,
.agent-item-tags {
  display: flex;
  gap: 4px;
  margin-top: 4px;
  flex-wrap: wrap;
}
.agent-code {
  margin-top: 4px;
  color: var(--el-text-color-secondary);
}
.mini-tag {
  margin-right: 2px;
}
.list-loading,
.list-end {
  text-align: center;
  padding: 12px;
  color: var(--el-text-color-secondary);
  font-size: 13px;
}
.list-end {
  color: var(--el-text-color-placeholder);
  font-size: 12px;
}
.detail-panel {
  background: var(--el-bg-color);
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 8px;
  padding: 20px;
  height: 100%;
  display: flex;
  flex-direction: column;
}
.detail-header {
  margin-bottom: 20px;
}
.detail-title-row h3 {
  margin: 0;
}
.edit-name-input {
  max-width: 300px;
}
.detail-body {
  max-height: calc(100vh - 420px);
  overflow: auto;
}
.section {
  margin-bottom: 20px;
}
.section > h4, .section-title-row {
  margin: 0 0 12px 0;
  font-size: 14px;
  color: var(--el-text-color-secondary);
  border-bottom: 1px solid var(--el-border-color-lighter);
  padding-bottom: 6px;
}
.section-title-row h4 {
  font-size: 14px;
  color: var(--el-text-color-secondary);
}
.mono {
  font-family: monospace;
  font-size: 13px;
}
.text-muted {
  color: var(--el-text-color-placeholder);
  font-size: 13px;
}
.tag-chip {
  margin-right: 6px;
  margin-bottom: 4px;
}
.model-grid {
  display: grid;
  grid-template-columns: 1fr 1fr 160px 160px;
  gap: 8px;
  margin-top: 12px;
}
.model-summary {
  font-size: 13px;
  color: var(--el-text-color-regular);
}
.detail-footer {
  margin-top: 20px;
  padding-top: 16px;
  border-top: 1px solid var(--el-border-color-lighter);
  display: flex;
  gap: 8px;
  justify-content: flex-end;
}
.test-actions {
  margin: 12px 0;
  display: flex;
  gap: 8px;
}
.test-output {
  min-height: 180px;
  max-height: 400px;
  padding: 12px;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 6px;
  white-space: pre-wrap;
  background: var(--el-bg-color-page);
  font-size: 12px;
  overflow: auto;
}
.test-entry {
  margin-bottom: 8px;
  padding: 8px;
  border-radius: 4px;
  background: var(--el-fill-color-light);
}
.test-entry--token {
  white-space: pre-wrap;
}
.test-entry--tool_call {
  border-left: 3px solid var(--el-color-warning);
}
.test-entry--tool_result {
  border-left: 3px solid var(--el-color-success);
}
.test-entry--error {
  border-left: 3px solid var(--el-color-danger);
  color: var(--el-color-danger);
}
.test-entry--done {
  border-left: 3px solid var(--el-color-primary);
  color: var(--el-color-primary);
}
.test-entry-label {
  font-weight: 600;
  font-size: 12px;
  margin-bottom: 4px;
}
.test-entry-content {
  font-size: 12px;
}
.test-output-empty {
  color: var(--el-text-color-placeholder);
  text-align: center;
  padding: 40px;
}
.prompt-select-row {
  display: flex;
  width: 100%;
  align-items: center;
  gap: 8px;
}
.create-model-section {
  display: flex;
  flex-direction: column;
  width: 100%;
  gap: 12px;
}
.variables-overview {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.variables-group {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.variables-group-title {
  font-size: 13px;
  font-weight: 500;
  color: var(--el-text-color-regular);
}
.variable-chip-list {
  display: flex;
  flex-wrap: wrap;
}
.ml-4 {
  margin-left: 4px;
}
.mt-8 {
  margin-top: 8px;
}
.flex-1 {
  flex: 1;
}
</style>
