"""Tests for DAG resolver, state_utils, and engine components."""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from bson import ObjectId

from app.workflows.state_utils import (
    extract_template_vars,
    render_template,
    resolve_mapping,
    resolve_value,
)
from app.workflows.resolver import DAGResolver

VALID_OID = str(ObjectId())


# ── DAGResolver ──────────────────────────────────────────


class TestDAGResolverValidate:
    def test_valid_dag_no_errors(self):
        nodes = [
            {"id": "start", "type": "io", "config": {"io_direction": "input"}},
            {"id": "a", "type": "agent", "config": {"agent_id": VALID_OID}},
            {"id": "end", "type": "io", "config": {"io_direction": "output"}},
        ]
        edges = [
            {"id": "e1", "source": "start", "target": "a"},
            {"id": "e2", "source": "a", "target": "end"},
        ]
        errors = DAGResolver.validate(nodes, edges)
        assert errors == []

    def test_detects_cycle(self):
        nodes = [
            {"id": "start", "type": "io", "config": {"io_direction": "input"}},
            {"id": "a", "type": "agent"},
            {"id": "b", "type": "agent"},
            {"id": "end", "type": "io", "config": {"io_direction": "output"}},
        ]
        edges = [
            {"id": "e1", "source": "start", "target": "a"},
            {"id": "e2", "source": "a", "target": "b"},
            {"id": "e3", "source": "b", "target": "a"},
            {"id": "e4", "source": "b", "target": "end"},
        ]
        errors = DAGResolver.validate(nodes, edges)
        assert any("环" in e for e in errors)

    def test_missing_input_io(self):
        nodes = [
            {"id": "a", "type": "agent"},
            {"id": "end", "type": "io", "config": {"io_direction": "output"}},
        ]
        errors = DAGResolver.validate(nodes, [])
        assert any("输入" in e for e in errors)

    def test_missing_output_io(self):
        nodes = [
            {"id": "start", "type": "io", "config": {"io_direction": "input"}},
            {"id": "a", "type": "agent"},
        ]
        errors = DAGResolver.validate(nodes, [])
        assert any("输出" in e for e in errors)

    def test_duplicate_input_io(self):
        nodes = [
            {"id": "s1", "type": "io", "config": {"io_direction": "input"}},
            {"id": "s2", "type": "io", "config": {"io_direction": "input"}},
            {"id": "end", "type": "io", "config": {"io_direction": "output"}},
        ]
        errors = DAGResolver.validate(nodes, [])
        assert any("一个" in e for e in errors)

    def test_orphan_agent_node(self):
        nodes = [
            {"id": "start", "type": "io", "config": {"io_direction": "input"}},
            {"id": "end", "type": "io", "config": {"io_direction": "output"}},
            {"id": "lonely", "type": "agent", "label": "孤立"},
        ]
        errors = DAGResolver.validate(nodes, [
            {"id": "e1", "source": "start", "target": "end"},
        ])
        assert any("孤立" in e for e in errors)

    def test_invalid_edge_source(self):
        nodes = [
            {"id": "start", "type": "io", "config": {"io_direction": "input"}},
            {"id": "end", "type": "io", "config": {"io_direction": "output"}},
        ]
        errors = DAGResolver.validate(nodes, [
            {"id": "e1", "source": "missing", "target": "end"},
        ])
        assert any("source" in e for e in errors)


class TestDAGResolverTopologicalSort:
    def test_linear_dag(self):
        nodes = [
            {"id": "start", "type": "io"},
            {"id": "a", "type": "agent"},
            {"id": "end", "type": "io"},
        ]
        edges = [
            {"source": "start", "target": "a"},
            {"source": "a", "target": "end"},
        ]
        layers = DAGResolver.topological_sort(nodes, edges)
        assert layers == [["start"], ["a"], ["end"]]

    def test_parallel_dag(self):
        nodes = [
            {"id": "start", "type": "io"},
            {"id": "a", "type": "agent"},
            {"id": "b", "type": "agent"},
            {"id": "end", "type": "io"},
        ]
        edges = [
            {"source": "start", "target": "a"},
            {"source": "start", "target": "b"},
            {"source": "a", "target": "end"},
            {"source": "b", "target": "end"},
        ]
        layers = DAGResolver.topological_sort(nodes, edges)
        assert layers[0] == ["start"]
        assert sorted(layers[1]) == ["a", "b"]
        assert layers[2] == ["end"]


