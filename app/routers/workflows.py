"""
工作流管理 API
"""
import json
import logging
from typing import Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse

from app.core.response import ok
from app.models.workflows import WorkflowCreate, WorkflowUpdate
from app.routers.auth_db import get_current_user
from app.services.workflow_service import workflow_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/workflows", tags=["工作流管理"])


async def _sync_workflow_cron(workflow_id: str) -> None:
    """Sync a single workflow's cron job with the scheduler."""
    try:
        from app.services.scheduler_service import get_scheduler_service
        from app.workflows.cron_scheduler import WorkflowCronScheduler
        svc = get_scheduler_service()
        wf_cron = WorkflowCronScheduler(svc.scheduler)
        await wf_cron.register_workflow(workflow_id)
    except Exception as e:
        logger.warning(f"Sync workflow cron failed for {workflow_id}: {e}")


def _wf_error_status(message: str, default: int = 400) -> int:
    if "不存在" in message:
        return 404
    if "不能删除" in message:
        return 403
    if "无效" in message:
        return 400
    return default


@router.get("/")
async def list_workflows(
    search: Optional[str] = Query(None, description="搜索关键词（name/code/description）"),
    tag: Optional[str] = Query(None, description="标签筛选"),
    enabled: Optional[bool] = Query(None, description="启用状态"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
):
    try:
        workflows, total = await workflow_service.list_workflows(
            search=search,
            tag=tag,
            enabled=enabled,
            page=page,
            page_size=page_size,
        )
        return ok({"items": workflows, "total": total, "page": page, "page_size": page_size})
    except Exception as exc:  # noqa: BLE001
        logger.exception(f"List workflows failed: {exc}")
        raise HTTPException(status_code=500, detail=f"获取工作流列表失败: {exc}")


@router.get("/tags")
async def get_all_tags(current_user: dict = Depends(get_current_user)):
    try:
        return ok(await workflow_service.get_all_tags())
    except Exception as exc:  # noqa: BLE001
        logger.exception(f"Get workflow tags failed: {exc}")
        raise HTTPException(status_code=500, detail=f"获取标签失败: {exc}")


@router.get("/{workflow_id}")
async def get_workflow(workflow_id: str, current_user: dict = Depends(get_current_user)):
    try:
        workflow = await workflow_service.get_workflow(workflow_id)
        if not workflow:
            raise HTTPException(status_code=404, detail="工作流不存在")
        return ok(workflow)
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=_wf_error_status(str(exc)), detail=str(exc))
    except Exception as exc:  # noqa: BLE001
        logger.exception(f"Get workflow failed: {exc}")
        raise HTTPException(status_code=500, detail=f"获取工作流详情失败: {exc}")


@router.post("/")
async def create_workflow(payload: WorkflowCreate, current_user: dict = Depends(get_current_user)):
    try:
        data = payload.model_dump(exclude_none=True)
        workflow = await workflow_service.create_workflow(data)
        return ok(workflow, "创建成功")
    except ValueError as exc:
        raise HTTPException(status_code=_wf_error_status(str(exc)), detail=str(exc))
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.exception(f"Create workflow failed: {exc}")
        raise HTTPException(status_code=500, detail=f"创建工作流失败: {exc}")


@router.put("/{workflow_id}")
async def update_workflow(
    workflow_id: str,
    payload: WorkflowUpdate,
    current_user: dict = Depends(get_current_user),
):
    try:
        data = payload.model_dump(exclude_unset=True)
        if not data:
            raise HTTPException(status_code=400, detail="无更新字段")
        workflow = await workflow_service.update_workflow(workflow_id, data)
        # Sync cron if trigger changed
        if "trigger" in data or "enabled" in data:
            await _sync_workflow_cron(workflow_id)
        return ok(workflow, "更新成功")
    except ValueError as exc:
        raise HTTPException(status_code=_wf_error_status(str(exc)), detail=str(exc))
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.exception(f"Update workflow failed: {exc}")
        raise HTTPException(status_code=500, detail=f"更新工作流失败: {exc}")


@router.delete("/{workflow_id}")
async def delete_workflow(workflow_id: str, current_user: dict = Depends(get_current_user)):
    try:
        success = await workflow_service.delete_workflow(workflow_id)
        if not success:
            raise HTTPException(status_code=404, detail="工作流不存在")
        return ok({"id": workflow_id}, "删除成功")
    except ValueError as exc:
        raise HTTPException(status_code=_wf_error_status(str(exc)), detail=str(exc))
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.exception(f"Delete workflow failed: {exc}")
        raise HTTPException(status_code=500, detail=f"删除工作流失败: {exc}")


@router.put("/{workflow_id}/toggle")
async def toggle_workflow(
    workflow_id: str,
    payload: dict = Body(...),
    current_user: dict = Depends(get_current_user),
):
    try:
        enabled = payload.get("enabled")
        if enabled is None:
            raise HTTPException(status_code=400, detail="缺少 enabled 字段")
        success = await workflow_service.toggle_workflow(workflow_id, bool(enabled))
        if not success:
            raise HTTPException(status_code=404, detail="工作流不存在")
        return ok({"id": workflow_id, "enabled": bool(enabled)}, "状态更新成功")
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.exception(f"Toggle workflow failed: {exc}")
        raise HTTPException(status_code=500, detail=f"切换状态失败: {exc}")


