"""
工具管理 API
"""
import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from app.models.tools import ToolCreate, ToolUpdate, ToolUpdateExtended
from app.routers.auth_db import get_current_user
from app.core.response import ok
from app.services.tool_service import tool_service
from app.tools.handler_map import HANDLER_MAP

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/tools", tags=["工具管理"])


@router.get("/")
async def list_tools(
    type: Optional[str] = Query(None, description="工具类型: builtin/rpc/remote"),
    enabled: Optional[bool] = Query(None, description="启用状态"),
    tag: Optional[str] = Query(None, description="标签筛选"),
    search: Optional[str] = Query(None, description="搜索关键词"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
):
    try:
        tools, total = await tool_service.list_tools(tool_type=type, enabled=enabled, tag=tag, search=search, page=page, page_size=page_size)
        return ok({"items": tools, "total": total, "page": page, "page_size": page_size})
    except Exception as e:
        logger.exception(f"List tools failed: {e}")
        raise HTTPException(status_code=500, detail=f"获取工具列表失败: {e}")


@router.get("/tags")
async def get_all_tags(current_user: dict = Depends(get_current_user)):
    try:
        tags = await tool_service.get_all_tags()
        return ok(tags)
    except Exception as e:
        logger.exception(f"Get tags failed: {e}")
        raise HTTPException(status_code=500, detail=f"获取标签失败: {e}")


@router.get("/{tool_id}")
async def get_tool(tool_id: str, current_user: dict = Depends(get_current_user)):
    try:
        tool = await tool_service.get_tool(tool_id)
        if not tool:
            raise HTTPException(status_code=404, detail="工具不存在")
        return ok(tool)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Get tool failed: {e}")
        raise HTTPException(status_code=500, detail=f"获取工具详情失败: {e}")


@router.post("/")
async def create_tool(payload: ToolCreate, current_user: dict = Depends(get_current_user)):
    try:
        data = payload.model_dump(exclude_none=True)
        if data["type"] == "builtin":
            if not data.get("handler"):
                raise HTTPException(status_code=400, detail="builtin 工具必须指定 handler")
            if data["handler"] not in HANDLER_MAP:
                raise HTTPException(status_code=400, detail=f"Handler '{data['handler']}' 不存在于 HANDLER_MAP 中")
        elif data["type"] in ("rpc", "remote"):
            if not data.get("endpoint_url"):
                raise HTTPException(status_code=400, detail="rpc/remote 工具必须指定 endpoint_url")
        elif data["type"] == "workflow":
            if not data.get("workflow_id"):
                raise HTTPException(status_code=400, detail="workflow 工具必须指定 workflow_id")
        existing_code = await tool_service.get_tool_by_code(data["code"])
        if existing_code:
            raise HTTPException(status_code=400, detail=f"工具编码 '{data['code']}' 已存在")
        existing_name = await tool_service.get_tool_by_name(data["name"])
        if existing_name:
            raise HTTPException(status_code=400, detail=f"工具名称 '{data['name']}' 已存在")
        tool = await tool_service.create_tool(data)
        return ok(tool, "创建成功")
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Create tool failed: {e}")
        raise HTTPException(status_code=500, detail=f"创建工具失败: {e}")


@router.put("/{tool_id}")
async def update_tool(tool_id: str, payload: ToolUpdateExtended, current_user: dict = Depends(get_current_user)):
    try:
        existing = await tool_service.get_tool(tool_id)
        if not existing:
            raise HTTPException(status_code=404, detail="工具不存在")
        tool_type = existing.get("type", "builtin")
        if tool_type == "builtin":
            update_data = ToolUpdate(**payload.model_dump(exclude_none=True))
        else:
            update_data = payload
        data = update_data.model_dump(exclude_none=True)
        if not data:
            return ok({"id": tool_id}, "无变更")
        success = await tool_service.update_tool(tool_id, data)
        if not success:
            raise HTTPException(status_code=404, detail="工具不存在")
        return ok({"id": tool_id}, "更新成功")
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Update tool failed: {e}")
        raise HTTPException(status_code=500, detail=f"更新工具失败: {e}")


@router.delete("/{tool_id}")
async def delete_tool(tool_id: str, current_user: dict = Depends(get_current_user)):
    try:
        success = await tool_service.delete_tool(tool_id)
        if not success:
            raise HTTPException(status_code=404, detail="工具不存在")
        return ok({"id": tool_id}, "删除成功")
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Delete tool failed: {e}")
        raise HTTPException(status_code=500, detail=f"删除工具失败: {e}")


@router.put("/{tool_id}/toggle")
async def toggle_tool(tool_id: str, payload: dict, current_user: dict = Depends(get_current_user)):
    try:
        enabled = payload.get("enabled")
        if enabled is None:
            raise HTTPException(status_code=400, detail="缺少 enabled 字段")
        success = await tool_service.toggle_tool(tool_id, enabled)
        if not success:
            raise HTTPException(status_code=404, detail="工具不存在")
        return ok({"id": tool_id, "enabled": enabled}, "状态更新成功")
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Toggle tool failed: {e}")
        raise HTTPException(status_code=500, detail=f"切换工具状态失败: {e}")


@router.post("/{tool_id}/health-check")
async def health_check_tool(tool_id: str, current_user: dict = Depends(get_current_user)):
    try:
        tool = await tool_service.get_tool(tool_id)
        if not tool:
            raise HTTPException(status_code=404, detail="工具不存在")
        tool_type = tool.get("type", "builtin")
        if tool_type == "builtin":
            handler_name = tool.get("handler", "")
            is_healthy = handler_name in HANDLER_MAP
            status_str = "healthy" if is_healthy else "unhealthy"
            await tool_service.update_health_status(tool_id, status_str)
            return ok({"id": tool_id, "health_status": status_str, "details": f"Handler '{handler_name}' {'exists' if is_healthy else 'not found'} in HANDLER_MAP"})
        elif tool_type == "workflow":
            workflow_id = tool.get("workflow_id", "")
            from app.workflows.service import workflow_service
            wf = await workflow_service.get_workflow(workflow_id) if workflow_id else None
            is_healthy = wf is not None
            status_str = "healthy" if is_healthy else "unhealthy"
            await tool_service.update_health_status(tool_id, status_str)
            return ok({"id": tool_id, "health_status": status_str, "details": f"Workflow '{workflow_id}' {'exists' if is_healthy else 'not found'}"})
        else:
            await tool_service.update_health_status(tool_id, "unknown")
            return ok({"id": tool_id, "health_status": "unknown", "details": "Health check not implemented for rpc/remote yet"})
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Health check failed: {e}")
        raise HTTPException(status_code=500, detail=f"健康检查失败: {e}")


@router.post("/seed")
async def seed_tools(current_user: dict = Depends(get_current_user)):
    try:
        from app.tools.handler_map import seed_tools_to_db
        result = await seed_tools_to_db()
        return ok(result, "工具数据初始化完成")
    except Exception as e:
        logger.exception(f"Seed tools failed: {e}")
        raise HTTPException(status_code=500, detail=f"初始化工具数据失败: {e}")