class TestDAGResolverFindNodes:
    def test_find_entry_node(self):
        nodes = [
            {"id": "start", "type": "io", "config": {"io_direction": "input"}},
            {"id": "end", "type": "io", "config": {"io_direction": "output"}},
        ]
        assert DAGResolver.find_entry_node(nodes) == "start"

    def test_find_entry_node_missing(self):
        with pytest.raises(ValueError, match="未找到"):
            DAGResolver.find_entry_node([])

    def test_find_exit_node(self):
        nodes = [
            {"id": "start", "type": "io", "config": {"io_direction": "input"}},
            {"id": "end", "type": "io", "config": {"io_direction": "output"}},
        ]
        assert DAGResolver.find_exit_node(nodes) == "end"


# ── state_utils ──────────────────────────────────────────


class TestStateUtils:
    def test_render_template_simple(self):
        state = {"params": {"date": "2026-05-22", "symbols": ["000001"]}}
        result = render_template(state, "请分析 {{input.date}} 的市场")
        assert result == "请分析 2026-05-22 的市场"

    def test_resolve_mapping(self):
        state = {
            "params": {"ticker": "000001"},
            "node_outputs": {"analyzer": {"output": "市场向好"}},
        }
        mapping = {
            "ticker": "{{input.ticker}}",
            "report": "{{analyzer.output}}",
        }
        resolved = resolve_mapping(state, mapping)
        assert resolved["ticker"] == "000001"
        assert resolved["report"] == "市场向好"

    def test_resolve_value_node_output(self):
        state = {"node_outputs": {"node1": {"result": "ok"}}}
        assert resolve_value(state, "node1.result") == "ok"

    def test_resolve_value_input_path(self):
        state = {"params": {"date": "2026-05-22"}}
        assert resolve_value(state, "input.date") == "2026-05-22"

    def test_resolve_value_nested(self):
        state = {"params": {"data": {"price": 10.5}}}
        assert resolve_value(state, "input.data.price") == 10.5

    def test_resolve_value_item(self):
        state = {"_loop_item": {"symbol": "600519"}}
        assert resolve_value(state, "item.symbol") == "600519"

    def test_extract_template_vars(self):
        result = extract_template_vars("分析 {{stock}} 在 {{date}} 的走势，{{stock}} 再次出现")
        assert result == ["stock", "date"]

    def test_extract_template_vars_no_match(self):
        assert extract_template_vars("无模板变量") == []


# ── IO Node Executors ─────────────────────────────────────


class TestInputIONodeExecutor:
    def test_input_node_sets_output(self):
        async def _test():
            from app.workflows.nodes import InputIONodeExecutor

            workflow = {"message_template": "分析 {{input.date}}"}
            node = {"id": "start", "type": "io", "config": {"io_direction": "input"}}
            executor = InputIONodeExecutor(node, workflow, "run1")
            result = await executor({
                "params": {"date": "2026-05-22"},
                "node_outputs": {},
                "errors": [],
            })
            assert result["sender"] == "start"
            assert result["node_outputs"]["start"]["output"] == {"date": "2026-05-22"}
            assert len(result["messages"]) == 1
            assert "2026-05-22" in result["messages"][0].content

        asyncio.run(_test())


class TestOutputIONodeExecutor:
    def test_output_node_extracts_final(self):
        async def _test():
            from app.workflows.nodes import OutputIONodeExecutor

            workflow = {"output_template": "{{summary.output}}"}
            node = {"id": "end", "type": "io", "config": {"io_direction": "output"}}
            executor = OutputIONodeExecutor(node, workflow, "run1")
            result = await executor({
                "params": {},
                "node_outputs": {"summary": {"output": "最终报告"}},
                "errors": [],
            })
            assert result["sender"] == "end"
            assert result["node_outputs"]["end"]["output"] == "最终报告"

        asyncio.run(_test())

    def test_output_node_no_template(self):
        async def _test():
            from app.workflows.nodes import OutputIONodeExecutor

            workflow = {}
            node = {"id": "end", "type": "io", "config": {"io_direction": "output"}}
            executor = OutputIONodeExecutor(node, workflow, "run1")
            result = await executor({
                "params": {},
                "node_outputs": {"a": {"output": "hello"}},
                "errors": [],
            })
            assert result["node_outputs"]["end"]["output"] == {"a": {"output": "hello"}}

        asyncio.run(_test())
