<script setup lang="ts">
import type { FlowNode } from '../composables/useWorkflowSync'
import type { Workflow } from '@/api/workflows'
import { computed, ref } from 'vue'

const props = defineProps<{
  node: FlowNode | null
  workflowOptions: Workflow[]
  currentWorkflowId?: string
}>()

const emit = defineEmits<{ change: [] }>()

const newMappingKey = ref('')
const newMappingVal = ref('')

const mappingEntries = computed(() => props.node?.data.input_mapping || {})

function emitChange() { emit('change') }

function onWorkflowChange(wfId: string) {
  const wf = props.workflowOptions?.find(w => w.id === wfId)
  if (props.node && wf) {
    props.node.data.workflowName = wf.name
  }
  emitChange()
}

function updateMapping(key: string, val: string) {
  if (props.node) {
    if (!props.node.data.input_mapping)
      props.node.data.input_mapping = {}
    props.node.data.input_mapping[key] = val
    emitChange()
  }
}

function removeMapping(key: string) {
  if (props.node?.data.input_mapping) {
    delete props.node.data.input_mapping[key]
    emitChange()
  }
}

function addMapping() {
  if (!newMappingKey.value || !props.node)
    return
  if (!props.node.data.input_mapping)
    props.node.data.input_mapping = {}
  props.node.data.input_mapping[newMappingKey.value] = newMappingVal.value
  newMappingKey.value = ''
  newMappingVal.value = ''
  emitChange()
}
</script>

<template>
  <div v-if="node" class="config-panel">
    <h4>子流程配置</h4>
    <el-form label-width="80px" size="small">
      <el-form-item label="标签">
        <el-input :model-value="node!.label" @update:model-value="(v: string) => { node!.label = v; emitChange() }" />
      </el-form-item>
      <el-form-item label="绑定工作流">
        <el-select :model-value="node!.data.workflow_id" filterable placeholder="选择工作流" @update:model-value="onWorkflowChange">
          <el-option v-for="wf in workflowOptions" :key="wf.id" :label="wf.name" :value="wf.id" />
        </el-select>
      </el-form-item>
      <el-form-item label="输入映射">
        <div class="mapping-list">
          <div v-for="(val, key) in mappingEntries" :key="key" class="mapping-row">
            <el-input :model-value="key" disabled size="small" style="width: 120px" />
            <span class="mapping-arrow">=</span>
            <el-input :model-value="val" size="small" @change="(v: string) => updateMapping(String(key), v)" />
            <el-button size="small" text type="danger" @click="removeMapping(String(key))">
              x
            </el-button>
          </div>
          <div class="mapping-add">
            <el-input v-model="newMappingKey" size="small" placeholder="变量名" style="width: 120px" />
            <span class="mapping-arrow">=</span>
            <el-input v-model="newMappingVal" size="small" placeholder="{{input.xxx}}" />
            <el-button size="small" text type="primary" @click="addMapping">
              +
            </el-button>
          </div>
        </div>
      </el-form-item>
    </el-form>
  </div>
</template>

<style scoped>
.config-panel { padding: 12px; }
.config-panel h4 { margin: 0 0 12px; font-size: 14px; color: var(--el-text-color-secondary); }
.mapping-list { display: flex; flex-direction: column; gap: 6px; width: 100%; }
.mapping-row, .mapping-add { display: flex; align-items: center; gap: 4px; }
.mapping-arrow { color: var(--el-text-color-placeholder); font-size: 12px; }
</style>
