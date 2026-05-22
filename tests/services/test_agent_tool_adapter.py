"""Tests for the Agent tool adapter."""
import asyncio

import pytest

from app.services.agent_tool_adapter import build_args_schema, wrap_as_base_tool


def test_build_args_schema_maps_tool_parameters():
    schema = build_args_schema("sample_tool", [
        {"name": "ticker", "type": "string", "required": True, "description": "股票代码"},
        {"name": "look_back_days", "type": "integer", "required": False, "default": 30, "description": "回看天数"},
    ])

    fields = schema.model_fields
    assert "ticker" in fields
    assert "look_back_days" in fields
    assert fields["look_back_days"].default == 30


def test_build_args_schema_accepts_empty_parameters():
    schema = build_args_schema("no_args_tool", [])

    assert schema.__name__.endswith("Args")
    assert schema.model_fields == {}


def test_wrap_as_base_tool_invokes_sync_handler():
    def handler(ticker: str):
        return f"data:{ticker}"

    tool = wrap_as_base_tool(handler, {
        "code": "get_data",
        "name": "获取数据",
        "description": "获取股票数据",
        "parameters": [{"name": "ticker", "type": "string", "required": True, "description": "股票代码"}],
    })

    assert tool.name == "get_data"
    assert tool.description == "获取股票数据"
    assert tool.invoke({"ticker": "000001"}) == "data:000001"


@pytest.mark.asyncio
async def test_wrap_as_base_tool_invokes_async_handler():
    async def handler(ticker: str):
        return f"async:{ticker}"

    tool = wrap_as_base_tool(handler, {
        "code": "get_data_async",
        "name": "获取数据异步",
        "description": "异步获取股票数据",
        "parameters": [{"name": "ticker", "type": "string", "required": True, "description": "股票代码"}],
    })

    assert await tool.ainvoke({"ticker": "000001"}) == "async:000001"


@pytest.mark.asyncio
async def test_wrap_as_base_tool_retries_async_handler_once_when_enabled():
    calls = {"count": 0}

    async def handler(symbol: str):
        calls["count"] += 1
        if calls["count"] == 1:
            raise RuntimeError("temporary")
        return f"ok:{symbol}"

    tool = wrap_as_base_tool(
        handler,
        {
            "code": "flaky_async_tool",
            "name": "波动异步工具",
            "description": "测试重试",
            "parameters": [{"name": "symbol", "type": "string", "required": True, "description": "股票代码"}],
        },
        retry_on_failure=True,
    )

    assert await tool.ainvoke({"symbol": "000001"}) == "ok:000001"
    assert calls["count"] == 2


@pytest.mark.asyncio
async def test_wrap_as_base_tool_raises_after_second_async_failure_when_enabled():
    calls = {"count": 0}

    async def handler(symbol: str):
        calls["count"] += 1
        raise RuntimeError(f"failed:{calls['count']}")

    tool = wrap_as_base_tool(
        handler,
        {
            "code": "always_fail_async_tool",
            "name": "总是失败异步工具",
            "description": "测试重试失败",
            "parameters": [{"name": "symbol", "type": "string", "required": True, "description": "股票代码"}],
        },
        retry_on_failure=True,
    )

    with pytest.raises(RuntimeError, match="failed:2"):
        await tool.ainvoke({"symbol": "000001"})
    assert calls["count"] == 2


def test_wrap_as_base_tool_retries_sync_handler_once_when_enabled():
    calls = {"count": 0}

    def handler(symbol: str):
        calls["count"] += 1
        if calls["count"] == 1:
            raise RuntimeError("temporary")
        return f"ok:{symbol}"

    tool = wrap_as_base_tool(
        handler,
        {
            "code": "flaky_sync_tool",
            "name": "波动同步工具",
            "description": "测试同步重试",
            "parameters": [{"name": "symbol", "type": "string", "required": True, "description": "股票代码"}],
        },
        retry_on_failure=True,
    )

    assert tool.invoke({"symbol": "000001"}) == "ok:000001"
    assert calls["count"] == 2


def test_wrap_as_base_tool_sync_invoke_rejects_async_handler_without_retrying():
    calls = {"count": 0}

    async def async_handler(symbol: str):
        return f"async:{symbol}"

    def handler(symbol: str):
        calls["count"] += 1
        return async_handler(symbol)

    tool = wrap_as_base_tool(
        handler,
        {
            "code": "async_tool_via_sync_invoke",
            "name": "同步调用异步工具",
            "description": "测试同步校验不重试",
            "parameters": [{"name": "symbol", "type": "string", "required": True, "description": "股票代码"}],
        },
        retry_on_failure=True,
    )

    with pytest.raises(RuntimeError, match="use ainvoke"):
        tool.invoke({"symbol": "000001"})
    assert calls["count"] == 1
