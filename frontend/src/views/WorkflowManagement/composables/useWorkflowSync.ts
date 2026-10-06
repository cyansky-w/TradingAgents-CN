import type { WorkflowEdge, WorkflowNode } from '@/api/workflows'
import { ref } from 'vue'
import { workflowsApi } from '@/api/workflows'

export interface FlowNode {
  id: string
  type: string
  label: string
  position: { x: number, y: number }
  data: Record<string, any>
}

export interface FlowEdge {
  id: string
  source: string
  target: string
}

let _nodeCounter = 0

function nextNodeId(type: string) {
  _nodeCounter += 1
  return `${type}_${Date.now()}_${_nodeCounter}`
}

export function toFlowNodes(nodes: WorkflowNode[]): FlowNode[] {
  return nodes.map(n => ({
    id: n.id,
    type: n.type,
    label: n.label || n.id,
    position: n.position || { x: 0, y: 0 },
    data: {
      label: n.label || n.id,
      ...(n.config || {})
    }
  }))
}

export function toFlowEdges(edges: WorkflowEdge[]): FlowEdge[] {
  return edges.map(e => ({
    id: e.id,
    source: e.source,
    target: e.target
  }))
}

export function toApiNodes(flowNodes: FlowNode[]): WorkflowNode[] {
  return flowNodes.map(n => {
    const { label, io_direction, agent_id, agentName, workflow_id, workflowName, input_mapping, loop_over, parallel, max_concurrency, ...rest } = n.data
    return {
      id: n.id,
      type: n.type as 'agent' | 'subflow' | 'io',
      label: n.label,
      position: n.position,
      config: { io_direction, agent_id, agentName, workflow_id, workflowName, input_mapping, loop_over, parallel, max_concurrency, ...rest }
    }
  })
}

export function toApiEdges(flowEdges: FlowEdge[]): WorkflowEdge[] {
  return flowEdges.map(e => ({
    id: e.id,
    source: e.source,
    target: e.target
  }))
}

export function createNode(type: string, x: number, y: number): FlowNode {
  const id = nextNodeId(type)
  let label = ''
  const data: Record<string, any> = {}

  if (type === 'io') {
    label = 'IO'
    data.io_direction = 'input'
  } else if (type === 'agent') {
    label = 'Agent 节点'
  } else if (type === 'subflow') {
    label = '子流程'
  }

  return { id, type, label, position: { x, y }, data: { label, ...data } }
}

export function autoLayoutIfNeeded(nodes: FlowNode[], edges: FlowEdge[]): void {
  if (!nodes.length)
    return
  const needsLayout = nodes.every(n =>
    !n.position || (n.position.x === 0 && n.position.y === 0)
  )
  if (!needsLayout)
    return

  const inDeg: Record<string, number> = {}
  const adj: Record<string, string[]> = {}
  nodes.forEach(n => { inDeg[n.id] = 0; adj[n.id] = [] })
  edges.forEach(e => {
    if (adj[e.source]) {
      inDeg[e.target] = (inDeg[e.target] || 0) + 1
      adj[e.source].push(e.target)
    }
  })

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
        if (inDeg[tid] <= 0 && !assigned.has(tid)) {
          next.push(tid)
          assigned.add(tid)
        }
      }
    }
    queue = next
  }
  for (const n of nodes) {
    if (!assigned.has(n.id)) {
      (layers[layers.length - 1] ||= []).push(n.id)
    }
  }

  const LAYER_GAP = 280; const NODE_GAP = 120; const START_X = 80; const START_Y = 50
  const nodeMap = new Map(nodes.map(n => [n.id, n]))
  layers.forEach((layer, li) => {
    const x = START_X + li * LAYER_GAP
    const totalH = (layer.length - 1) * NODE_GAP
    const startY = START_Y + Math.max(0, (300 - totalH) / 2)
    layer.forEach((id, ni) => {
      const node = nodeMap.get(id)
      if (node)
        node.position = { x, y: startY + ni * NODE_GAP }
    })
  })
}

export function useWorkflowSync() {
  const saving = ref(false)
  const loading = ref(false)

  async function load(workflowId: string) {
    loading.value = true
    try {
      const res = await workflowsApi.get(workflowId)
      if (res.success)
        return res.data
      return null
    } finally {
      loading.value = false
    }
  }

  async function save(workflowId: string, nodes: FlowNode[], edges: FlowEdge[], extra: Record<string, any> = {}) {
    saving.value = true
    try {
      const res = await workflowsApi.update(workflowId, {
        nodes: toApiNodes(nodes),
        edges: toApiEdges(edges),
        ...extra
      })
      return res.success ? res.data : null
    } finally {
      saving.value = false
    }
  }

  return { saving, loading, load, save }
}
