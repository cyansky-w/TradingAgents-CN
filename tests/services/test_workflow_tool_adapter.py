"""Tests for workflow-as-tool adapter in agent_service."""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestWorkflowToolAdapter:
    def test_make_workflow_invoker_calls_engine(self):
        async def _test():
            from app.services.agent_service import AgentService

            tool_meta = {
                "workflow_id": "wf123",
                "output_format": "full",
            }
            invoker = AgentService._make_workflow_invoker(tool_meta)

            mock_result = {"run_id": "r1", "output": {"report": "市场分析完成"}}

            with patch("app.workflows.engine.workflow_engine") as mock_engine:
                mock_engine.run = AsyncMock(return_value=mock_result)

                result = await invoker(date="2026-05-22", ticker="000001")

                mock_engine.run.assert_awaited_once_with(
                    workflow_id="wf123",
                    input_data={"date": "2026-05-22", "ticker": "000001"},
                    trigger_type="tool",
                )
                import json
                assert result == json.dumps({"report": "市场分析完成"}, ensure_ascii=False)

        asyncio.run(_test())

    def test_make_workflow_invoker_summary_truncates(self):
        async def _test():
            from app.services.agent_service import AgentService

            tool_meta = {
                "workflow_id": "wf456",
                "output_format": "summary",
            }
            invoker = AgentService._make_workflow_invoker(tool_meta)

            long_output = "x" * 5000
            mock_result = {"run_id": "r2", "output": long_output}

            with patch("app.workflows.engine.workflow_engine") as mock_engine:
                mock_engine.run = AsyncMock(return_value=mock_result)

                result = await invoker()
                assert len(result) == 4000
                assert result == long_output[:4000]

        asyncio.run(_test())

    def test_make_workflow_invoker_string_output(self):
        async def _test():
            from app.services.agent_service import AgentService

            tool_meta = {
                "workflow_id": "wf789",
                "output_format": "full",
            }
            invoker = AgentService._make_workflow_invoker(tool_meta)

            mock_result = {"run_id": "r3", "output": "文本结果"}

            with patch("app.workflows.engine.workflow_engine") as mock_engine:
                mock_engine.run = AsyncMock(return_value=mock_result)

                result = await invoker()
                assert result == "文本结果"

        asyncio.run(_test())
