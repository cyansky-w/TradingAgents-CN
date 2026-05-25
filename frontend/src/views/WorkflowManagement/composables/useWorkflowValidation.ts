import type { FlowNode, FlowEdge } from './useWorkflowSync'

export interface ValidationError {
  level: 'error' | 'warning'
  nodeId?: string
  message: string
  type: string
}

export function validateDag(nodes: FlowNode[], edges: FlowEdge[], currentWorkflowId?: string): ValidationError[] {
  const errors: ValidationError[] = []
  const nodeIds = new Set(nodes.map(n => n.id))

  // Check IO nodes
  const ioNodes = nodes.filter(n => n.type === 'io')
  const inputNodes = ioNodes.filter(n => n.data.io_direction === 'input')
  const outputNodes = ioNodes.filter(n => n.data.io_direction === 'output')

  if (inputNodes.length === 0) {
    errors.push({ level: 'error', message: '缺少输入 IO 节点', type: 'missing_input' })
  } else if (inputNodes.length > 1) {
    errors.push({ level: 'error', message: '只能有一个输入 IO 节点', type: 'duplicate_input' })
  }

  if (outputNodes.length === 0) {
    errors.push({ level: 'error', message: '缺少输出 IO 节点', type: 'missing_output' })
  } else if (outputNodes.length > 1) {
    errors.push({ level: 'error', message: '只能有一个输出 IO 节点', type: 'duplicate_output' })
  }

  // Check edge references
  for (const edge of edges) {
    if (!nodeIds.has(edge.source)) {
      errors.push({ level: 'error', message: `边引用了不存在的节点: ${edge.source}`, type: 'invalid_edge' })
    }
    if (!nodeIds.has(edge.target)) {
      errors.push({ level: 'error', message: `边引用了不存在的节点: ${edge.target}`, type: 'invalid_edge' })
    }
  }

  // Check cycles via DFS
  const adj = new Map<string, string[]>()
  for (const node of nodes) adj.set(node.id, [])
  for (const edge of edges) {
    if (nodeIds.has(edge.source) && nodeIds.has(edge.target)) {
      adj.get(edge.source)!.push(edge.target)
    }
  }

  const WHITE = 0, GRAY = 1, BLACK = 2
  const color = new Map<string, number>()
  for (const node of nodes) color.set(node.id, WHITE)

  function dfs(nodeId: string): boolean {
    color.set(nodeId, GRAY)
    for (const neighbor of adj.get(nodeId) || []) {
      const c = color.get(neighbor) || WHITE
      if (c === GRAY) return true
      if (c === WHITE && dfs(neighbor)) return true
    }
    color.set(nodeId, BLACK)
    return false
  }

  for (const node of nodes) {
    if (color.get(node.id) === WHITE) {
      if (dfs(node.id)) {
        errors.push({ level: 'error', message: '检测到循环依赖', type: 'cycle' })
        break
      }
    }
  }

  // Check orphan agent/subflow nodes
  const targets = new Set(edges.map(e => e.target))
  const sources = new Set(edges.map(e => e.source))
  const inputId = inputNodes[0]?.id

  for (const node of nodes) {
    if (node.type === 'agent' || node.type === 'subflow') {
      if (node.id !== inputId && !targets.has(node.id) && !sources.has(node.id)) {
        errors.push({
          level: 'warning',
          nodeId: node.id,
          message: `节点「${node.label}」未连接`,
          type: 'orphan'
        })
      }
    }
    // Agent must have agent_id
    if (node.type === 'agent' && !node.data.agent_id) {
      errors.push({
        level: 'error',
        nodeId: node.id,
        message: `Agent 节点「${node.label}」未绑定 Agent`,
        type: 'config_missing'
      })
    }
    // Subflow must have workflow_id
    if (node.type === 'subflow' && !node.data.workflow_id) {
      errors.push({
        level: 'error',
        nodeId: node.id,
        message: `子流程节点「${node.label}」未绑定工作流`,
        type: 'config_missing'
      })
    }
    // Subflow self-reference
    if (node.type === 'subflow' && node.data.workflow_id && node.data.workflow_id === currentWorkflowId) {
      errors.push({
        level: 'error',
        nodeId: node.id,
        message: `子流程节点「${node.label}」不能引用自身`,
        type: 'self_reference'
      })
    }
    // loop_over must reference a valid source
    if (node.type === 'agent' && node.data.loop_over) {
      const loopPath = node.data.loop_over as string
      const root = loopPath.split('.')[0]
      if (root === 'input' || nodeIds.has(root)) {
        // valid source
      } else {
        errors.push({
          level: 'warning',
          nodeId: node.id,
          message: `循环节点「${node.label}」的 loop_over "${loopPath}" 引用了不存在的源`,
          type: 'invalid_loop_source'
        })
      }
    }
  }

  return errors
}