@router.post("/{workflow_id}/validate")
async def validate_workflow(workflow_id: str, current_user: dict = Depends(get_current_user)):
    try:
        result = await workflow_service.validate_dag(workflow_id)
        return ok(result)
    except ValueError as exc:
        raise HTTPException(status_code=_wf_error_status(str(exc)), detail=str(exc))
    except Exception as exc:  # noqa: BLE001
        logger.exception(f"Validate workflow failed: {exc}")
        raise HTTPException(status_code=500, detail=f"校验工作流失败: {exc}")


# ── Seed endpoint ──────────────────────────────────────────────


@router.post("/seed")
async def seed_workflows(current_user: dict = Depends(get_current_user)):
    try:
        from app.workflows.seed_workflows import seed_workflows_to_db
        result = await seed_workflows_to_db()
        return ok(result, "工作流种子数据初始化完成")
    except Exception as exc:  # noqa: BLE001
        logger.exception(f"Seed workflows failed: {exc}")
        raise HTTPException(status_code=500, detail=f"工作流种子数据初始化失败: {exc}")


# ── Execution endpoints ──────────────────────────────────────────


@router.post("/{workflow_id}/run")
async def run_workflow(
    workflow_id: str,
    payload: dict = Body(default={}),
    current_user: dict = Depends(get_current_user),
):
    """手动触发工作流执行，返回 run_id。"""
    try:
        from app.workflows.engine import workflow_engine

        input_data = payload.get("input", {})
        result = await workflow_engine.run(
            workflow_id=workflow_id,
            input_data=input_data,
            trigger_type="manual",
        )
        return ok({"run_id": result["run_id"], "output": result["output"]}, "执行完成")
    except ValueError as exc:
        raise HTTPException(status_code=_wf_error_status(str(exc)), detail=str(exc))
    except Exception as exc:  # noqa: BLE001
        logger.exception(f"Run workflow failed: {exc}")
        raise HTTPException(status_code=500, detail=f"工作流执行失败: {exc}")


@router.get("/{workflow_id}/runs")
async def list_workflow_runs(
    workflow_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
):
    try:
        from app.workflows.engine import workflow_engine

        runs, total = await workflow_engine.list_runs(workflow_id, page, page_size)
        return ok({"items": runs, "total": total, "page": page, "page_size": page_size})
    except Exception as exc:  # noqa: BLE001
        logger.exception(f"List workflow runs failed: {exc}")
        raise HTTPException(status_code=500, detail=f"获取运行历史失败: {exc}")


@router.get("/runs/{run_id}")
async def get_workflow_run(run_id: str, current_user: dict = Depends(get_current_user)):
    try:
        from app.workflows.engine import workflow_engine

        run = await workflow_engine.get_run(run_id)
        if not run:
            raise HTTPException(status_code=404, detail="运行记录不存在")
        return ok(run)
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:  # noqa: BLE001
        logger.exception(f"Get workflow run failed: {exc}")
        raise HTTPException(status_code=500, detail=f"获取运行详情失败: {exc}")


@router.post("/runs/{run_id}/cancel")
async def cancel_workflow_run(run_id: str, current_user: dict = Depends(get_current_user)):
    try:
        from app.workflows.engine import workflow_engine

        success = await workflow_engine.cancel_run(run_id)
        if not success:
            raise HTTPException(status_code=400, detail="无法取消（运行已结束或不存在）")
        return ok({"run_id": run_id, "status": "cancelled"}, "已取消")
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.exception(f"Cancel workflow run failed: {exc}")
        raise HTTPException(status_code=500, detail=f"取消运行失败: {exc}")


# ── SSE endpoint ──────────────────────────────────────────────────


async def _workflow_run_events(run_id: str):
    """SSE 事件流，推送节点执行状态。"""
    try:
        from app.workflows.engine import workflow_engine

        last_status = None
        while True:
            run = await workflow_engine.get_run(run_id)
            if not run:
                yield f"event: error\ndata: {json.dumps({'message': '运行记录不存在'})}\n\n"
                break

            if run["status"] != last_status:
                yield f"event: status\ndata: {json.dumps(run, ensure_ascii=False)}\n\n"
                last_status = run["status"]

            if last_status in ("completed", "failed", "cancelled"):
                break

            import asyncio
            await asyncio.sleep(1)

        yield f"event: done\ndata: {json.dumps({'run_id': run_id})}\n\n"
    except Exception as exc:  # noqa: BLE001
        logger.exception(f"SSE stream error: {exc}")
        yield f"event: error\ndata: {json.dumps({'message': str(exc)})}\n\n"


@router.get("/runs/{run_id}/stream")
async def stream_workflow_run(run_id: str, current_user: dict = Depends(get_current_user)):
    return StreamingResponse(
        _workflow_run_events(run_id),
        media_type="text/event-stream",
    )
