<template>
  <div class="tool-management">
    <div class="page-header">
      <h2>工具管理</h2>
      <div class="header-actions">
        <el-button type="primary" @click="showRegisterDialog">
          <el-icon><Plus /></el-icon> 注册工具
        </el-button>
        <el-button @click="handleSeed" :loading="seedLoading">
          <el-icon><Refresh /></el-icon> 初始化工具
        </el-button>
      </div>
    </div>

    <el-row :gutter="20" class="flex-1" >
      <!-- Left: Filter + List -->
      <el-col :span="6">
        <div class="filter-section">
          <el-input
            v-model="searchText"
            placeholder="搜索工具..."
            prefix-icon="Search"
            clearable
            @input="handleSearch"
          />
          <div class="filter-row">
            <el-select v-model="filterType" placeholder="类型" clearable @change="loadTools()">
              <el-option label="builtin" value="builtin" />
              <el-option label="rpc" value="rpc" />
              <el-option label="remote" value="remote" />
              <el-option label="workflow" value="workflow" />
            </el-select>
            <el-select v-model="filterTag" placeholder="标签" clearable @change="loadTools()">
              <el-option v-for="tag in allTags" :key="tag" :label="tag" :value="tag" />
            </el-select>
          </div>
          <div class="filter-row">
            <el-select v-model="filterEnabled" placeholder="状态" clearable @change="loadTools()">
              <el-option label="已启用" :value="true" />
              <el-option label="已禁用" :value="false" />
            </el-select>
          </div>
        </div>

        <el-scrollbar class="tool-list" @scroll="onListScroll" ref="listScrollbar">
          <div
            v-for="tool in tools"
            :key="tool.id"
            class="tool-item"
            :class="{ active: selectedTool?.id === tool.id }"
            @click="selectTool(tool)"
          >
            <div class="tool-item-header">
              <span class="tool-name">{{ tool.name }}</span>
              <el-switch
                :model-value="tool.enabled"
                size="small"
                @click.stop
                @change="(val: any) => handleToggle(tool, !!val)"
              />
            </div>
            <div class="tool-item-meta">
              <el-tag size="small" :type="typeTagType(tool.type)">{{ tool.type }}</el-tag>
              <el-tag v-if="tool.is_system" size="small" type="info">系统</el-tag>
            </div>
            <div class="tool-item-tags">
              <el-tag v-for="tag in tool.tags.slice(0, 3)" :key="tag" size="small" type="info" class="mini-tag">{{ tag }}</el-tag>
            </div>
          </div>
          <el-empty v-if="tools.length === 0 && !listLoading" description="暂无工具" />
          <div v-if="listLoading" class="list-loading">
            <el-icon class="is-loading"><Loading /></el-icon> 加载中...
          </div>
          <div v-if="!listLoading && tools.length > 0 && tools.length >= total" class="list-end">
            已加载全部 {{ total }} 个工具
          </div>
        </el-scrollbar>
      </el-col>

      <!-- Right: Detail / Edit -->
      <el-col :span="18">
        <div v-if="selectedTool" class="detail-panel">
          <div class="detail-header">
            <div class="detail-title-row">
              <el-input
                v-if="editing"
                v-model="editForm.name"
                class="edit-name-input"
              />
              <h3 v-else>{{ selectedTool.name }}</h3>
              <div class="detail-badges">
                <el-tag :type="typeTagType(selectedTool.type)">{{ selectedTool.type }}</el-tag>
                <el-tag v-if="selectedTool.is_system" type="info">系统工具</el-tag>
                <el-switch
                  :model-value="selectedTool.enabled"
                  active-text="启用"
                  inactive-text="禁用"
                  @change="(val: any) => selectedTool && handleToggle(selectedTool, !!val)"
                />
              </div>
            </div>
          </div>

          <div class="detail-body">
            <!-- Basic Info -->
            <div class="section">
              <h4>基本信息</h4>
              <el-form label-width="100px" size="small">
                <el-form-item label="编码">
                  <span class="mono">{{ selectedTool.code }}</span>
                </el-form-item>
                <el-form-item label="名称">
                  <el-input v-if="editing" v-model="editForm.name" />
                  <span v-else>{{ selectedTool.name }}</span>
                </el-form-item>
                <el-form-item label="描述">
                  <el-input
                    v-if="editing"
                    v-model="editForm.description"
                    type="textarea"
                    :rows="3"
                  />
                  <span v-else>{{ selectedTool.description }}</span>
                </el-form-item>
                <el-form-item label="超时时间">
                  <el-input-number
                    v-if="editing"
                    v-model="editForm.timeout"
                    :min="1"
                    :max="3600"
                  />
                  <span v-else>{{ selectedTool.timeout }} 秒</span>
                </el-form-item>
                <el-form-item v-if="selectedTool.type === 'builtin'" label="Handler">
                  <span class="mono">{{ selectedTool.handler }}</span>
                </el-form-item>
              </el-form>
            </div>

            <!-- Tags -->
            <div class="section">
              <h4>标签</h4>
              <div v-if="editing">
                <el-select
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
              </div>
              <div v-else>
                <el-tag v-for="tag in selectedTool.tags" :key="tag" class="tag-chip">{{ tag }}</el-tag>
                <span v-if="selectedTool.tags.length === 0" class="text-muted">无标签</span>
              </div>
            </div>

            <!-- Parameters (builtin: read-only table) -->
            <div class="section">
              <h4>参数</h4>
              <el-table :data="displayParams" size="small" border>
                <el-table-column prop="name" label="名称" />
                <el-table-column prop="type" label="类型" width="100" />
                <el-table-column prop="required" label="必填" width="80">
                  <template #default="{ row }">
                    <el-tag :type="row.required ? 'danger' : 'info'" size="small">
                      {{ row.required ? '是' : '否' }}
                    </el-tag>
                  </template>
                </el-table-column>
                <el-table-column prop="default" label="默认值" width="120">
                  <template #default="{ row }">{{ row.default ?? '-' }}</template>
                </el-table-column>
                <el-table-column prop="description" label="描述" />
                <el-table-column v-if="editing && selectedTool.type !== 'builtin'" label="操作" width="80">
                  <template #default="{ $index }">
                    <el-button type="danger" size="small" link @click="removeParam($index)">删除</el-button>
                  </template>
                </el-table-column>
              </el-table>
              <el-button
                v-if="editing && selectedTool.type !== 'builtin'"
                size="small"
                @click="addParam"
                style="margin-top: 8px"
              >
                <el-icon><Plus /></el-icon> 添加参数
              </el-button>
            </div>

            <!-- RPC/Remote specific fields -->
            <div v-if="selectedTool.type !== 'builtin'" class="section">
              <h4>连接配置</h4>
              <el-form label-width="100px" size="small">
                <el-form-item label="服务地址">
                  <el-input v-if="editing" v-model="editForm.endpoint_url" />
                  <span v-else class="mono">{{ selectedTool.endpoint_url || '-' }}</span>
                </el-form-item>
                <el-form-item v-if="selectedTool.type === 'remote'" label="请求方法">
                  <el-select v-if="editing" v-model="editForm.endpoint_method">
                    <el-option label="GET" value="GET" />
                    <el-option label="POST" value="POST" />
                    <el-option label="PUT" value="PUT" />
                    <el-option label="DELETE" value="DELETE" />
                  </el-select>
                  <span v-else>{{ selectedTool.endpoint_method || '-' }}</span>
                </el-form-item>
                <el-form-item label="认证方式">
                  <el-select v-if="editing" v-model="editForm.auth_type">
                    <el-option label="无" value="none" />
                    <el-option label="API Key" value="api_key" />
                    <el-option label="Bearer Token" value="bearer" />
                    <el-option label="Basic Auth" value="basic" />
                  </el-select>
                  <span v-else>{{ selectedTool.auth_type || 'none' }}</span>
                </el-form-item>
                <el-form-item v-if="displayAuthType !== 'none'" label="认证配置">
                  <div v-if="editing" class="auth-config-form">
                    <template v-if="editForm.auth_type === 'api_key'">
                      <el-input v-model="editForm.auth_config.key" placeholder="Key" style="margin-bottom: 4px" />
                      <el-input v-model="editForm.auth_config.value" placeholder="Value" />
                    </template>
                    <template v-else-if="editForm.auth_type === 'bearer'">
                      <el-input v-model="editForm.auth_config.token" placeholder="Token" />
                    </template>
                    <template v-else-if="editForm.auth_type === 'basic'">
                      <el-input v-model="editForm.auth_config.username" placeholder="Username" style="margin-bottom: 4px" />
                      <el-input v-model="editForm.auth_config.password" placeholder="Password" type="password" />
                    </template>
                  </div>
                  <span v-else class="text-muted">{{ JSON.stringify(selectedTool.auth_config) }}</span>
                </el-form-item>
                <el-form-item label="自定义请求头">
                  <div v-if="editing">
                    <div v-for="(_, i) in displayHeaders" :key="i" class="header-row">
                      <el-input v-model="displayHeaders[i].key" placeholder="Key" />
                      <el-input v-model="displayHeaders[i].value" placeholder="Value" />
                      <el-button type="danger" link @click="displayHeaders.splice(i, 1)">
                        <el-icon><Delete /></el-icon>
                      </el-button>
                    </div>
                    <el-button size="small" @click="displayHeaders.push({ key: '', value: '' })">
                      <el-icon><Plus /></el-icon> 添加请求头
                    </el-button>
                  </div>
                  <div v-else>
                    <div v-for="(val, key) in selectedTool.headers" :key="key" class="header-row-readonly">
                      <span class="mono">{{ key }}: {{ val }}</span>
                    </div>
                    <span v-if="!selectedTool.headers || Object.keys(selectedTool.headers).length === 0" class="text-muted">无</span>
                  </div>
                </el-form-item>
                <el-form-item label="健康检查URL">
                  <el-input v-if="editing" v-model="editForm.health_check_url" />
                  <span v-else class="mono">{{ selectedTool.health_check_url || '-' }}</span>
                </el-form-item>
                <el-form-item label="输出Schema">
                  <el-input
                    v-if="editing"
                    v-model="editForm.output_schema_str"
                    type="textarea"
                    :rows="3"
                    placeholder="JSON Schema (可选)"
                  />
                  <span v-else class="text-muted">{{ selectedTool.output_schema ? JSON.stringify(selectedTool.output_schema) : '-' }}</span>
                </el-form-item>
              </el-form>
            </div>

            <!-- Health Status -->
            <div class="section">
              <h4>健康状态</h4>
              <div class="health-row">
                <el-tag :type="healthTagType(selectedTool.health_status)" size="small">
                  {{ healthLabel(selectedTool.health_status) }}
                </el-tag>
                <span v-if="selectedTool.last_health_check" class="text-muted">
                  上次检查: {{ selectedTool.last_health_check }}
                </span>
              </div>
            </div>
          </div>

          <!-- Actions -->
          <div class="detail-footer">
            <el-button @click="handleHealthCheck" :loading="healthLoading">健康检查</el-button>
            <template v-if="editing">
              <el-button type="primary" @click="handleSave" :loading="saveLoading">保存</el-button>
              <el-button @click="cancelEdit">取消</el-button>
            </template>
            <template v-else>
              <el-button type="primary" @click="startEdit">编辑</el-button>
              <el-button
                v-if="!selectedTool.is_system"
                type="danger"
                @click="handleDelete(selectedTool)"
              >删除</el-button>
            </template>
          </div>
        </div>

        <el-empty v-else description="选择左侧工具查看详情" />
      </el-col>
    </el-row>

    <!-- Register Dialog -->
    <el-dialog v-model="registerVisible" title="注册工具" width="640px" destroy-on-close>
      <el-form :model="registerForm" label-width="100px" size="small">
        <el-form-item label="类型" required>
          <el-select v-model="registerForm.type">
            <el-option label="rpc" value="rpc" />
            <el-option label="remote" value="remote" />
            <el-option label="workflow" value="workflow" />
          </el-select>
        </el-form-item>
        <el-form-item label="编码" required>
          <el-input v-model="registerForm.code" placeholder="小写字母开头，仅允许小写字母、数字、下划线" />
        </el-form-item>
        <el-form-item label="名称" required>
          <el-input v-model="registerForm.name" />
        </el-form-item>
        <el-form-item label="描述" required>
          <el-input v-model="registerForm.description" type="textarea" :rows="2" />
        </el-form-item>
        <el-form-item v-if="registerForm.type !== 'workflow'" label="服务地址" required>
          <el-input v-model="registerForm.endpoint_url" placeholder="http://..." />
        </el-form-item>
        <el-form-item v-if="registerForm.type === 'workflow'" label="绑定工作流" required>
          <el-select v-model="registerForm.workflow_id" placeholder="选择工作流" filterable>
            <el-option v-for="wf in workflowOptions" :key="wf.id" :label="wf.name" :value="wf.id" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="registerForm.type === 'workflow'" label="输出格式">
          <el-select v-model="registerForm.output_format">
            <el-option label="完整 JSON" value="full" />
            <el-option label="摘要文本" value="summary" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="registerForm.type === 'remote'" label="请求方法">
          <el-select v-model="registerForm.endpoint_method">
            <el-option label="GET" value="GET" />
            <el-option label="POST" value="POST" />
            <el-option label="PUT" value="PUT" />
            <el-option label="DELETE" value="DELETE" />
          </el-select>
        </el-form-item>
        <el-form-item label="超时时间">
          <el-input-number v-model="registerForm.timeout" :min="1" :max="3600" />
        </el-form-item>
        <el-form-item label="认证方式">
          <el-select v-model="registerForm.auth_type">
            <el-option label="无" value="none" />
            <el-option label="API Key" value="api_key" />
            <el-option label="Bearer Token" value="bearer" />
            <el-option label="Basic Auth" value="basic" />
          </el-select>
        </el-form-item>
        <template v-if="registerForm.auth_type === 'api_key'">
          <el-form-item label="API Key">
            <el-input v-model="registerForm.auth_config.key" placeholder="Key" />
          </el-form-item>
          <el-form-item label="API Value">
            <el-input v-model="registerForm.auth_config.value" placeholder="Value" />
          </el-form-item>
        </template>
        <template v-else-if="registerForm.auth_type === 'bearer'">
          <el-form-item label="Token">
            <el-input v-model="registerForm.auth_config.token" placeholder="Token" />
          </el-form-item>
        </template>
        <template v-else-if="registerForm.auth_type === 'basic'">
          <el-form-item label="Username">
            <el-input v-model="registerForm.auth_config.username" placeholder="Username" />
          </el-form-item>
          <el-form-item label="Password">
            <el-input v-model="registerForm.auth_config.password" placeholder="Password" type="password" />
          </el-form-item>
        </template>
        <el-form-item label="自定义请求头">
          <div v-for="(_, i) in registerHeaders" :key="i" class="header-row">
            <el-input v-model="registerHeaders[i].key" placeholder="Key" />
            <el-input v-model="registerHeaders[i].value" placeholder="Value" />
            <el-button type="danger" link @click="registerHeaders.splice(i, 1)">
              <el-icon><Delete /></el-icon>
            </el-button>
          </div>
          <el-button size="small" @click="registerHeaders.push({ key: '', value: '' })">
            <el-icon><Plus /></el-icon> 添加请求头
          </el-button>
        </el-form-item>
        <el-form-item label="标签">
          <el-select
            v-model="registerForm.tags"
            multiple
            filterable
            allow-create
            default-first-option
            placeholder="添加标签"
            style="width: 100%"
          >
            <el-option v-for="tag in allTags" :key="tag" :label="tag" :value="tag" />
          </el-select>
        </el-form-item>
        <el-form-item label="健康检查URL">
          <el-input v-model="registerForm.health_check_url" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="registerVisible = false">取消</el-button>
        <el-button type="primary" @click="handleRegister" :loading="registerLoading">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Refresh, Delete, Loading } from '@element-plus/icons-vue'
