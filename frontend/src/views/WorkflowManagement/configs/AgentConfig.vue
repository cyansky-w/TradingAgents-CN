<script setup lang="ts">
import type { FlowNode } from '../composables/useWorkflowSync'
import type { Agent } from '@/api/agents'
import { computed, ref } from 'vue'

const props = defineProps<{
  node: FlowNode | null
  agentOptions: Agent[]
}>()

const emit = defineEmits<{ change: [] }>()

const newMappingKey = ref('')
const newMappingVal = ref('')

const hasLoop = computed(() => !!props.node?.data.loop_over)

const mappingEntries = computed(() => {
  const m: Record<string, string> = props.node?.data.input_mapping || {}
  return m
})

function emitChange() {
  emit('change')
}

function onAgentChange(agentId: string) {
  const agent = props.agentOptions?.find(a => a.id === agentId)
  if (agent && props.node) {
    props.node.data.agentName = agent.name
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

function onLoopToggle(val: boolean) {
  if (props.node) {
    if (val) {
      props.node.data.loop_over = ''
    } else {
      delete props.node.data.loop_over
      delete props.node.data.parallel
      delete props.node.data.max_concurrency
    }
    emitChange()
  }
}
</script>

<template>
  <div v-if="node" class="config-panel">
    <h4>Agent 节点配置</h4>
    <el-form label-width="80px" size="small">
      <el-form-item label="标签">
        <el-input :model-value="node!.label" @update:model-value="(v: string) => { node!.label = v; emitChange() }" />
      </el-form-item>
      <el-form-item label="绑定 Agent">
        <el-select :model-value="node!.data.agent_id" filterable placeholder="选择 Agent" @update:model-value="onAgentChange">
          <el-option v-for="a in agentOptions" :key="a.id" :label="a.name" :value="a.id" />
        </el-select>
      </el-form-item>
      <el-form-item label="输入映射">
        <div class="mapping-list">
          <div v-for="(val, key) in mappingEntries" :key="key" class="mapping-row">
            <el-input :model-value="key" disabled size="small" style="width: 120px" />
            <span class="mapping-arrow">=</span>
            <el-input :model-value="val" size="small" @change="(v: string) => updateMapping(key, v)" />
            <el-button size="small" text type="danger" @click="removeMapping(key)">
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
      <el-form-item label="循环">
        <el-switch v-model="hasLoop" @change="(val: string | number | boolean) => onLoopToggle(!!val)" />
      </el-form-item>
      <el-form-item v-if="hasLoop" label="循环字段">
        <el-input :model-value="node!.data.loop_over" placeholder="input.symbols" @update:model-value="(v: string) => { node!.data.loop_over = v; emitChange() }" />
      </el-form-item>
      <el-form-item v-if="hasLoop" label="并行执行">
        <el-switch :model-value="!!node!.data.parallel" @update:model-value="(v: string | number | boolean) => { node!.data.parallel = !!v; emitChange() }" />
      </el-form-item>
      <el-form-item v-if="hasLoop && node!.data.parallel" label="最大并发">
        <el-input-number :model-value="node!.data.max_concurrency" :min="1" :max="10" size="small" @update:model-value="(v: number | undefined) => { node!.data.max_concurrency = v ?? 1; emitChange() }" />
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
