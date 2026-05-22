"""
Agent 管理 API
"""
import asyncio
import json
import logging
from typing import Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse

from app.core.response import ok
from app.models.agents import AgentCreate, AgentUpdate
from app.routers.auth_db import get_current_user
from app.services.agent_service import agent_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/agents", tags=["Agent 管理"])


def _agent_error_status(message: str, default: int = 400) -> int:
    if "不存在" in message:
        return 404
    if "不能删除" in message:
        return 403
    if "无效" in message:
        return 400
    return default


@router.get("/")
async def list_agents(
    search: Optional[str] = Query(None, description="搜索关键词（name/code/description）"),
    tag: Optional[str] = Query(None, description="标签筛选"),
    enabled: Optional[bool] = Query(None, description="启用状态"),
    is_chat: Optional[bool] = Query(None, description="聊天助手类型"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
):
    try:
        agents, total = await agent_service.list_agents(
            search=search,
            tag=tag,
            enabled=enabled,
            is_chat=is_chat,
            page=page,
            page_size=page_size,
        )
        return ok({"items": agents, "total": total, "page": page, "page_size": page_size})
    except Exception as exc:  # noqa: BLE001
        logger.exception(f"List agents failed: {exc}")
        raise HTTPException(status_code=500, detail=f"获取 Agent 列表失败: {exc}")


@router.get("/tags")
async def get_all_tags(current_user: dict = Depends(get_current_user)):
    try:
        return ok(await agent_service.get_all_tags())
    except Exception as exc:  # noqa: BLE001
        logger.exception(f"Get agent tags failed: {exc}")
        raise HTTPException(status_code=500, detail=f"获取标签失败: {exc}")


@router.get("/models")
async def get_available_models(current_user: dict = Depends(get_current_user)):
    """返回前端模型选择器使用的厂家列表（含 api_key 状态和模型目录）。"""
    try:
        from app.services.config_service import ConfigService

        config_service = ConfigService()
        providers = await config_service.get_llm_providers()
        catalogs = await config_service.get_model_catalog()
        catalog_map = {c.provider: [m.name for m in c.models] for c in catalogs}
        return ok([
            {
                "name": p.name,
                "display_name": p.display_name or p.name,
                "default_base_url": p.default_base_url or "",
                "default_models": catalog_map.get(p.name, []),
                "has_api_key": bool(p.api_key),
            }
            for p in providers
        ])
    except Exception as exc:  # noqa: BLE001
        logger.exception(f"Get available models failed: {exc}")
        raise HTTPException(status_code=500, detail=f"获取模型列表失败: {exc}")


@router.get("/{agent_id}")
async def get_agent(agent_id: str, current_user: dict = Depends(get_current_user)):
    try:
        agent = await agent_service.get_agent(agent_id)
        if not agent:
            raise HTTPException(status_code=404, detail="Agent 不存在")
        return ok(agent)
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=_agent_error_status(str(exc)), detail=str(exc))
    except Exception as exc:  # noqa: BLE001
        logger.exception(f"Get agent failed: {exc}")
        raise HTTPException(status_code=500, detail=f"获取 Agent 详情失败: {exc}")


@router.post("/")
async def create_agent(payload: AgentCreate, current_user: dict = Depends(get_current_user)):
    try:
        data = payload.model_dump(exclude_none=True, by_alias=False)
        agent = await agent_service.create_agent(data)
        return ok(agent, "创建成功")
    except ValueError as exc:
        raise HTTPException(status_code=_agent_error_status(str(exc)), detail=str(exc))
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.exception(f"Create agent failed: {exc}")
        raise HTTPException(status_code=500, detail=f"创建 Agent 失败: {exc}")


@router.put("/{agent_id}")
async def update_agent(
    agent_id: str,
    payload: AgentUpdate,
    current_user: dict = Depends(get_current_user),
):
    try:
        data = payload.model_dump(exclude_unset=True, by_alias=False)
        if not data:
            raise HTTPException(status_code=400, detail="无更新字段")
        agent = await agent_service.update_agent(agent_id, data)
        return ok(agent, "更新成功")
    except ValueError as exc:
        raise HTTPException(status_code=_agent_error_status(str(exc)), detail=str(exc))
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.exception(f"Update agent failed: {exc}")
        raise HTTPException(status_code=500, detail=f"更新 Agent 失败: {exc}")


@router.delete("/{agent_id}")
async def delete_agent(agent_id: str, current_user: dict = Depends(get_current_user)):
    try:
        success = await agent_service.delete_agent(agent_id)
        if not success:
            raise HTTPException(status_code=404, detail="Agent 不存在")
        return ok({"id": agent_id}, "删除成功")
    except ValueError as exc:
        raise HTTPException(status_code=_agent_error_status(str(exc)), detail=str(exc))
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.exception(f"Delete agent failed: {exc}")
        raise HTTPException(status_code=500, detail=f"删除 Agent 失败: {exc}")