import { toolsApi } from '@/api/tools'
import type { Tool, ToolParameter } from '@/api/tools'
import { workflowsApi, type Workflow } from '@/api/workflows'

const tools = ref<Tool[]>([])
const total = ref(0)
const currentPage = ref(1)
const pageSize = 20
const listLoading = ref(false)
const listScrollbar = ref()
const allTags = ref<string[]>([])
const workflowOptions = ref<Workflow[]>([])
const selectedTool = ref<Tool | null>(null)
const editing = ref(false)

// Filters
const searchText = ref('')
const filterType = ref('')
const filterTag = ref('')
const filterEnabled = ref<boolean | string>('')

// Loading states
const seedLoading = ref(false)
const saveLoading = ref(false)
const healthLoading = ref(false)
const registerLoading = ref(false)

// Edit form
const editForm = reactive({
  name: '',
  description: '',
  timeout: 300,
  tags: [] as string[],
  endpoint_url: '',
  endpoint_method: 'POST' as string,
  auth_type: 'none' as string,
  auth_config: {} as Record<string, string>,
  health_check_url: '',
  output_schema_str: '',
  params: [] as ToolParameter[],
})

const displayHeaders = ref<{ key: string; value: string }[]>([])

// Register form
const registerVisible = ref(false)
const registerHeaders = ref<{ key: string; value: string }[]>([])
const registerForm = reactive({
  type: 'rpc' as 'rpc' | 'remote' | 'workflow',
  code: '',
  name: '',
  description: '',
  endpoint_url: '',
  endpoint_method: 'POST' as string,
  timeout: 300,
  auth_type: 'none' as string,
  auth_config: {} as Record<string, string>,
  tags: [] as string[],
  health_check_url: '',
  workflow_id: '',
  output_format: 'summary' as 'full' | 'summary',
})

