<script setup lang="ts">
import type { DerivedVariablesResult, Prompt, PromptBlock, PromptCreateDto, PromptType, RenderResult } from '@/api/prompts'
import type { Tool } from '@/api/tools'
import { Loading, Plus, Refresh } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import Sortable from 'sortablejs'
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { extractVariables, promptsApi } from '@/api/prompts'
import { toolsApi } from '@/api/tools'

const route = useRoute()

const prompts = ref<Prompt[]>([])
const total = ref(0)
const currentPage = ref(1)
const pageSize = 20
const listLoading = ref(false)
const listScrollbar = ref()
const allTags = ref<string[]>([])
const selectedPrompt = ref<Prompt | null>(null)
const editing = ref(false)
const pendingRoutePromptId = ref('')

const searchText = ref('')
const filterType = ref<PromptType | ''>('')
const filterTag = ref('')
const filterEnabled = ref<boolean | string>('')

const seedLoading = ref(false)
const saveLoading = ref(false)
const createLoading = ref(false)
const versionsLoading = ref(false)
const renderLoading = ref(false)

const versions = ref<Prompt[]>([])
const versionCollapseNames = ref<string[]>([])
const blocksContainer = ref<HTMLElement>()
let sortableInstance: Sortable | null = null
const blockInputRefs = ref<Record<number, any>>({})
const focusedBlockIndex = ref<number | null>(null)

const editForm = reactive({
  name: '',
  description: '',
  prompt_type: 'workflow' as PromptType,
  blocks: [] as PromptBlock[],
  bind_tools: [] as string[],
  tags: [] as string[],
  enabled: true
})

const createVisible = ref(false)
const createForm = reactive<PromptCreateDto>({
  code: '',
  name: '',
  description: '',
  prompt_type: 'workflow',
  blocks: [],
  bind_tools: [],
  tags: [],
  enabled: true
})

const toolSelectValue = ref('')
const toolSearchQuery = ref('')
const allTools = ref<Tool[]>([])
const filteredToolOptions = ref<Tool[]>([])
const derivedVariables = ref<DerivedVariablesResult>({ tool_params: [], tool_outputs: [] })

const renderVisible = ref(false)
const renderVariablesText = ref('{}')
const renderResult = ref<RenderResult | null>(null)

const displayBlocks = computed(() => editing.value ? editForm.blocks : selectedPrompt.value?.blocks ?? [])
const blockKeys = computed(() => displayBlocks.value.map((block, index) => `${index}-${block.type}-${block.label}`))
const manualVariables = computed(() => extractVariables(editForm.blocks))

function promptTypeTag(type: string) {
  return type === 'chat' ? 'success' : 'primary'
}

function toolTypeTag(type: string) {
  if (type === 'builtin')
    return 'success'
  if (type === 'rpc')
    return 'warning'
  return 'primary'
}

function variableTemplate(name: string) {
  return `{{${name}}}`
}

function getRoutePromptId(): string {
  const value = route.query.prompt_id
  return typeof value === 'string' ? value.trim() : ''
}

async function syncPromptSelectionFromRoute() {
  const promptId = pendingRoutePromptId.value || getRoutePromptId()
  if (!promptId)
    return

  const existing = prompts.value.find(prompt => prompt.id === promptId)
  if (existing) {
    pendingRoutePromptId.value = ''
    selectPrompt(existing)
    return
  }

  try {
    const res = await promptsApi.get(promptId)
    if (!res.success)
      return
    const prompt = res.data
    if (!prompts.value.some(item => item.id === prompt.id)) {
      prompts.value = [prompt, ...prompts.value]
      total.value = Math.max(total.value, prompts.value.length)
    }
    pendingRoutePromptId.value = ''
    selectPrompt(prompt)
  } catch {
    // ignore invalid route prompt id
  }
}

async function loadPrompts(append = false) {
  if (listLoading.value)
    return
  if (!append)
    currentPage.value = 1
  listLoading.value = true
  try {
    const res = await promptsApi.list({
      search: searchText.value || undefined,
      prompt_type: filterType.value || undefined,
      tag: filterTag.value || undefined,
      enabled: filterEnabled.value === '' ? undefined : Boolean(filterEnabled.value),
      page: currentPage.value,
      page_size: pageSize
    })
    if (res.success) {
      prompts.value = append ? [...prompts.value, ...res.data.items] : res.data.items
      total.value = res.data.total
      if (getRoutePromptId()) {
        pendingRoutePromptId.value = getRoutePromptId()
        await syncPromptSelectionFromRoute()
      } else if (!selectedPrompt.value && prompts.value.length > 0) {
        selectPrompt(prompts.value[0])
      }
    }
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '加载提示词列表失败')
  } finally {
    listLoading.value = false
  }
}

