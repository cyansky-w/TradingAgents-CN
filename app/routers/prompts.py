"""
提示词管理 API
"""
import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from app.schemas.prompts import PromptCreate, PromptUpdate
from app.routers.auth_db import get_current_user
from app.core.response import ok
from app.services.prompt_service import prompt_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/prompts", tags=["提示词管理"])


def _prompt_error_status(message: str, default: int = 400) -> int:
    if "ID" in message:
        return 400
    if "不存在" in message:
        return 404
    if "不能删除" in message or "正被" in message:
        return 403
    return default


@router.get("/")
async def list_prompts(
    search: Optional[str] = Query(None, description="搜索关键词"),
    prompt_type: Optional[str] = Query(None, description="类型: chat/workflow"),
    tag: Optional[str] = Query(None, description="标签筛选"),
    enabled: Optional[bool] = Query(None, description="启用状态"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    all_versions: bool = Query(False, description="显示所有版本"),
    code: Optional[str] = Query(None, description="查询指定 code 的所有版本"),
    current_user: dict = Depends(get_current_user),
):
    try:
        prompts, total = await prompt_service.list_prompts(
            search=search,
            prompt_type=prompt_type,
            tag=tag,
            enabled=enabled,
            page=page,
            page_size=page_size,
            all_versions=all_versions,
            code=code,
        )
        return ok({"items": prompts, "total": total, "page": page, "page_size": page_size})
    except Exception as e:
        logger.exception(f"List prompts failed: {e}")
        raise HTTPException(status_code=500, detail=f"获取提示词列表失败: {e}")


@router.get("/tags")
async def get_all_tags(current_user: dict = Depends(get_current_user)):
    try:
        tags = await prompt_service.get_all_tags()
        return ok(tags)
    except Exception as e:
        logger.exception(f"Get tags failed: {e}")
        raise HTTPException(status_code=500, detail=f"获取标签失败: {e}")


@router.get("/variables")
async def derive_variables(
    tools: str = Query(..., description="工具编码列表，逗号分隔"),
    current_user: dict = Depends(get_current_user),
):
    try:
        tool_codes = [t.strip() for t in tools.split(",") if t.strip()]
        result = await prompt_service.derive_variables(tool_codes)
        return ok(result)
    except Exception as e:
        logger.exception(f"Derive variables failed: {e}")
        raise HTTPException(status_code=500, detail=f"推导变量失败: {e}")


@router.get("/code/{code}")
async def get_prompt_by_code(code: str, current_user: dict = Depends(get_current_user)):
    try:
        prompt = await prompt_service.get_active_prompt(code)
        if not prompt:
            raise HTTPException(status_code=404, detail="提示词不存在")
        return ok(prompt)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Get prompt by code failed: {e}")
        raise HTTPException(status_code=500, detail=f"获取提示词失败: {e}")


@router.get("/code/{code}/versions")
async def get_versions(code: str, current_user: dict = Depends(get_current_user)):
    try:
        versions = await prompt_service.get_versions(code)
        return ok(versions)
    except Exception as e:
        logger.exception(f"Get versions failed: {e}")
        raise HTTPException(status_code=500, detail=f"获取版本列表失败: {e}")


@router.get("/{prompt_id}")
async def get_prompt(prompt_id: str, current_user: dict = Depends(get_current_user)):
    try:
        prompt = await prompt_service.get_prompt(prompt_id)
        if not prompt:
            raise HTTPException(status_code=404, detail="提示词不存在")
        return ok(prompt)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Get prompt failed: {e}")
        raise HTTPException(status_code=500, detail=f"获取提示词详情失败: {e}")


@router.post("/")
async def create_prompt(payload: PromptCreate, current_user: dict = Depends(get_current_user)):
    try:
        data = payload.model_dump(exclude_none=True)
        prompt = await prompt_service.create_prompt(data)
        return ok(prompt, "创建成功")
    except ValueError as e:
        raise HTTPException(status_code=_prompt_error_status(str(e)), detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Create prompt failed: {e}")
        raise HTTPException(status_code=500, detail=f"创建提示词失败: {e}")


@router.put("/{prompt_id}")
async def update_prompt(prompt_id: str, payload: PromptUpdate, current_user: dict = Depends(get_current_user)):
    try:
        data = payload.model_dump(exclude_none=True)
        prompt = await prompt_service.update_prompt(prompt_id, data)
        return ok(prompt, "更新成功")
    except ValueError as e:
        raise HTTPException(status_code=_prompt_error_status(str(e)), detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Update prompt failed: {e}")
        raise HTTPException(status_code=500, detail=f"更新提示词失败: {e}")


@router.post("/{prompt_id}/new-version")
async def save_new_version(prompt_id: str, payload: PromptUpdate, current_user: dict = Depends(get_current_user)):
    try:
        data = payload.model_dump(exclude_none=True)
        prompt = await prompt_service.save_new_version(prompt_id, data)
        return ok(prompt, "新版本已保存")
    except ValueError as e:
        raise HTTPException(status_code=_prompt_error_status(str(e)), detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Save new version failed: {e}")
        raise HTTPException(status_code=500, detail=f"保存新版本失败: {e}")


@router.put("/{prompt_id}/activate")
async def activate_version(prompt_id: str, current_user: dict = Depends(get_current_user)):
    try:
        prompt = await prompt_service.activate_version(prompt_id)
        return ok(prompt, "版本已激活")
    except ValueError as e:
        raise HTTPException(status_code=_prompt_error_status(str(e)), detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Activate version failed: {e}")
        raise HTTPException(status_code=500, detail=f"激活版本失败: {e}")


@router.delete("/{prompt_id}")
async def delete_version(prompt_id: str, current_user: dict = Depends(get_current_user)):
    try:
        success = await prompt_service.delete_version(prompt_id)
        if not success:
            raise HTTPException(status_code=404, detail="版本不存在")
        return ok({"id": prompt_id}, "版本已删除")
    except ValueError as e:
        raise HTTPException(status_code=_prompt_error_status(str(e)), detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Delete version failed: {e}")
        raise HTTPException(status_code=500, detail=f"删除版本失败: {e}")


@router.delete("/code/{code}")
async def delete_prompt_by_code(code: str, current_user: dict = Depends(get_current_user)):
    try:
        success = await prompt_service.delete_prompt_by_code(code)
        if not success:
            raise HTTPException(status_code=404, detail="提示词不存在")
        return ok({"code": code}, "提示词已删除")
    except ValueError as e:
        raise HTTPException(status_code=_prompt_error_status(str(e)), detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Delete prompt failed: {e}")
        raise HTTPException(status_code=500, detail=f"删除提示词失败: {e}")


@router.put("/{prompt_id}/toggle")
async def toggle_prompt(prompt_id: str, payload: dict, current_user: dict = Depends(get_current_user)):
    try:
        enabled = payload.get("enabled")
        if enabled is None:
            raise HTTPException(status_code=400, detail="缺少 enabled 字段")
        success = await prompt_service.toggle_prompt(prompt_id, enabled)
        if not success:
            raise HTTPException(status_code=404, detail="提示词不存在")
        return ok({"id": prompt_id, "enabled": enabled}, "状态更新成功")
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Toggle prompt failed: {e}")
        raise HTTPException(status_code=500, detail=f"切换提示词状态失败: {e}")


@router.post("/{prompt_id}/render")
async def render_prompt(prompt_id: str, payload: dict, current_user: dict = Depends(get_current_user)):
    try:
        variables = payload.get("variables", {})
        result = await prompt_service.render_prompt(prompt_id, variables)
        return ok(result)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Render prompt failed: {e}")
        raise HTTPException(status_code=500, detail=f"渲染提示词失败: {e}")


@router.post("/seed")
async def seed_prompts(current_user: dict = Depends(get_current_user)):
    try:
        from app.prompts.seed_prompts import seed_prompts_to_db
        result = await seed_prompts_to_db()
        return ok(result, "提示词数据初始化完成")
    except Exception as e:
        logger.exception(f"Seed prompts failed: {e}")
        raise HTTPException(status_code=500, detail=f"初始化提示词数据失败: {e}")