const displayParams = computed(() => {
  if (editing.value) return editForm.params
  return selectedTool.value?.parameters ?? []
})

const displayAuthType = computed(() => {
  if (editing.value) return editForm.auth_type
  return selectedTool.value?.auth_type ?? 'none'
})

function typeTagType(type: string) {
  if (type === 'builtin') return 'success'
  if (type === 'rpc') return 'warning'
  if (type === 'workflow') return 'info'
  return 'primary'
}

function healthTagType(status: string) {
  if (status === 'healthy') return 'success'
  if (status === 'unhealthy') return 'danger'
  return 'info'
}

function healthLabel(status: string) {
  if (status === 'healthy') return '健康'
  if (status === 'unhealthy') return '异常'
  return '未知'
}

async function loadTools(append = false) {
  if (listLoading.value) return
  if (!append) currentPage.value = 1
  listLoading.value = true
  try {
    const params: Record<string, any> = {
      page: currentPage.value,
      page_size: pageSize,
    }
    if (filterType.value) params.type = filterType.value
    if (filterTag.value) params.tag = filterTag.value
    params.enabled = filterEnabled.value === undefined || filterEnabled.value === '' ? undefined : Boolean(filterEnabled.value)
    if (searchText.value) params.search = searchText.value
    const res = await toolsApi.list(params)
    if (res.success) {
      if (append) {
        tools.value = [...tools.value, ...res.data.items]
      } else {
        tools.value = res.data.items
      }
      total.value = res.data.total
    }
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '加载工具列表失败')
  } finally {
    listLoading.value = false
  }
}

