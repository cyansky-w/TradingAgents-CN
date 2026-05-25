"""Tests for SubflowNodeExecutor."""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.workflows.nodes import SubflowNodeExecutor


class TestSubflowNodeExecutor:
    def test_subflow_calls_engine_run(self):
        async def _test():
            workflow = {}
            node = {
                "id": "sub1",
                "type": "subflow",
                "config": {
                    "workflow_id": "child_wf_id",
                    "input_mapping": {
                        "ticker": "{{input.ticker}}",
                    },
                },
            }

            mock_result = {"run_id": "run123", "output": "子工作流结果"}

            with patch("app.workflows.engine.workflow_engine") as mock_engine:
                mock_engine.run = AsyncMock(return_value=mock_result)

                executor = SubflowNodeExecutor(node, workflow, "parent_run_id")
                result = await executor({
                    "params": {"ticker": "000001"},
                    "node_outputs": {},
                    "errors": [],
                })

                mock_engine.run.assert_awaited_once_with(
                    workflow_id="child_wf_id",
                    input_data={"ticker": "000001"},
                    trigger_type="subflow",
                    parent_run_id="parent_run_id",
                )

                assert result["sender"] == "sub1"
                assert result["node_outputs"]["sub1"] == mock_result

        asyncio.run(_test())

    def test_subflow_empty_mapping(self):
        async def _test():
            workflow = {}
            node = {
                "id": "sub2",
                "type": "subflow",
                "config": {
                    "workflow_id": "child_id",
                },
            }

            with patch("app.workflows.engine.workflow_engine") as mock_engine:
                mock_engine.run = AsyncMock(return_value={"run_id": "r2", "output": "ok"})

                executor = SubflowNodeExecutor(node, workflow, "parent_run")
                result = await executor({
                    "params": {},
                    "node_outputs": {},
                    "errors": [],
                })

                mock_engine.run.assert_awaited_once_with(
                    workflow_id="child_id",
                    input_data={},
                    trigger_type="subflow",
                    parent_run_id="parent_run",
                )
                assert result["sender"] == "sub2"

        asyncio.run(_test())

    def test_subflow_engine_failure(self):
        async def _test():
            workflow = {}
            node = {
                "id": "sub_fail",
                "type": "subflow",
                "config": {"workflow_id": "bad_id"},
            }

            with patch("app.workflows.engine.workflow_engine") as mock_engine:
                mock_engine.run = AsyncMock(side_effect=ValueError("子工作流不存在"))

                executor = SubflowNodeExecutor(node, workflow, "parent_run")
                with pytest.raises(ValueError, match="子工作流不存在"):
                    await executor({
                        "params": {},
                        "node_outputs": {},
                        "errors": [],
                    })

        asyncio.run(_test())

    def test_subflow_nested_context_propagation(self):
        async def _test():
            workflow = {}
            node = {
                "id": "sub3",
                "type": "subflow",
                "config": {
                    "workflow_id": "child_id",
                    "input_mapping": {
                        "market": "{{analyzer.output}}",
                    },
                },
            }

            with patch("app.workflows.engine.workflow_engine") as mock_engine:
                mock_engine.run = AsyncMock(return_value={"run_id": "r3", "output": "deep"})

                executor = SubflowNodeExecutor(node, workflow, "p_run")
                await executor({
                    "params": {},
                    "node_outputs": {"analyzer": {"output": "市场向好"}},
                    "errors": [],
                })

                call_kwargs = mock_engine.run.call_args
                assert call_kwargs.kwargs["input_data"]["market"] == "市场向好"

        asyncio.run(_test())