async function loadTags() {
  try {
    const res = await promptsApi.getAllTags()
    if (res.success)
      allTags.value = res.data
  } catch { /* ignore */ }
}

function onListScroll() {
  const wrap = listScrollbar.value?.wrapRef
  if (!wrap || listLoading.value || prompts.value.length >= total.value)
    return
  const distanceToBottom = wrap.scrollHeight - wrap.scrollTop - wrap.clientHeight
  if (distanceToBottom < 50) {
    currentPage.value++
    loadPrompts(true)
  }
}

let searchTimer: ReturnType<typeof setTimeout>
function handleSearch() {
  clearTimeout(searchTimer)
  searchTimer = setTimeout(() => loadPrompts(), 300)
}

function selectPrompt(prompt: Prompt) {
  if (editing.value)
    cancelEdit()
  selectedPrompt.value = prompt
  loadVersions()
  fillEditForm(prompt)
  deriveVariables()
}

function selectVersion(prompt: Prompt) {
  selectedPrompt.value = prompt
  fillEditForm(prompt)
  deriveVariables()
  startEdit()
}

function fillEditForm(prompt: Prompt) {
  editForm.name = prompt.name
  editForm.description = prompt.description
  editForm.prompt_type = prompt.prompt_type
  editForm.blocks = prompt.blocks.map(block => ({ ...block }))
  editForm.bind_tools = [...prompt.bind_tools]
  editForm.tags = [...prompt.tags]
  editForm.enabled = prompt.enabled
}

function startEdit() {
  if (!selectedPrompt.value)
    return
  fillEditForm(selectedPrompt.value)
  editing.value = true
  nextTick(initSortable)
}

function cancelEdit() {
  editing.value = false
  destroySortable()
  if (selectedPrompt.value)
    fillEditForm(selectedPrompt.value)
}

function setBlockInputRef(el: any, index: number) {
  if (el)
    blockInputRefs.value[index] = el
}

function initSortable() {
  destroySortable()
  if (!blocksContainer.value || !editing.value)
    return
  sortableInstance = Sortable.create(blocksContainer.value, {
    handle: '.drag-handle',
    animation: 150,
    ghostClass: 'sortable-ghost',
    onEnd(event) {
      const oldIndex = event.oldIndex
      const newIndex = event.newIndex
      if (oldIndex === undefined || newIndex === undefined || oldIndex === newIndex)
        return
      const moved = editForm.blocks.splice(oldIndex, 1)[0]
      editForm.blocks.splice(newIndex, 0, moved)
    }
  })
}

function destroySortable() {
  if (sortableInstance) {
    sortableInstance.destroy()
    sortableInstance = null
  }
}

function addTextBlock() {
  editForm.blocks.push({ type: 'text', label: '文本块', content: '' })
  handleBlocksChanged()
  nextTick(initSortable)
}

function addPlaceholderBlock() {
  editForm.blocks.push({ type: 'messages_placeholder', label: '对话历史' })
  nextTick(initSortable)
}

function removeBlock(index: number) {
  editForm.blocks.splice(index, 1)
  handleBlocksChanged()
  nextTick(initSortable)
}

function handleBlocksChanged() {
  // manualVariables is computed from editForm.blocks.
}

async function handleToggle(prompt: Prompt, enabled: boolean) {
  try {
    const res = await promptsApi.toggle(prompt.id, enabled)
    if (res.success) {
      prompt.enabled = enabled
      if (selectedPrompt.value?.id === prompt.id)
        selectedPrompt.value.enabled = enabled
      ElMessage.success('状态更新成功')
    }
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '操作失败')
  }
}

async function handleSave() {
  if (!selectedPrompt.value)
    return
  saveLoading.value = true
  try {
    const res = await promptsApi.update(selectedPrompt.value.id, buildUpdatePayload())
    if (res.success) {
      ElMessage.success('更新成功')
      editing.value = false
      destroySortable()
      selectedPrompt.value = res.data
      await loadPrompts()
      await loadVersions()
      await loadTags()
    }
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '更新失败')
  } finally {
    saveLoading.value = false
  }
}

async function handleSaveNewVersion() {
  if (!selectedPrompt.value)
    return
  saveLoading.value = true
  try {
    const res = await promptsApi.saveNewVersion(selectedPrompt.value.id, buildUpdatePayload())
    if (res.success) {
      ElMessage.success('新版本已保存')
      editing.value = false
      destroySortable()
      selectedPrompt.value = res.data
      await loadPrompts()
      await loadVersions()
      await loadTags()
    }
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '保存新版本失败')
  } finally {
    saveLoading.value = false
  }
}