function onListScroll() {
  if (!listScrollbar.value) return
  const wrap = listScrollbar.value.wrapRef
  if (!wrap) return
  if (listLoading.value) return
  if (tools.value.length >= total.value) return
  const distanceToBottom = wrap.scrollHeight - wrap.scrollTop - wrap.clientHeight
  if (distanceToBottom < 50) {
    currentPage.value++
    loadTools(true)
  }
}

async function loadTags() {
  try {
    const res = await toolsApi.getAllTags()
    if (res.success) allTags.value = res.data
  } catch { /* ignore */ }
}

let searchTimer: ReturnType<typeof setTimeout>
function handleSearch() {
  clearTimeout(searchTimer)
  searchTimer = setTimeout(() => {
    currentPage.value = 1
    loadTools()
  }, 300)
}

function selectTool(tool: Tool) {
  if (editing.value) cancelEdit()
  selectedTool.value = tool
}

async function handleToggle(tool: Tool, enabled: boolean) {
  try {
    const res = await toolsApi.toggle(tool.id, enabled)
    if (res.success) {
      tool.enabled = enabled
      ElMessage.success('状态更新成功')
    }
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '操作失败')
  }
}

function startEdit() {
  if (!selectedTool.value) return
  const t = selectedTool.value
  editForm.name = t.name
  editForm.description = t.description
  editForm.timeout = t.timeout
  editForm.tags = [...t.tags]
  editForm.endpoint_url = t.endpoint_url || ''
  editForm.endpoint_method = t.endpoint_method || 'POST'
  editForm.auth_type = t.auth_type || 'none'
  editForm.auth_config = t.auth_config ? { ...t.auth_config } : {}
  editForm.health_check_url = t.health_check_url || ''
  editForm.output_schema_str = t.output_schema ? JSON.stringify(t.output_schema, null, 2) : ''
  editForm.params = t.parameters ? t.parameters.map(p => ({ ...p })) : []
  displayHeaders.value = t.headers
    ? Object.entries(t.headers).map(([key, value]) => ({ key, value }))
    : []
  editing.value = true
}

