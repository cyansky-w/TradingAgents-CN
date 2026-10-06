<script setup lang="ts">
import type { Workflow } from '@/api/workflows'
import { EditPen, MoreFilled, VideoPlay } from '@element-plus/icons-vue'
import { computed, ref } from 'vue'

const props = defineProps<{ workflow: Workflow }>()

defineEmits<{
  detail: []
  edit: []
  run: []
  toggle: [wf: Workflow, enabled: boolean]
  validate: [wf: Workflow]
  delete: [wf: Workflow]
}>()

const hoveredNode = ref<string | null>(null)

function nodeLabel(id: string) {
  const node = props.workflow.nodes.find(n => n.id === id)
  return node?.label || id
}

const triggerLabel = computed(() => {
  const map: Record<string, string> = { manual: '手动触发', cron: '定时触发', event: '事件触发' }
  const t = props.workflow.trigger?.type || 'manual'
  return map[t] || t
})

function nodeColor(type: string) {
  const map: Record<string, string> = {
    agent: 'var(--el-color-primary)',
    subflow: 'var(--el-color-warning)',
    io: 'var(--el-color-success)'
  }
  return map[type] || 'var(--el-color-info)'
}

function nodeTypeLabel(type: string) {
  const map: Record<string, string> = { agent: 'Agent', subflow: '子流程', io: 'IO' }
  return map[type] || type
}

interface SvgNode { id: string, type: string, x: number, y: number }
interface SvgEdge { id: string, x1: number, y1: number, x2: number, y2: number }

const W = 240; const H = 90; const PAD = 20

const svgNodes = computed<SvgNode[]>(() => {
  const nodes = props.workflow.nodes
  if (!nodes.length)
    return []
  const pos = layout(nodes, props.workflow.edges)
  return nodes.map(n => ({ id: n.id, type: n.type, ...pos[n.id] }))
})

const svgEdges = computed<SvgEdge[]>(() => {
  const pos = layout(props.workflow.nodes, props.workflow.edges)
  return props.workflow.edges.map(e => {
    const s = pos[e.source]; const t = pos[e.target]
    return s && t ? { id: e.id, x1: s.x, y1: s.y, x2: t.x, y2: t.y } : null
  }).filter(Boolean) as SvgEdge[]
})

function layout(nodes: Workflow['nodes'], edges: Workflow['edges']) {
  const inDeg: Record<string, number> = {}
  const adj: Record<string, string[]> = {}
  nodes.forEach(n => { inDeg[n.id] = 0; adj[n.id] = [] })
  edges.forEach(e => { inDeg[e.target] = (inDeg[e.target] || 0) + 1; adj[e.source]?.push(e.target) })

  const layers: string[][] = []
  const assigned = new Set<string>()
  let queue = nodes.filter(n => inDeg[n.id] === 0).map(n => n.id)
  if (!queue.length)
    queue = [nodes[0].id]

  while (queue.length) {
    layers.push([...queue])
    queue.forEach(id => assigned.add(id))
    const next: string[] = []
    for (const id of queue) {
      for (const tid of (adj[id] || [])) {
        inDeg[tid]--
        if (inDeg[tid] <= 0 && !assigned.has(tid)) { next.push(tid); assigned.add(tid) }
      }
    }
    queue = next
  }
  for (const n of nodes) { if (!assigned.has(n.id)) { (layers[layers.length - 1] ||= []).push(n.id) } }

  const positions: Record<string, { x: number, y: number }> = {}
  const ls = layers.length > 1 ? (W - 2 * PAD) / (layers.length - 1) : 0
  layers.forEach((layer, li) => {
    const x = layers.length > 1 ? PAD + li * ls : W / 2
    const vs = layer.length > 1 ? (H - 2 * PAD) / (layer.length - 1) : 0
    layer.forEach((id, ni) => {
      positions[id] = { x, y: layer.length > 1 ? PAD + ni * vs : H / 2 }
    })
  })
  return positions
}
</script>

