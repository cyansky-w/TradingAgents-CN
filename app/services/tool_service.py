"""
工具管理服务
"""
from __future__ import annotations
import logging
import re
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime
from bson import ObjectId
from app.core.database import get_mongo_db

logger = logging.getLogger(__name__)


class ToolService:
    def __init__(self) -> None:
        self.db = None
        self._indexes_ensured = False

    async def _get_db(self):
        if self.db is None:
            self.db = get_mongo_db()
        return self.db

    async def ensure_indexes(self) -> None:
        if self._indexes_ensured:
            return
        db = await self._get_db()
        try:
            await db.tools.drop_index("uniq_tool_code")
        except Exception:
            pass
        try:
            await db.tools.drop_index("uniq_tool_name")
        except Exception:
            pass
        dirty = await db.tools.delete_many({"code": None})
        if dirty.deleted_count:
            logger.warning(f"Removed {dirty.deleted_count} tool docs with missing code")
        await db.tools.create_index("code", unique=True, name="uniq_tool_code")
        await db.tools.create_index("name", unique=True, name="uniq_tool_name")
        await db.tools.create_index([("type", 1), ("enabled", 1)], name="idx_type_enabled")
        await db.tools.create_index("tags", name="idx_tags")
        self._indexes_ensured = True
        logger.info("Tool collection indexes ensured")

    def _format_doc(self, doc: Dict[str, Any]) -> Dict[str, Any]:
        if doc is None:
            return None
        return {
            "id": str(doc.get("_id")),
            "code": doc.get("code", ""),
            "name": doc.get("name", ""),
            "description": doc.get("description", ""),
            "type": doc.get("type", "builtin"),
            "handler": doc.get("handler"),
            "endpoint_url": doc.get("endpoint_url"),
            "endpoint_method": doc.get("endpoint_method"),
            "headers": doc.get("headers"),
            "auth_type": doc.get("auth_type"),
            "auth_config": doc.get("auth_config"),
            "parameters": doc.get("parameters", []),
            "output_schema": doc.get("output_schema"),
            "timeout": doc.get("timeout", 300),
            "tags": doc.get("tags", []),
            "enabled": doc.get("enabled", True),
            "is_system": doc.get("is_system", False),
            "health_status": doc.get("health_status", "unknown"),
            "last_health_check": _iso(doc.get("last_health_check")),
            "health_check_url": doc.get("health_check_url"),
            "agent_count": doc.get("agent_count", 0),
            "created_at": _iso(doc.get("created_at")),
            "updated_at": _iso(doc.get("updated_at")),
        }

    async def list_tools(self, *, tool_type=None, enabled=None, tag=None, search=None, page=1, page_size=20) -> Tuple[List[Dict[str, Any]], int]:
        db = await self._get_db()
        await self.ensure_indexes()
        query: Dict[str, Any] = {}
        if tool_type:
            query["type"] = tool_type
        if enabled is not None:
            query["enabled"] = enabled
        if tag:
            query["tags"] = tag
        if search:
            search_pattern = re.escape(search)
            query["$or"] = [
                {"name": {"$regex": search_pattern, "$options": "i"}},
                {"description": {"$regex": search_pattern, "$options": "i"}},
                {"code": {"$regex": search_pattern, "$options": "i"}},
                {"handler": {"$regex": search_pattern, "$options": "i"}},
                {"tags": {"$regex": search_pattern, "$options": "i"}},
                {"type": {"$regex": search_pattern, "$options": "i"}},
                {"parameters.name": {"$regex": search_pattern, "$options": "i"}},
                {"parameters.description": {"$regex": search_pattern, "$options": "i"}},
            ]
        total = await db.tools.count_documents(query)
        skip = (page - 1) * page_size
        cursor = db.tools.find(query).sort("name", 1).skip(skip).limit(page_size)
        docs = await cursor.to_list(length=page_size)
        return [self._format_doc(d) for d in docs], total

    async def get_tool(self, tool_id: str) -> Optional[Dict[str, Any]]:
        db = await self._get_db()
        await self.ensure_indexes()
        doc = await db.tools.find_one({"_id": ObjectId(tool_id)})
        return self._format_doc(doc)

    async def get_tool_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        db = await self._get_db()
        await self.ensure_indexes()
        doc = await db.tools.find_one({"name": name})
        return self._format_doc(doc)

    async def get_tool_by_code(self, code: str) -> Optional[Dict[str, Any]]:
        db = await self._get_db()
        await self.ensure_indexes()
        doc = await db.tools.find_one({"code": code})
        return self._format_doc(doc)

    async def create_tool(self, data: Dict[str, Any]) -> Dict[str, Any]:
        db = await self._get_db()
        await self.ensure_indexes()
        now = datetime.utcnow()
        doc = {**data, "is_system": False, "health_status": "unknown", "last_health_check": None, "agent_count": 0, "created_at": now, "updated_at": now}
        result = await db.tools.insert_one(doc)
        doc["_id"] = result.inserted_id
        logger.info(f"Created tool: {data.get('name')}")
        return self._format_doc(doc)

    async def update_tool(self, tool_id: str, data: Dict[str, Any]) -> bool:
        db = await self._get_db()
        await self.ensure_indexes()
        update = {k: v for k, v in data.items() if v is not None}
        update["updated_at"] = datetime.utcnow()
        if not update:
            return True
        result = await db.tools.update_one({"_id": ObjectId(tool_id)}, {"$set": update})
        return result.matched_count > 0

    async def delete_tool(self, tool_id: str) -> bool:
        db = await self._get_db()
        await self.ensure_indexes()
        doc = await db.tools.find_one({"_id": ObjectId(tool_id)})
        if not doc:
            return False
        if doc.get("is_system"):
            raise ValueError("System tools cannot be deleted")
        result = await db.tools.delete_one({"_id": ObjectId(tool_id)})
        if result.deleted_count > 0:
            logger.info(f"Deleted tool: {doc.get('name')}")
            return True
        return False

    async def toggle_tool(self, tool_id: str, enabled: bool) -> bool:
        db = await self._get_db()
        await self.ensure_indexes()
        result = await db.tools.update_one({"_id": ObjectId(tool_id)}, {"$set": {"enabled": enabled, "updated_at": datetime.utcnow()}})
        return result.matched_count > 0

    async def update_health_status(self, tool_id: str, status: str) -> bool:
        db = await self._get_db()
        await self.ensure_indexes()
        result = await db.tools.update_one({"_id": ObjectId(tool_id)}, {"$set": {"health_status": status, "last_health_check": datetime.utcnow(), "updated_at": datetime.utcnow()}})
        return result.matched_count > 0

    async def get_all_tags(self) -> List[str]:
        db = await self._get_db()
        await self.ensure_indexes()
        tags = await db.tools.distinct("tags")
        return sorted(tags)


def _iso(dt) -> str:
    if dt is None:
        return ""
    if isinstance(dt, str):
        return dt
    return dt.isoformat()


tool_service = ToolService()