function cancelEdit() {
  editing.value = false
}

async function handleSave() {
  if (!selectedTool.value) return
  saveLoading.value = true
  try {
    const payload: any = {
      name: editForm.name,
      description: editForm.description,
      timeout: editForm.timeout,
      tags: editForm.tags,
    }
    if (selectedTool.value.type !== 'builtin') {
      payload.endpoint_url = editForm.endpoint_url
      payload.auth_type = editForm.auth_type
      payload.auth_config = editForm.auth_config
      payload.health_check_url = editForm.health_check_url
      payload.parameters = editForm.params
      if (editForm.output_schema_str) {
        try { payload.output_schema = JSON.parse(editForm.output_schema_str) } catch { /* ignore */ }
      }
      if (selectedTool.value.type === 'remote') {
        payload.endpoint_method = editForm.endpoint_method
      }
      const headers: Record<string, string> = {}
      for (const h of displayHeaders.value) {
        if (h.key) headers[h.key] = h.value
      }
      payload.headers = headers
    }
    const res = await toolsApi.update(selectedTool.value.id, payload)
    if (res.success) {
      ElMessage.success('更新成功')
      editing.value = false
      await loadTools()
      // Re-select the updated tool
      const updated = tools.value.find(t => t.id === selectedTool.value!.id)
      if (updated) selectedTool.value = updated
    }
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '更新失败')
  } finally {
    saveLoading.value = false
  }
}

