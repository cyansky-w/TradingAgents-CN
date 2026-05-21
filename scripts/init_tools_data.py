#!/usr/bin/env python3
"""
工具数据初始化脚本
幂等执行：按 name upsert，只更新结构字段，不覆盖 enabled/timeout

Usage:
    python scripts/init_tools_data.py           # 幂等 upsert
    python scripts/init_tools_data.py --reset   # 删除后重建
"""

import sys
import asyncio
import logging
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)


async def main():
    from motor.motor_asyncio import AsyncIOMotorClient
    from app.core.config import settings
    from app.tools.handler_map import seed_tools_to_db

    client = AsyncIOMotorClient(settings.MONGO_URI)
    db = client[settings.MONGO_DB]

    # --reset: drop tools collection first
    if "--reset" in sys.argv:
        await db.drop_collection("tools")
        logger.info("Dropped tools collection")

    # Point global mongo_db so seed_tools_to_db's get_mongo_db() works
    from app.core import database as db_mod
    db_mod.mongo_db = db

    result = await seed_tools_to_db()
    logger.info(f"Seed result: {result}")
    client.close()


if __name__ == "__main__":
    asyncio.run(main())