function buildUpdatePayload() {
  return {
    name: editForm.name,
    description: editForm.description,
    prompt_type: editForm.prompt_type,
    blocks: editForm.blocks,
    bind_tools: editForm.bind_tools,
    tags: editForm.tags,
    enabled: editForm.enabled
  }
}

async function loadVersions() {
  if (!selectedPrompt.value)
    return
  versionsLoading.value = true
  try {
    const res = await promptsApi.getVersions(selectedPrompt.value.code)
    if (res.success)
      versions.value = res.data
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '加载版本失败')
  } finally {
    versionsLoading.value = false
  }
}

async function handleActivate(prompt: Prompt) {
  try {
    const res = await promptsApi.activate(prompt.id)
    if (res.success) {
      ElMessage.success('版本已激活')
      selectedPrompt.value = res.data
      fillEditForm(res.data)
      await loadPrompts()
      await loadVersions()
    }
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '激活失败')
  }
}

async function handleDeleteVersion(prompt: Prompt) {
  try {
    await ElMessageBox.confirm(`确定删除提示词版本 v${prompt.version} 吗？`, '删除确认', { type: 'warning' })
    const res = await promptsApi.remove(prompt.id)
    if (res.success) {
      ElMessage.success('删除成功')
      if (selectedPrompt.value?.id === prompt.id)
        selectedPrompt.value = null
      await loadPrompts()
      await loadVersions()
    }
  } catch (e: any) {
    if (e !== 'cancel')
      ElMessage.error(e?.response?.data?.detail || '删除失败')
  }
}

async function handleDeletePrompt(prompt: Prompt) {
  try {
    await ElMessageBox.confirm(`确定删除提示词 "${prompt.name}" 的所有版本吗？`, '删除确认', { type: 'warning' })
    const res = await promptsApi.removeByCode(prompt.code)
    if (res.success) {
      ElMessage.success('提示词已删除')
      selectedPrompt.value = null
      versions.value = []
      await loadPrompts()
      await loadTags()
    }
  } catch (e: any) {
    if (e !== 'cancel')
      ElMessage.error(e?.response?.data?.detail || '删除失败')
  }
}

function showCreateDialog() {
  createForm.code = ''
  createForm.name = ''
  createForm.description = ''
  createForm.prompt_type = 'workflow'
  createForm.blocks = [
    { type: 'text', label: '系统角色', content: '' },
    { type: 'messages_placeholder', label: '对话历史' }
  ]
  createForm.bind_tools = []
  createForm.tags = []
  createForm.enabled = true
  createVisible.value = true
}

async function handleCreate() {
  if (!createForm.code || !createForm.name) {
    ElMessage.warning('请填写编码和名称')
    return
  }
  createLoading.value = true
  try {
    const res = await promptsApi.create(createForm)
    if (res.success) {
      ElMessage.success('创建成功')
      createVisible.value = false
      selectedPrompt.value = res.data
      await loadPrompts()
      await loadTags()
      selectPrompt(res.data)
    }
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '创建失败')
  } finally {
    createLoading.value = false
  }
}

async function handleSeed() {
  seedLoading.value = true
  try {
    const res = await promptsApi.seed()
    if (res.success) {
      ElMessage.success(`初始化完成: 新增${res.data.created} 跳过${res.data.skipped}`)
      await loadPrompts()
      await loadTags()
    }
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '初始化失败')
  } finally {
    seedLoading.value = false
  }
}

async function loadAllTools() {
  try {
    const res = await toolsApi.list({ page: 1, page_size: 100 })
    if (res.success) {
      allTools.value = res.data.items
      filterTools(toolSearchQuery.value)
    }
  } catch { /* ignore */ }
}

function filterTools(query = '') {
  toolSearchQuery.value = query.trim()
  if (!toolSearchQuery.value) {
    filteredToolOptions.value = allTools.value
    return
  }
  const keyword = toolSearchQuery.value.toLowerCase()
  filteredToolOptions.value = allTools.value.filter(tool => getToolSearchTexts(tool).some(text => text.toLowerCase().includes(keyword)))
}

function handleToolSelectVisible(visible: boolean) {
  if (visible && allTools.value.length === 0)
    loadAllTools()
}

function handleToolSelectChange(toolName: string) {
  if (!toolName)
    return
  bindTool(toolName)
  toolSelectValue.value = ''
  filterTools(toolSearchQuery.value)
}

function bindTool(toolCode: string) {
  if (!editForm.bind_tools.includes(toolCode)) {
    editForm.bind_tools.push(toolCode)
    deriveVariables()
  }
}

function removeBoundTool(toolCode: string) {
  editForm.bind_tools = editForm.bind_tools.filter(code => code !== toolCode)
  filterTools(toolSearchQuery.value)
  deriveVariables()
}

