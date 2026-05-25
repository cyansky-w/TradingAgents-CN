"""
节点执行器 — InputIO / OutputIO / Agent / Subflow
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable, Dict, List, Optional, Tuple

from app.workflows.state_utils import render_template, resolve_mapping, resolve_value

logger = logging.getLogger(__name__)


class InputIONodeExecutor:
    """工作流入口节点。"""

    def __init__(self, node, workflow, run_id, on_complete=None):
        self.node = node
        self.workflow = workflow
        self.node_id = node["id"]
        self.run_id = run_id
        self.on_complete = on_complete

    async def __call__(self, state: Dict[str, Any]) -> Dict[str, Any]:
        input_data = state.get("params", {})

        message_template = self.workflow.get("message_template", "")
        if message_template:
            rendered = render_template(state, message_template)
        else:
            rendered = str(input_data)

        from langchain_core.messages import HumanMessage

        result = {
            "params": input_data,
            "messages": [HumanMessage(content=rendered)],
            "node_outputs": {self.node_id: {"output": input_data}},
            "sender": self.node_id,
            "iterations": state.get("iterations", 0),
            "errors": [],
        }

        if self.on_complete:
            await self.on_complete(
                self.run_id, self.node_id, "completed",
                output=input_data,
            )

        return result


class OutputIONodeExecutor:
    """工作流出口节点。"""

    def __init__(self, node, workflow, run_id, on_complete=None):
        self.node = node
        self.workflow = workflow
        self.node_id = node["id"]
        self.run_id = run_id
        self.on_complete = on_complete

    async def __call__(self, state: Dict[str, Any]) -> Dict[str, Any]:
        output_template = self.workflow.get("output_template")

        if output_template:
            output = render_template(state, output_template)
        else:
            output = dict(state.get("node_outputs", {}))

        result = {
            "node_outputs": {self.node_id: {"output": output}},
            "sender": self.node_id,
            "iterations": state.get("iterations", 0),
            "errors": [],
        }

        if self.on_complete:
            await self.on_complete(
                self.run_id, self.node_id, "completed",
                output=output,
            )

        return result


class AgentNodeExecutor:
    """执行单个 Agent 节点，内部复用 create_react_agent。"""

    def __init__(self, node, workflow, run_id, on_complete=None):
        self.node = node
        self.workflow = workflow
        self.node_id = node["id"]
        self.run_id = run_id
        self.on_complete = on_complete

    async def __call__(self, state: Dict[str, Any]) -> Dict[str, Any]:
        config = self.node.get("config", {})
        agent_id = config.get("agent_id", "")

        if config.get("loop_over"):
            output, ai_messages = await self._execute_loop(state, agent_id, config)
        else:
            mapping = config.get("input_mapping", {})
            variables = resolve_mapping(state, mapping) if mapping else dict(state.get("params", {}))
            output, ai_messages = await self._execute_single(state, agent_id, variables)

        result = {
            "node_outputs": {self.node_id: {"output": output}},
            "messages": ai_messages,
            "sender": self.node_id,
            "iterations": state.get("iterations", 0),
            "errors": [],
        }

        if self.on_complete:
            await self.on_complete(self.run_id, self.node_id, "completed", output=output)

        return result

    async def _execute_single(
        self, state: Dict[str, Any], agent_id: str, variables: Dict[str, Any]
    ) -> Tuple[str, list]:
        """执行单个 Agent 调用，返回 (output, ai_messages)。"""
        from langchain_core.messages import HumanMessage, SystemMessage

        from app.services.agent_service import agent_service

        spec = await agent_service.build_agent(agent_id, variables)

        if spec.message_template:
            human_content = render_template(state, spec.message_template)
        else:
            human_content = self._params_to_message(variables)

        messages = [
            SystemMessage(content=spec.system_prompt),
            HumanMessage(content=human_content),
        ]

        if spec.tools:
            from langgraph.prebuilt import create_react_agent

            react_agent = create_react_agent(spec.llm, spec.tools)
            react_result = await react_agent.ainvoke(
                {"messages": messages},
                config={"recursion_limit": spec.parameters.max_tool_calls},
            )
            output = self._extract_output(react_result)
            ai_messages = react_result.get("messages", [])
        else:
            response = await spec.llm.ainvoke(messages)
            output = response.content
            ai_messages = [response]

        await agent_service.record_usage(agent_id)
        return output, ai_messages

    async def _execute_loop(
        self, state, agent_id, config
    ) -> Tuple[Any, list]:
        """并行或串行执行循环体。"""
        loop_path = config.get("loop_over", "")
        loop_source = resolve_value(state, loop_path)

        if not isinstance(loop_source, list):
            logger.warning(f"loop_over for {self.node_id} did not resolve to a list")
            return None, []

        parallel = config.get("parallel", False)
        max_concurrency = config.get("max_concurrency", 3)
        base_mapping = config.get("input_mapping", {})
        base_variables = resolve_mapping(state, base_mapping) if base_mapping else {}

        async def run_single(item):
            loop_state = {**state, "_loop_item": item}
            loop_vars = {**base_variables, "item": item}
            return await self._execute_single(loop_state, agent_id, loop_vars)

        all_ai_messages: list = []
        outputs: list = []

        if parallel:
            semaphore = asyncio.Semaphore(max_concurrency)

            async def run_with_sem(item):
                async with semaphore:
                    return await run_single(item)

            results = await asyncio.gather(*[run_with_sem(item) for item in loop_source])
            for output, msgs in results:
                outputs.append(output)
                all_ai_messages.extend(msgs)
        else:
            for item in loop_source:
                output, msgs = await run_single(item)
                outputs.append(output)
                all_ai_messages.extend(msgs)

        return outputs, all_ai_messages

    @staticmethod
    def _extract_output(result: Dict[str, Any]) -> str:
        from langchain_core.messages import AIMessage

        messages = result.get("messages", [])
        ai_msgs = [
            m for m in messages
            if isinstance(m, AIMessage) and not getattr(m, "tool_calls", None)
        ]
        return ai_msgs[-1].content if ai_msgs else ""

    @staticmethod
    def _params_to_message(params: Dict[str, Any]) -> str:
        """当 Agent 无 message_template 时，将参数拼接为自然语言。"""
        if not params:
            return "请执行任务"
        parts = [f"{k}: {v}" for k, v in params.items() if v is not None]
        return "\n".join(parts)


class SubflowNodeExecutor:
    """嵌套子工作流节点，递归调用 WorkflowEngine。"""

    def __init__(self, node, workflow, run_id, on_complete=None):
        self.node = node
        self.workflow = workflow
        self.node_id = node["id"]
        self.run_id = run_id
        self.on_complete = on_complete

    async def __call__(self, state: Dict[str, Any]) -> Dict[str, Any]:
        config = self.node.get("config", {})
        workflow_id = config.get("workflow_id", "")
        mapping = config.get("input_mapping", {})
        variables = resolve_mapping(state, mapping) if mapping else {}

        from app.workflows.engine import workflow_engine

        sub_result = await workflow_engine.run(
            workflow_id=workflow_id,
            input_data=variables,
            trigger_type="subflow",
            parent_run_id=self.run_id,
        )

        result = {
            "node_outputs": {self.node_id: sub_result},
            "sender": self.node_id,
            "iterations": state.get("iterations", 0),
            "errors": [],
        }

        if self.on_complete:
            await self.on_complete(self.run_id, self.node_id, "completed", output=sub_result)

        return result
