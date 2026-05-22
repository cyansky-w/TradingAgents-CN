"""
Agent runtime tool adapter.

Wrap (handler callable, tool metadata dict) into a LangChain BaseTool that
the LangGraph ReAct agent can dispatch to.
"""
from __future__ import annotations

import inspect
from typing import Any, Callable, Dict, List, Type

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field, create_model


_TYPE_MAP = {
    "string": str,
    "integer": int,
    "number": float,
    "boolean": bool,
    "array": list,
    "object": dict,
}


def _safe_class_name(tool_code: str) -> str:
    parts = [p for p in tool_code.replace("-", "_").split("_") if p]
    if not parts:
        return "AgentToolArgs"
    return "".join(part[:1].upper() + part[1:] for part in parts) + "Args"


def build_args_schema(tool_code: str, parameters: List[Dict[str, Any]]) -> Type[BaseModel]:
    fields: Dict[str, Any] = {}
    for param in parameters or []:
        name = param.get("name", "")
        if not name:
            continue
        py_type = _TYPE_MAP.get(param.get("type", "string"), str)
        description = param.get("description") or ""
        required = param.get("required", True)
        default = ... if required else param.get("default", None)
        fields[name] = (py_type, Field(default, description=description))

    if not fields:
        # StructuredTool requires a schema; provide an empty one.
        return create_model(_safe_class_name(tool_code))

    return create_model(_safe_class_name(tool_code), **fields)


def wrap_as_base_tool(
    handler: Callable,
    tool_meta: Dict[str, Any],
    retry_on_failure: bool = False,
) -> StructuredTool:
    from langchain_core.tools import BaseTool

    # handler 可能已经是 BaseTool（如 @tool 装饰的 Toolkit 方法），直接返回
    if isinstance(handler, BaseTool):
        return handler

    tool_code = tool_meta.get("code") or tool_meta.get("name") or getattr(handler, "name", "agent_tool")
    description = tool_meta.get("description") or tool_meta.get("name") or tool_code
    args_schema = build_args_schema(tool_code, tool_meta.get("parameters", []))

    async def coroutine(**kwargs):
        try:
            result = handler(**kwargs)
            if inspect.isawaitable(result):
                return await result
            return result
        except Exception:
            if not retry_on_failure:
                raise
            result = handler(**kwargs)
            if inspect.isawaitable(result):
                return await result
            return result

    def func(**kwargs):
        try:
            result = handler(**kwargs)
        except Exception:
            if not retry_on_failure:
                raise
            result = handler(**kwargs)
        if inspect.isawaitable(result):
            if inspect.iscoroutine(result):
                result.close()
            raise RuntimeError(f"Tool '{tool_code}' is async; use ainvoke")
        return result

    return StructuredTool.from_function(
        func=func,
        coroutine=coroutine,
        name=tool_code,
        description=description,
        args_schema=args_schema,
    )