<template>
  <div class="workflow-card" :class="{ disabled: !workflow.enabled }" @click="$emit('detail')">
    <div class="card-header">
      <span class="card-name" :title="workflow.name">{{ workflow.name }}</span>
      <el-switch
        :model-value="workflow.enabled"
        size="small"
        @click.stop
        @change="(val: any) => $emit('toggle', workflow, !!val)"
      />
    </div>

    <div class="card-preview">
      <svg :width="240" :height="90" viewBox="0 0 240 90" xmlns="http://www.w3.org/2000/svg">
        <line
          v-for="edge in svgEdges" :key="edge.id"
          :x1="edge.x1" :y1="edge.y1" :x2="edge.x2" :y2="edge.y2"
          :stroke="workflow.enabled ? 'var(--el-color-primary-light-5)' : 'var(--el-border-color)'"
          stroke-width="1.5"
        />
        <g
          v-for="node in svgNodes" :key="node.id" class="preview-node"
          @mouseenter="hoveredNode = node.id"
          @mouseleave="hoveredNode = null"
        >
          <title>{{ nodeTypeLabel(node.type) }}: {{ nodeLabel(node.id) }}</title>
          <circle
            :cx="node.x" :cy="node.y" :r="hoveredNode === node.id ? 7 : 5"
            :fill="nodeColor(node.type)"
            :stroke="hoveredNode === node.id ? 'var(--el-color-primary-dark-2)' : 'none'"
            stroke-width="1.5"
          />
          <text
            v-if="hoveredNode === node.id"
            :x="node.x" :y="node.y - 12"
            text-anchor="middle"
            font-size="10"
            fill="var(--el-text-color-primary)"
          >{{ nodeLabel(node.id) }}</text>
        </g>
      </svg>
    </div>

    <div class="card-meta">
      <span class="meta-item">{{ triggerLabel }}</span>
      <span class="meta-item">{{ workflow.nodes.length }} 节点</span>
      <el-tag :type="workflow.enabled ? 'success' : 'info'" size="small">
        {{ workflow.enabled ? '启用' : '禁用' }}
      </el-tag>
    </div>

    <div v-if="workflow.description" class="card-desc">
      {{ workflow.description }}
    </div>

    <div v-if="workflow.tags.length" class="card-tags">
      <el-tag v-for="tag in workflow.tags.slice(0, 2)" :key="tag" size="small" type="info">
        {{ tag }}
      </el-tag>
      <el-tag v-if="workflow.tags.length > 2" size="small" type="info">
        +{{ workflow.tags.length - 2 }}
      </el-tag>
    </div>

    <div class="card-actions" @click.stop>
      <el-button size="small" @click="$emit('edit')">
        <el-icon><EditPen /></el-icon> 编辑
      </el-button>
      <el-button size="small" @click="$emit('run')">
        <el-icon><VideoPlay /></el-icon> 运行
      </el-button>
      <el-dropdown trigger="click" @command="(cmd: string) => $emit(cmd as any, workflow)">
        <el-button size="small" text>
          <el-icon><MoreFilled /></el-icon>
        </el-button>
        <template #dropdown>
          <el-dropdown-menu>
            <el-dropdown-item command="validate">
              校验 DAG
            </el-dropdown-item>
            <el-dropdown-item command="delete" divided style="color: var(--el-color-danger)">
              删除
            </el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>
    </div>
  </div>
</template>

<style scoped>
.workflow-card {
  background: var(--el-bg-color);
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 8px;
  padding: 16px;
  cursor: pointer;
  transition: all 0.2s;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.workflow-card:hover {
  border-color: var(--el-color-primary-light-5);
  box-shadow: 0 2px 12px var(--el-color-primary-light-9);
}
.workflow-card.disabled { opacity: 0.65; }
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.card-name {
  font-weight: 600;
  font-size: 14px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex: 1;
  margin-right: 8px;
}
.card-preview {
  background: var(--el-fill-color-lighter);
  border-radius: 6px;
  display: flex;
  justify-content: center;
  overflow: hidden;
}
.card-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
.meta-item { white-space: nowrap; }
.card-desc {
  font-size: 12px;
  color: var(--el-text-color-regular);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.card-tags {
  display: flex;
  gap: 4px;
  flex-wrap: wrap;
}
.card-actions {
  display: flex;
  gap: 4px;
  align-items: center;
  margin-top: auto;
  padding-top: 4px;
  border-top: 1px solid var(--el-border-color-lighter);
}
.preview-node { cursor: pointer; }
</style>
