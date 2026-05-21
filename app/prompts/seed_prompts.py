"""
Seed 提示词数据到 MongoDB

策略：按 code 查询，存在则跳过（不覆盖用户修改），不存在则插入新文档，
标记 is_system=True / is_active=True / version=1。
"""
from __future__ import annotations
import logging
from datetime import datetime
from typing import Dict

from app.core.database import close_db, get_mongo_db, init_db
from app.services.prompt_service import prompt_service
from tradingagents.prompts import PROMPT_SEEDS

logger = logging.getLogger(__name__)


async def seed_prompts_to_db() -> Dict[str, int]:
    db = get_mongo_db()
    await prompt_service.ensure_indexes()

    created = 0
    skipped = 0
    failed: list[str] = []

    now = datetime.utcnow()
    for seed in PROMPT_SEEDS:
        code = seed.get("code", "")
        if not code:
            failed.append("<missing code>")
            continue
        try:
            existing = await db.prompts.find_one({"code": code})
            if existing:
                skipped += 1
                logger.info(f"[Seed] 跳过已存在的提示词: {code}")
                continue

            doc = {
                "code": code,
                "name": seed["name"],
                "description": seed.get("description", ""),
                "prompt_type": seed.get("prompt_type", "workflow"),
                "blocks": seed.get("blocks", []),
                "bind_tools": seed.get("bind_tools", []),
                "tags": seed.get("tags", []),
                "enabled": True,
                "is_system": True,
                "is_active": True,
                "version": 1,
                "agent_count": 0,
                "created_at": now,
                "updated_at": now,
            }
            await db.prompts.insert_one(doc)
            created += 1
            logger.info(f"[Seed] 已创建提示词: {code}")
        except Exception as e:
            failed.append(code)
            logger.exception(f"[Seed] 创建提示词失败 {code}: {e}")

    return {
        "created": created,
        "skipped": skipped,
        "failed": failed,
        "total": len(PROMPT_SEEDS),
    }


async def run_seed_prompts_cli() -> Dict[str, int]:
    await init_db()
    try:
        return await seed_prompts_to_db()
    finally:
        await close_db()


if __name__ == "__main__":
    import asyncio

    print(asyncio.run(run_seed_prompts_cli()))