function getToolName(code: string): string {
  const tool = allTools.value.find(t => t.code === code)
  return tool ? tool.name : code
}

function getToolSearchTexts(tool: Tool): string[] {
  const outputSchema = tool.output_schema || {}
  const outputProperties = outputSchema.properties || {}
  const outputTexts = Object.entries(outputProperties).flatMap(([name, info]: [string, any]) => [name, info?.description || '', info?.type || ''])
  const parameterTexts = (tool.parameters || []).flatMap(param => [param.name, param.type, param.description || '', String(param.default ?? '')])
  return [
    tool.code,
    tool.name,
    tool.description || '',
    tool.type,
    tool.handler || '',
    tool.endpoint_url || '',
    ...(tool.tags || []),
    ...parameterTexts,
    ...outputTexts
  ].filter(Boolean)
}

function getToolMatchText(tool: Tool): string {
  if (!toolSearchQuery.value)
    return ''
  const keyword = toolSearchQuery.value.toLowerCase()
  return getToolSearchTexts(tool).find(text => text.toLowerCase().includes(keyword)) || ''
}

function escapeHtml(value: string): string {
  return value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}

function escapeRegExp(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

function highlightMatch(value: string): string {
  const escaped = escapeHtml(String(value || ''))
  if (!toolSearchQuery.value)
    return escaped
  const pattern = new RegExp(`(${escapeRegExp(toolSearchQuery.value)})`, 'gi')
  return escaped.replace(pattern, '<mark class="tool-match-highlight">$1</mark>')
}

async function deriveVariables() {
  if (editForm.bind_tools.length === 0) {
    derivedVariables.value = { tool_params: [], tool_outputs: [] }
    return
  }
  try {
    const res = await promptsApi.deriveVariables(editForm.bind_tools)
    if (res.success)
      derivedVariables.value = res.data
  } catch {
    derivedVariables.value = { tool_params: [], tool_outputs: [] }
  }
}

async function insertVariable(name: string) {
  if (!editing.value)
    return
  const index = focusedBlockIndex.value ?? editForm.blocks.findIndex(block => block.type === 'text')
  if (index < 0)
    return
  const block = editForm.blocks[index]
  if (block.type !== 'text')
    return
  const token = variableTemplate(name)
  const input = blockInputRefs.value[index]?.textarea as HTMLTextAreaElement | undefined
  const content = block.content || ''
  if (input) {
    const start = input.selectionStart ?? content.length
    const end = input.selectionEnd ?? content.length
    block.content = `${content.slice(0, start)}${token}${content.slice(end)}`
    await nextTick()
    input.focus()
    input.setSelectionRange(start + token.length, start + token.length)
  } else {
    block.content = `${content}${token}`
  }
}

function showRenderDialog() {
  renderVariablesText.value = '{}'
  renderResult.value = null
  renderVisible.value = true
}

async function handleRender() {
  if (!selectedPrompt.value)
    return
  renderLoading.value = true
  try {
    const variables = renderVariablesText.value.trim() ? JSON.parse(renderVariablesText.value) : {}
    const res = await promptsApi.render(selectedPrompt.value.id, { variables })
    if (res.success)
      renderResult.value = res.data
  } catch (e: any) {
    ElMessage.error(e instanceof SyntaxError ? '变量 JSON 格式错误' : e?.response?.data?.detail || '渲染失败')
  } finally {
    renderLoading.value = false
  }
}

watch(() => editForm.bind_tools, deriveVariables, { deep: true })
watch(
  () => route.query.prompt_id,
  async () => {
    pendingRoutePromptId.value = getRoutePromptId()
    if (pendingRoutePromptId.value) {
      await syncPromptSelectionFromRoute()
    }
  }
)

onMounted(() => {
  pendingRoutePromptId.value = getRoutePromptId()
  loadPrompts()
  loadTags()
  loadAllTools()
})

onBeforeUnmount(() => {
  destroySortable()
})
</script>

<template>
  <div class="prompt-management">
    <div class="page-header">
      <h2>提示词管理</h2>
      <div class="header-actions">
        <el-button type="primary" @click="showCreateDialog">
          <el-icon><Plus /></el-icon> 新建
        </el-button>
        <el-button :loading="seedLoading" @click="handleSeed">
          <el-icon><Refresh /></el-icon> 初始化 Seed
        </el-button>
      </div>
    </div>

    <el-row :gutter="20" class="flex-1">
      <el-col :span="7">
        <div class="filter-section">
          <el-input
            v-model="searchText"
            placeholder="搜索提示词..."
            prefix-icon="Search"
            clearable
            @input="handleSearch"
          />
          <div class="filter-row">
            <el-select v-model="filterType" placeholder="类型" clearable @change="loadPrompts()">
              <el-option label="workflow" value="workflow" />
              <el-option label="chat" value="chat" />
            </el-select>
            <el-select v-model="filterTag" placeholder="标签" clearable @change="loadPrompts()">
              <el-option v-for="tag in allTags" :key="tag" :label="tag" :value="tag" />
            </el-select>
          </div>
          <div class="filter-row">
            <el-select v-model="filterEnabled" placeholder="状态" clearable @change="loadPrompts()">
              <el-option label="已启用" :value="true" />
              <el-option label="已禁用" :value="false" />
            </el-select>
          </div>
        </div>

        <el-scrollbar ref="listScrollbar" class="prompt-list" @scroll="onListScroll">
          <div
            v-for="prompt in prompts"
            :key="prompt.id"
            class="prompt-item"
            :class="{ active: selectedPrompt?.id === prompt.id }"
            @click="selectPrompt(prompt)"
          >
            <div class="prompt-item-header">
              <span class="prompt-name">{{ prompt.name }}</span>
              <el-switch
                :model-value="prompt.enabled"
                size="small"
                @click.stop
                @change="(val: any) => handleToggle(prompt, !!val)"
              />
            </div>
            <div class="prompt-item-meta">
              <el-tag size="small" :type="promptTypeTag(prompt.prompt_type)">
                {{ prompt.prompt_type }}
              </el-tag>
              <el-tag size="small" type="success">
                v{{ prompt.version }}
              </el-tag>
              <el-tag v-if="prompt.is_system" size="small" type="info">
                系统
              </el-tag>
              <el-tag v-if="prompt.is_active" size="small" type="primary">
                当前
              </el-tag>
            </div>
            <div class="prompt-code mono">
              {{ prompt.code }}
            </div>
            <div class="prompt-item-tags">
              <el-tag v-for="tag in prompt.tags.slice(0, 3)" :key="tag" size="small" type="info" class="mini-tag">
                {{ tag }}
              </el-tag>
            </div>
          </div>
          <el-empty v-if="prompts.length === 0 && !listLoading" description="暂无提示词" />
          <div v-if="listLoading" class="list-loading">
            <el-icon class="is-loading">
              <Loading />
            </el-icon> 加载中...
          </div>
          <div v-if="!listLoading && prompts.length > 0 && prompts.length >= total" class="list-end">
            已加载全部 {{ total }} 个提示词
          </div>
        </el-scrollbar>
      </el-col>

      <el-col :span="17">
        <div v-if="selectedPrompt" class="detail-panel">
          <div class="detail-header">
            <div class="detail-title-row">
              <el-input v-if="editing" v-model="editForm.name" class="edit-name-input" />
              <h3 v-else>
                {{ selectedPrompt.name }}
              </h3>
              <div class="detail-badges">
                <el-tag :type="promptTypeTag(selectedPrompt.prompt_type)">
                  {{ selectedPrompt.prompt_type }}
                </el-tag>
                <el-tag type="success">
                  v{{ selectedPrompt.version }}
                </el-tag>
                <el-tag v-if="selectedPrompt.is_system" type="info">
                  系统提示词
                </el-tag>
                <el-switch
                  :model-value="selectedPrompt.enabled"
                  active-text="启用"
                  inactive-text="禁用"
                  @change="(val: any) => selectedPrompt && handleToggle(selectedPrompt, !!val)"
                />
                <el-button size="small" :loading="versionsLoading" @click="loadVersions">
                  刷新版本
                </el-button>
              </div>
            </div>
          </div>

          <div class="detail-body">
            <div class="section">
              <el-collapse v-model="versionCollapseNames" class="version-collapse">
                <el-collapse-item name="versions">
                  <template #title>
                    <span class="version-collapse-title">
                      版本管理（共 {{ versions.length }} 个版本）
                    </span>
                  </template>
                  <div class="version-list">
                    <div v-for="version in versions" :key="version.id" class="version-item">
                      <span :class="{ active: version.is_active }">
                        <span class="text-muted">{{ version.updated_at || version.created_at }}</span>
                        v{{ version.version }}{{ version.is_active ? '（当前）' : '' }}
                      </span>
                      <div class="version-actions">
                        <el-button size="small" link @click="selectVersion(version)">
                          编辑
                        </el-button>
                        <el-button v-if="!version.is_active" size="small" link type="primary" @click="handleActivate(version)">
                          激活
                        </el-button>
                        <el-button
                          v-if="!version.is_active && !version.is_system"
                          size="small"
                          link
                          type="danger"
                          @click="handleDeleteVersion(version)"
                        >
                          删除
                        </el-button>
                      </div>
                    </div>
                  </div>
                </el-collapse-item>
              </el-collapse>
            </div>
            <div class="section">
              <h4>基本信息</h4>
              <el-form label-width="100px" size="small">
                <el-form-item label="编码">
                  <span class="mono">{{ selectedPrompt.code }}</span>
                </el-form-item>
                <el-form-item label="名称">
                  <el-input v-if="editing" v-model="editForm.name" />
                  <span v-else>{{ selectedPrompt.name }}</span>
                </el-form-item>
                <el-form-item label="类型">
                  <el-select v-if="editing" v-model="editForm.prompt_type">
                    <el-option label="workflow" value="workflow" />
                    <el-option label="chat" value="chat" />
                  </el-select>
                  <span v-else>{{ selectedPrompt.prompt_type }}</span>
                </el-form-item>
                <el-form-item label="描述">
                  <el-input v-if="editing" v-model="editForm.description" type="textarea" :rows="2" />
                  <span v-else>{{ selectedPrompt.description || '-' }}</span>
                </el-form-item>
              </el-form>
            </div>

            <div class="section">
              <div class="section-title-row">
                <h4>提示词构造序列</h4>
                <div v-if="editing" class="inline-actions">
                  <el-button size="small" @click="addTextBlock">
                    <el-icon><Plus /></el-icon> 文本块
                  </el-button>
                  <el-button size="small" @click="addPlaceholderBlock">
                    <el-icon><Plus /></el-icon> 对话历史占位符
                  </el-button>
                </div>
              </div>

              <div ref="blocksContainer" class="blocks-list">
                <div v-for="(block, index) in displayBlocks" :key="blockKeys[index]" class="block-card" :data-index="index">
                  <div class="block-header">
                    <div class="flex items-center flex-1 gap-2">
                      <span class="drag-handle">≡ {{ index + 1 }}</span>
                      <el-input v-if="editing" v-model="block.label" class="block-label-input" size="small" />
                      <span v-else class="block-label">{{ block.label }}</span>
                      <el-tag size="small" :type="block.type === 'text' ? 'primary' : 'warning'">
                        {{ block.type === 'text' ? '文本' : '对话历史' }}
                      </el-tag>
                    </div>
                    <el-button v-if="editing" size="small" link type="danger" @click="removeBlock(index)">
                      删除
                    </el-button>
                  </div>
                  <el-input
                    v-if="block.type === 'text'"
                    :ref="(el: any) => setBlockInputRef(el, index)"
                    v-model="block.content"
                    type="textarea"
                    :rows="5"
                    :readonly="!editing"
                    @focus="focusedBlockIndex = index"
                    @input="handleBlocksChanged"
                  />
                  <div v-else class="placeholder-block">
                    运行时插入 LangGraph 对话历史占位符
                  </div>
                </div>
              </div>
            </div>

            <div class="section">
              <h4>工具绑定</h4>
              <div v-if="editing" class="tool-bind-row">
                <el-select
                  v-model="toolSelectValue"
                  filterable
                  clearable
                  popper-class="tool-select-dropdown"
                  :filter-method="filterTools"
                  placeholder="搜索并绑定工具..."
                  style="width: 100%"
                  @visible-change="handleToolSelectVisible"
                  @change="handleToolSelectChange"
                >
                  <el-option
                    v-for="tool in filteredToolOptions"
                    :key="tool.id"
                    :label="tool.name"
                    :value="tool.code"
                    :disabled="editForm.bind_tools.includes(tool.code)"
                  >
                    <div class="tool-option">
                      <div class="tool-option-header">
                        <span class="tool-option-name" v-html="highlightMatch(tool.name)" />
                        <el-tag size="small" :type="toolTypeTag(tool.type)">
                          {{ tool.type }}
                        </el-tag>
                        <el-tag v-for="tag in tool.tags.slice(0, 2)" :key="tag" size="small" type="info">
                          <span v-html="highlightMatch(tag)" />
                        </el-tag>
                        <el-tag v-if="editForm.bind_tools.includes(tool.code)" size="small" type="success">
                          已绑定
                        </el-tag>
                      </div>
                      <div class="tool-option-description" v-html="highlightMatch(tool.description || '-')" />
                      <div v-if="toolSearchQuery && getToolMatchText(tool)" class="tool-option-match">
                        匹配：<span v-html="highlightMatch(getToolMatchText(tool))" />
                      </div>
                    </div>
                  </el-option>
                </el-select>
              </div>
              <div class="bound-tools">
                <el-tag
                  v-for="toolCode in editForm.bind_tools"
                  :key="toolCode"
                  :closable="editing"
                  class="tag-chip"
                  @close="removeBoundTool(toolCode)"
                >
                  {{ getToolName(toolCode) }}
                </el-tag>
                <span v-if="editForm.bind_tools.length === 0" class="text-muted">未绑定工具</span>
              </div>
            </div>

            <div class="section">
              <h4>可用变量</h4>
              <div class="variables-grid">
                <div class="variable-group">
                  <div class="variable-title">
                    工具入参
                  </div>
                  <el-tag v-for="variable in derivedVariables.tool_params" :key="`param-${variable.source_tool}-${variable.name}`" class="variable-chip" @click="insertVariable(variable.name)">
                    {{ variableTemplate(variable.name) }}
                  </el-tag>
                  <span v-if="derivedVariables.tool_params.length === 0" class="text-muted">无</span>
                </div>
                <div class="variable-group">
                  <div class="variable-title">
                    工具出参
                  </div>
                  <el-tag v-for="variable in derivedVariables.tool_outputs" :key="`output-${variable.source_tool}-${variable.name}`" class="variable-chip" type="success" @click="insertVariable(variable.name)">
                    {{ variableTemplate(variable.name) }}
                  </el-tag>
                  <span v-if="derivedVariables.tool_outputs.length === 0" class="text-muted">无</span>
                </div>
                <div class="variable-group">
                  <div class="variable-title">
                    文本中已使用
                  </div>
                  <el-tag v-for="name in manualVariables" :key="name" class="variable-chip" type="warning" @click="insertVariable(name)">
                    {{ variableTemplate(name) }}
                  </el-tag>
                  <span v-if="manualVariables.length === 0" class="text-muted">无</span>
                </div>
              </div>
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
                placeholder="添加标签"
                style="width: 100%"
              >
                <el-option v-for="tag in allTags" :key="tag" :label="tag" :value="tag" />
              </el-select>
              <div v-else>
                <el-tag v-for="tag in selectedPrompt.tags" :key="tag" class="tag-chip">
                  {{ tag }}
                </el-tag>
                <span v-if="selectedPrompt.tags.length === 0" class="text-muted">无标签</span>
              </div>
            </div>
          </div>

          <div class="detail-footer">
            <el-button :disabled="editing" @click="showRenderDialog">
              预览渲染
            </el-button>
            <template v-if="editing">
              <el-button type="primary" :loading="saveLoading" @click="handleSave">
                保存
              </el-button>
              <el-button :loading="saveLoading" @click="handleSaveNewVersion">
                另存为新版本
              </el-button>
              <el-button @click="cancelEdit">
                取消
              </el-button>
            </template>
            <template v-else>
              <el-button type="primary" @click="startEdit">
                编辑
              </el-button>
              <el-button
                v-if="!selectedPrompt.is_active && !selectedPrompt.is_system"
                type="danger"
                @click="handleDeleteVersion(selectedPrompt)"
              >
                删除版本
              </el-button>
              <el-button
                v-if="!selectedPrompt.is_system"
                type="danger"
                @click="handleDeletePrompt(selectedPrompt)"
              >
                删除提示词
              </el-button>
            </template>
          </div>
        </div>

        <el-empty v-else description="选择左侧提示词查看详情" />
      </el-col>
    </el-row>

    <el-dialog v-model="createVisible" title="新建提示词" width="640px" destroy-on-close>
      <el-form :model="createForm" label-width="100px" size="small">
        <el-form-item label="编码" required>
          <el-input v-model="createForm.code" placeholder="market_analyst_system" />
        </el-form-item>
        <el-form-item label="名称" required>
          <el-input v-model="createForm.name" />
        </el-form-item>
        <el-form-item label="类型">
          <el-select v-model="createForm.prompt_type">
            <el-option label="workflow" value="workflow" />
            <el-option label="chat" value="chat" />
          </el-select>
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="createForm.description" type="textarea" :rows="2" />
        </el-form-item>
        <el-form-item label="标签">
          <el-select v-model="createForm.tags" multiple filterable allow-create default-first-option style="width: 100%">
            <el-option v-for="tag in allTags" :key="tag" :label="tag" :value="tag" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createVisible = false">
          取消
        </el-button>
        <el-button type="primary" :loading="createLoading" @click="handleCreate">
          确定
        </el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="renderVisible" title="预览渲染" width="780px" destroy-on-close>
      <el-form label-width="100px" size="small">
        <el-form-item label="变量 JSON">
          <el-input v-model="renderVariablesText" type="textarea" :rows="5" placeholder="{&quot;ticker&quot;:&quot;AAPL&quot;}" />
        </el-form-item>
      </el-form>
      <el-button type="primary" :loading="renderLoading" @click="handleRender">
        渲染
      </el-button>
      <div v-if="renderResult" class="render-result">
        <h4>未解析变量</h4>
        <div>
          <el-tag v-for="name in renderResult.unresolved_variables" :key="name" type="warning" class="tag-chip">
            {{ variableTemplate(name) }}
          </el-tag>
          <span v-if="renderResult.unresolved_variables.length === 0" class="text-muted">无</span>
        </div>
        <h4>渲染结果</h4>
        <div v-for="(block, index) in renderResult.rendered_blocks" :key="index" class="render-block">
          <div class="render-block-title">
            {{ index + 1 }}. {{ block.label }}（{{ block.type }}）
          </div>
          <pre v-if="block.type === 'text'">{{ block.content }}</pre>
          <span v-else class="text-muted">对话历史占位符</span>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<style scoped>
.prompt-management {
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
.inline-actions,
.detail-badges,
.version-actions {
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
.prompt-list {
  max-height: calc(100vh - 390px);
}
.prompt-item {
  padding: 10px 12px;
  border-radius: 6px;
  cursor: pointer;
  margin-bottom: 4px;
  border: 1px solid transparent;
  transition: all 0.2s;
}
.prompt-item:hover {
  background: var(--el-fill-color-light);
}
.prompt-item.active {
  background: var(--el-color-primary-light-9);
  border-color: var(--el-color-primary-light-7);
}
.prompt-item-header,
.detail-title-row,
.section-title-row,
.tool-result-item,
.version-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.prompt-name {
  font-weight: 500;
  font-size: 13px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.prompt-item-meta,
.prompt-item-tags {
  display: flex;
  gap: 4px;
  margin-top: 4px;
  flex-wrap: wrap;
}
.prompt-code {
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
.version-collapse {
  border-top: none;
  border-bottom: none;
}
.version-collapse-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--el-text-color-secondary);
}
.version-list {
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 6px;
}
.version-item {
  padding: 8px 10px;
  border-bottom: 1px solid var(--el-border-color-lighter);
}
.version-item:last-child {
  border-bottom: none;
}
.version-item .active {
  color: var(--el-color-primary);
  font-weight: 600;
}
.blocks-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.block-card {
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 8px;
  padding: 12px;
}
.block-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}
.drag-handle {
  cursor: move;
  color: var(--el-text-color-secondary);
  user-select: none;
}
.block-label-input {
  max-width: 240px;
}
.block-label {
  font-weight: 500;
}
.placeholder-block {
  padding: 12px;
  border-radius: 6px;
  background: var(--el-fill-color-light);
  color: var(--el-text-color-secondary);
}
.tool-bind-row {
  margin-bottom: 8px;
}
.bound-tools {
  margin-bottom: 8px;
  min-height: 28px;
}
.tool-option {
  padding: 4px 0;
  line-height: 1.4;
}
.tool-option-header {
  display: flex;
  align-items: center;
  gap: 6px;
}
.tool-option-name {
  font-weight: 600;
}
.tool-option-description,
.tool-option-match {
  margin-top: 2px;
  color: var(--el-text-color-secondary);
  font-size: 12px;
  white-space: normal;
}
:global(.tool-select-dropdown .el-select-dropdown__item) {
  height: auto;
  min-height: 76px;
  padding: 8px 12px;
  line-height: normal;
  white-space: normal;
}
:global(.tool-select-dropdown .el-select-dropdown__item.selected) {
  font-weight: normal;
}
:global(.tool-select-dropdown .el-select-dropdown__item.is-disabled) {
  cursor: not-allowed;
}
:global(.tool-select-dropdown .el-select-dropdown__wrap) {
  max-height: 420px;
}
:global(.tool-match-highlight) {
  padding: 0 2px;
  border-radius: 2px;
  color: var(--el-color-warning-dark-2);
  background: var(--el-color-warning-light-8);
}
.variables-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}
.variable-group {
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 6px;
  padding: 10px;
}
.variable-title {
  font-size: 13px;
  font-weight: 600;
  margin-bottom: 8px;
}
.variable-chip {
  margin: 0 6px 6px 0;
  cursor: pointer;
}
.tag-chip {
  margin-right: 6px;
  margin-bottom: 4px;
}
.mono {
  font-family: monospace;
  font-size: 13px;
}
.text-muted {
  color: var(--el-text-color-placeholder);
  font-size: 13px;
}
.detail-footer {
  margin-top: 20px;
  padding-top: 16px;
  border-top: 1px solid var(--el-border-color-lighter);
  display: flex;
  gap: 8px;
  justify-content: flex-end;
}
.render-result {
  margin-top: 16px;
}
.render-block {
  margin-top: 10px;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 6px;
  padding: 10px;
}
.render-block-title {
  font-weight: 600;
  margin-bottom: 8px;
}
.render-block pre {
  white-space: pre-wrap;
  margin: 0;
  font-family: monospace;
  font-size: 13px;
}
:global(.sortable-ghost) {
  opacity: 0.5;
}
</style>