async function handleDelete(tool: Tool) {
  try {
    await ElMessageBox.confirm(`确定删除工具 "${tool.name}" 吗？`, '删除确认', { type: 'warning' })
    const res = await toolsApi.remove(tool.id)
    if (res.success) {
      ElMessage.success('删除成功')
      if (selectedTool.value?.id === tool.id) selectedTool.value = null
      await loadTools()
    }
  } catch (e: any) {
    if (e !== 'cancel') ElMessage.error(e?.response?.data?.detail || '删除失败')
  }
}

async function handleHealthCheck() {
  if (!selectedTool.value) return
  healthLoading.value = true
  try {
    const res = await toolsApi.healthCheck(selectedTool.value.id)
    if (res.success) {
      selectedTool.value.health_status = res.data.health_status
      if (res.data.health_status === 'healthy') {
        ElMessage.success('健康检查通过')
      } else {
        ElMessage.warning(res.data.details || '健康检查异常')
      }
    }
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '健康检查失败')
  } finally {
    healthLoading.value = false
  }
}

async function handleSeed() {
  seedLoading.value = true
  try {
    const res = await toolsApi.seed()
    if (res.success) {
      ElMessage.success(`初始化完成: 新增${res.data.created} 更新${res.data.updated} 跳过${res.data.skipped}`)
      await loadTools()
      await loadTags()
    }
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '初始化失败')
  } finally {
    seedLoading.value = false
  }
}

function addParam() {
  editForm.params.push({ name: '', type: 'string', required: true, description: '' })
}

function removeParam(index: number) {
  editForm.params.splice(index, 1)
}

function showRegisterDialog() {
  registerForm.type = 'rpc'
  registerForm.code = ''
  registerForm.name = ''
  registerForm.description = ''
  registerForm.endpoint_url = ''
  registerForm.endpoint_method = 'POST'
  registerForm.timeout = 300
  registerForm.auth_type = 'none'
  registerForm.auth_config = {}
  registerForm.tags = []
  registerForm.health_check_url = ''
  registerForm.workflow_id = ''
  registerForm.output_format = 'summary'
  registerHeaders.value = []
  registerVisible.value = true
}

