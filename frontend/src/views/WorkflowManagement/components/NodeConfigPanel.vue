<script setup lang="ts">
import type { FlowNode } from '../composables/useWorkflowSync'
import type { Agent } from '@/api/agents'
import type { Workflow } from '@/api/workflows'
import { InfoFilled } from '@element-plus/icons-vue'
import AgentConfig from '../configs/AgentConfig.vue'
import IOConfig from '../configs/IOConfig.vue'
import SubflowConfig from '../configs/SubflowConfig.vue'

defineProps<{
  selectedNode: FlowNode | null
  agentOptions: Agent[]
  workflowOptions: Workflow[]
  currentWorkflowId?: string
}>()

defineEmits<{
  change: []
  deleteNode: []
}>()
</script>

<template>
  <div class="editor-config">
    <template v-if="selectedNode">
      <AgentConfig
        v-if="selectedNode.type === 'agent'"
        :node="selectedNode"
        :agent-options="agentOptions"
        @change="$emit('change')"
      />
      <SubflowConfig
        v-else-if="selectedNode.type === 'subflow'"
        :node="selectedNode"
        :workflow-options="workflowOptions"
        :current-workflow-id="currentWorkflowId"
        @change="$emit('change')"
      />
      <IOConfig
        v-else-if="selectedNode.type === 'io'"
        :node="selectedNode"
        @change="$emit('change')"
      />
      <div class="config-actions">
        <el-button size="small" type="danger" @click="$emit('deleteNode')">
          删除节点
        </el-button>
      </div>
    </template>
    <template v-else>
      <div class="config-empty">
        <el-icon size="32" color="var(--el-text-color-placeholder)">
          <InfoFilled />
        </el-icon>
        <p>点击节点进行配置</p>
      </div>
    </template>
  </div>
</template>

<style scoped>
.editor-config {
  width: 320px;
  border-left: 1px solid var(--el-border-color-lighter);
  background: var(--el-bg-color);
  overflow-y: auto;
}
.config-actions {
  padding: 12px;
  border-top: 1px solid var(--el-border-color-lighter);
}
.config-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 200px;
  color: var(--el-text-color-placeholder);
}
.config-empty p {
  margin-top: 12px;
  font-size: 13px;
}
</style>
