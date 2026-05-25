"""
GraphBuilder — 从工作流文档动态构建 LangGraph StateGraph
"""
from __future__ import annotations

import logging
import operator
from typing import Annotated, Any, Callable, Dict, List, Optional, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages

from app.workflows.nodes import (
    AgentNodeExecutor,
    InputIONodeExecutor,
    OutputIONodeExecutor,
    SubflowNodeExecutor,
)
from app.workflows.resolver import DAGResolver

logger = logging.getLogger(__name__)


def dict_merge(left: Dict[str, Any], right: Dict[str, Any]) -> Dict[str, Any]:
    """Reducer: 合并两个 dict，right 覆盖 left 的同名 key。"""
    merged = {**left}
    merged.update(right)
    return merged


class WorkflowState(TypedDict):
    messages: Annotated[list, add_messages]
    params: Dict[str, Any]
    node_outputs: Annotated[Dict[str, Any], dict_merge]
    errors: Annotated[List[str], operator.add]
    iterations: int
    sender: str


class GraphBuilder:
    """从 MongoDB 工作流文档动态构建 LangGraph StateGraph。"""

    def __init__(
        self,
        workflow_doc: Dict[str, Any],
        run_id: str,
        on_node_complete: Optional[Callable] = None,
    ):
        self.workflow = workflow_doc
        self.run_id = run_id
        self.on_node_complete = on_node_complete
        self.nodes = workflow_doc.get("nodes", [])
        self.edges = workflow_doc.get("edges", [])

    async def build(self):
        """构建并编译 StateGraph。"""
        graph = StateGraph(WorkflowState)

        for node in self.nodes:
            executor = self._create_node_executor(node)
            graph.add_node(node["id"], executor)

        for edge in self.edges:
            graph.add_edge(edge["source"], edge["target"])

        try:
            entry = DAGResolver.find_entry_node(self.nodes)
            graph.add_edge(START, entry)
        except ValueError:
            logger.warning(f"Workflow {self.workflow.get('code')}: no entry node found")

        try:
            exit_node = DAGResolver.find_exit_node(self.nodes)
            graph.add_edge(exit_node, END)
        except ValueError:
            logger.warning(f"Workflow {self.workflow.get('code')}: no exit node found")

        return graph.compile()

    def _create_node_executor(self, node: Dict[str, Any]) -> Callable:
        node_type = node.get("type", "io")
        cb = self.on_node_complete

        if node_type == "agent":
            return AgentNodeExecutor(node, self.workflow, self.run_id, on_complete=cb)
        elif node_type == "subflow":
            return SubflowNodeExecutor(node, self.workflow, self.run_id, on_complete=cb)
        elif node_type == "io":
            direction = node.get("config", {}).get("io_direction", "input")
            if direction == "input":
                return InputIONodeExecutor(node, self.workflow, self.run_id, on_complete=cb)
            else:
                return OutputIONodeExecutor(node, self.workflow, self.run_id, on_complete=cb)
        else:
            logger.warning(f"Unknown node type: {node_type}, falling back to IO")
            return InputIONodeExecutor(node, self.workflow, self.run_id, on_complete=cb)