@router.put("/{agent_id}/toggle")
async def toggle_agent(
    agent_id: str,
    payload: dict = Body(...),
    current_user: dict = Depends(get_current_user),
):
    try:
        enabled = payload.get("enabled")
        if enabled is None:
            raise HTTPException(status_code=400, detail="缺少 enabled 字段")
        success = await agent_service.toggle_agent(agent_id, bool(enabled))
        if not success:
            raise HTTPException(status_code=404, detail="Agent 不存在")
        return ok({"id": agent_id, "enabled": bool(enabled)}, "状态更新成功")
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.exception(f"Toggle agent failed: {exc}")
        raise HTTPException(status_code=500, detail=f"切换状态失败: {exc}")


# ── Test run (SSE) ──────────────────────────────────────────────


async def _agent_test_run_events(agent_id: str, payload: dict):
    """SSE 事件生成器：token / tool_call / tool_result / done / error。"""
    try:
        from langchain_core.messages import HumanMessage, SystemMessage

        spec = await agent_service.build_agent(agent_id, payload.get("variables") or {})
        messages = [
            SystemMessage(content=spec.system_prompt),
            HumanMessage(content=payload.get("message", "")),
        ]

        async def _stream_events():
            if spec.tools:
                from langchain_core.messages import AIMessage, ToolMessage
                from langgraph.prebuilt import create_react_agent

                agent = create_react_agent(spec.llm, spec.tools)
                stream_config = {"recursion_limit": spec.parameters.max_tool_calls}
                async for chunk in agent.astream(
                    {"messages": messages},
                    stream_mode="messages",
                    config=stream_config,
                ):
                    msg = chunk[0] if isinstance(chunk, tuple) else chunk

                    if isinstance(msg, AIMessage) and getattr(msg, "tool_calls", None):
                        for tc in msg.tool_calls:
                            if not tc.get("name"):
                                continue
                            yield (
                                f"event: tool_call\n"
                                f"data: {json.dumps({'name': tc.get('name'), 'args': tc.get('args', {}), 'id': tc.get('id', '')}, ensure_ascii=False)}\n\n"
                            )

                    if isinstance(msg, ToolMessage):
                        yield (
                            f"event: tool_result\n"
                            f"data: {json.dumps({'name': getattr(msg, 'name', '') or 'unknown', 'content': str(getattr(msg, 'content', ''))}, ensure_ascii=False)}\n\n"
                        )

                    content = getattr(msg, "content", "")
                    if content and isinstance(content, str):
                        yield (
                            f"event: token\n"
                            f"data: {json.dumps({'content': content}, ensure_ascii=False)}\n\n"
                        )
            else:
                async for chunk in spec.llm.astream(messages):
                    content = getattr(chunk, "content", "") if hasattr(chunk, "content") else str(chunk)
                    if content:
                        yield (
                            f"event: token\n"
                            f"data: {json.dumps({'content': content}, ensure_ascii=False)}\n\n"
                        )

        timeout = getattr(spec.parameters, "timeout", None)
        if timeout:
            try:
                async def _collect():
                    async for event in _stream_events():
                        yield event
                # Python 3.10 compatible timeout
                gen = _collect()
                while True:
                    try:
                        event = await asyncio.wait_for(gen.__anext__(), timeout=timeout)
                        yield event
                    except StopAsyncIteration:
                        break
            except asyncio.TimeoutError:
                yield (
                    f"event: error\n"
                    f"data: {json.dumps({'message': f'Agent test run timed out after {timeout} seconds'}, ensure_ascii=False)}\n\n"
                )
                return
        else:
            async for event in _stream_events():
                yield event

        await agent_service.record_usage(agent_id)
        yield (
            f"event: done\n"
            f"data: {json.dumps({'agent_code': spec.agent_code}, ensure_ascii=False)}\n\n"
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("Agent test run failed")
        yield (
            f"event: error\n"
            f"data: {json.dumps({'message': str(exc)}, ensure_ascii=False)}\n\n"
        )


@router.post("/{agent_id}/test-run")
async def test_run_agent(
    agent_id: str,
    payload: dict = Body(...),
    current_user: dict = Depends(get_current_user),
):
    if not payload.get("message"):
        raise HTTPException(status_code=400, detail="缺少 message 字段")
    return StreamingResponse(
        _agent_test_run_events(agent_id, payload),
        media_type="text/event-stream",
    )


@router.post("/seed")
async def seed_agents(current_user: dict = Depends(get_current_user)):
    try:
        from app.agents.seed_agents import seed_agents_to_db

        result = await seed_agents_to_db()
        return ok(result, "Agent 数据初始化完成")
    except Exception as exc:  # noqa: BLE001
        logger.exception(f"Seed agents failed: {exc}")
        raise HTTPException(status_code=500, detail=f"初始化 Agent 数据失败: {exc}")


@router.post("/seed-test-data")
async def seed_test_data(current_user: dict = Depends(get_current_user)):
    try:
        from app.agents.seed_test_data import seed_test_data as _seed

        result = await _seed()
        return ok(result, "测试数据初始化完成")
    except Exception as exc:  # noqa: BLE001
        logger.exception(f"Seed test data failed: {exc}")
        raise HTTPException(status_code=500, detail=f"初始化测试数据失败: {exc}")