async function handleRegister() {
  const isWorkflow = registerForm.type === 'workflow'
  if (!registerForm.code || !registerForm.name || !registerForm.description) {
    ElMessage.warning('请填写必填字段')
    return
  }
  if (isWorkflow && !registerForm.workflow_id) {
    ElMessage.warning('请选择绑定的工作流')
    return
  }
  if (!isWorkflow && !registerForm.endpoint_url) {
    ElMessage.warning('请填写服务地址')
    return
  }
  registerLoading.value = true
  try {
    const headers: Record<string, string> = {}
    for (const h of registerHeaders.value) {
      if (h.key) headers[h.key] = h.value
    }
    const payload: any = {
      type: registerForm.type,
      code: registerForm.code,
      name: registerForm.name,
      description: registerForm.description,
      timeout: registerForm.timeout,
      tags: registerForm.tags,
      enabled: true,
    }
    if (isWorkflow) {
      payload.workflow_id = registerForm.workflow_id
      payload.output_format = registerForm.output_format
    } else {
      payload.endpoint_url = registerForm.endpoint_url
      payload.endpoint_method = registerForm.type === 'remote' ? registerForm.endpoint_method : undefined
      payload.auth_type = registerForm.auth_type
      payload.auth_config = registerForm.auth_type !== 'none' ? registerForm.auth_config : undefined
      payload.health_check_url = registerForm.health_check_url || undefined
      payload.headers = Object.keys(headers).length > 0 ? headers : undefined
    }
    const res = await toolsApi.create(payload)
    if (res.success) {
      ElMessage.success('注册成功')
      registerVisible.value = false
      await loadTools()
      await loadTags()
    }
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '注册失败')
  } finally {
    registerLoading.value = false
  }
}

onMounted(() => {
  loadTools()
  loadTags()
  workflowsApi.list({ page: 1, page_size: 100 }).then(res => {
    if (res.success) workflowOptions.value = res.data.items
  })
})
</script>

<style scoped>
.tool-management {
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
.header-actions {
  display: flex;
  gap: 8px;
}
.filter-section {
  margin-bottom: 12px;
}
.filter-section .el-input {
  margin-bottom: 8px;
}
.filter-row {
  display: flex;
  gap: 8px;
  margin-bottom: 8px;
}
.filter-row .el-select {
  flex: 1;
}
.tool-list {
  max-height: calc(100vh - 390px);
}
.tool-item {
  padding: 10px 12px;
  border-radius: 6px;
  cursor: pointer;
  margin-bottom: 4px;
  border: 1px solid transparent;
  transition: all 0.2s;
}
.tool-item:hover {
  background: var(--el-fill-color-light);
}
.tool-item.active {
  background: var(--el-color-primary-light-9);
  border-color: var(--el-color-primary-light-7);
}
.tool-item-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.tool-name {
  font-weight: 500;
  font-size: 13px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.tool-item-meta {
  display: flex;
  gap: 4px;
  margin-top: 4px;
}
.tool-item-tags {
  margin-top: 4px;
}
.mini-tag {
  margin-right: 2px;
}
.pagination-section {
  margin-top: 12px;
  display: flex;
  justify-content: center;
}
.list-loading {
  text-align: center;
  padding: 12px;
  color: var(--el-text-color-secondary);
  font-size: 13px;
}
.list-loading .el-icon {
  margin-right: 4px;
}
.list-end {
  text-align: center;
  padding: 12px;
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
.detail-title-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.detail-title-row h3 {
  margin: 0;
}
.edit-name-input {
  max-width: 300px;
}
.detail-badges {
  display: flex;
  align-items: center;
  gap: 8px;
}
.detail-body {
  flex: 1;
}
.section {
  margin-bottom: 20px;
}
.section h4 {
  margin: 0 0 12px 0;
  font-size: 14px;
  color: var(--el-text-color-secondary);
  border-bottom: 1px solid var(--el-border-color-lighter);
  padding-bottom: 6px;
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
.header-row {
  display: flex;
  gap: 8px;
  margin-bottom: 4px;
  align-items: center;
}
.header-row .el-input {
  flex: 1;
}
.header-row-readonly {
  font-size: 13px;
  margin-bottom: 2px;
}
.health-row {
  display: flex;
  align-items: center;
  gap: 12px;
}
.auth-config-form .el-input {
  margin-bottom: 4px;
}
.detail-footer {
  margin-top: 20px;
  padding-top: 16px;
  border-top: 1px solid var(--el-border-color-lighter);
  display: flex;
  gap: 8px;
  justify-content: flex-end;
}
</style>
