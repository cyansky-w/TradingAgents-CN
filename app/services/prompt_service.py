"""
提示词管理服务
"""
from __future__ import annotations
import logging
import re
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime
from bson import ObjectId
from bson.errors import InvalidId
from pymongo.errors import DuplicateKeyError
from app.core.database import get_mongo_db

logger = logging.getLogger(__name__)

VARIABLE_PATTERN = re.compile(r"\{\{(\w+)\}\}")


def _iso(dt) -> str:
    if dt is None:
        return ""
    if isinstance(dt, str):
        return dt
    return dt.isoformat()


class PromptService:
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
        await db.prompts.create_index(
            [("code", 1), ("version", 1)], unique=True, name="uniq_code_version"
        )
        indexes = await db.prompts.index_information()
        if "idx_code_active" in indexes:
            await db.prompts.drop_index("idx_code_active")
        await db.prompts.create_index(
            "code",
            unique=True,
            partialFilterExpression={"is_active": True},
            name="uniq_active_prompt_code",
        )
        if indexes.get("uniq_prompt_name", {}).get("unique"):
            await db.prompts.drop_index("uniq_prompt_name")
        await db.prompts.create_index(
            "name",
            unique=True,
            partialFilterExpression={"is_active": True},
            name="uniq_active_prompt_name",
        )
        await db.prompts.create_index("tags", name="idx_tags")
        await db.prompts.create_index("prompt_type", name="idx_prompt_type")
        self._indexes_ensured = True
        logger.info("Prompt collection indexes ensured")

    def _format_doc(self, doc: Dict[str, Any]) -> Dict[str, Any]:
        if doc is None:
            return None
        return {
            "id": str(doc.get("_id")),
            "code": doc.get("code", ""),
            "name": doc.get("name", ""),
            "description": doc.get("description", ""),
            "blocks": doc.get("blocks", []),
            "bind_tools": doc.get("bind_tools", []),
            "prompt_type": doc.get("prompt_type", "workflow"),
            "tags": doc.get("tags", []),
            "enabled": doc.get("enabled", True),
            "is_system": doc.get("is_system", False),
            "is_active": doc.get("is_active", True),
            "version": doc.get("version", 1),
            "agent_count": doc.get("agent_count", 0),
            "created_at": _iso(doc.get("created_at")),
            "updated_at": _iso(doc.get("updated_at")),
        }

    async def list_prompts(
        self,
        *,
        search: Optional[str] = None,
        prompt_type: Optional[str] = None,
        tag: Optional[str] = None,
        enabled: Optional[bool] = None,
        page: int = 1,
        page_size: int = 20,
        all_versions: bool = False,
        code: Optional[str] = None,
    ) -> Tuple[List[Dict[str, Any]], int]:
        db = await self._get_db()
        await self.ensure_indexes()
        query: Dict[str, Any] = {}

        if all_versions and code:
            query["code"] = code
        else:
            query["is_active"] = True

        if prompt_type:
            query["prompt_type"] = prompt_type
        if enabled is not None:
            query["enabled"] = enabled
        if tag:
            query["tags"] = tag
        if search:
            query["$or"] = [
                {"name": {"$regex": search, "$options": "i"}},
                {"code": {"$regex": search, "$options": "i"}},
                {"description": {"$regex": search, "$options": "i"}},
            ]

        total = await db.prompts.count_documents(query)
        skip = (page - 1) * page_size
        cursor = (
            db.prompts.find(query)
            .sort([("code", 1), ("version", -1)])
            .skip(skip)
            .limit(page_size)
        )
        docs = await cursor.to_list(length=page_size)
        return [self._format_doc(d) for d in docs], total

    async def get_prompt(self, prompt_id: str) -> Optional[Dict[str, Any]]:
        db = await self._get_db()
        await self.ensure_indexes()
        prompt_oid = self._object_id(prompt_id)
        doc = await db.prompts.find_one({"_id": prompt_oid})
        return self._format_doc(doc)

    async def get_active_prompt(self, code: str) -> Optional[Dict[str, Any]]:
        db = await self._get_db()
        await self.ensure_indexes()
        doc = await db.prompts.find_one({"code": code, "is_active": True})
        return self._format_doc(doc)

    async def get_prompt_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        db = await self._get_db()
        await self.ensure_indexes()
        doc = await db.prompts.find_one({"name": name, "is_active": True})
        return self._format_doc(doc)

    async def _check_code_unique(self, code: str) -> bool:
        db = await self._get_db()
        existing = await db.prompts.find_one({"code": code})
        return existing is None

    def _object_id(self, prompt_id: str) -> ObjectId:
        try:
            return ObjectId(prompt_id)
        except (InvalidId, TypeError):
            raise ValueError("无效的提示词 ID")

    async def _check_name_unique(self, name: str) -> bool:
        db = await self._get_db()
        existing = await db.prompts.find_one({"name": name, "is_active": True})
        return existing is None

    async def create_prompt(self, data: Dict[str, Any]) -> Dict[str, Any]:
        db = await self._get_db()
        await self.ensure_indexes()
        code = data.get("code", "")
        name = data.get("name", "")
        if not await self._check_code_unique(code):
            raise ValueError(f"编码 '{code}' 已存在")
        if not await self._check_name_unique(name):
            raise ValueError(f"名称 '{name}' 已存在")
        now = datetime.utcnow()
        doc = {
            "code": code,
            "name": name,
            "description": data.get("description", ""),
            "prompt_type": data.get("prompt_type", "workflow"),
            "blocks": data.get("blocks", []),
            "bind_tools": data.get("bind_tools", []),
            "tags": data.get("tags", []),
            "enabled": data.get("enabled", True),
            "is_system": False,
            "is_active": True,
            "version": 1,
            "agent_count": 0,
            "created_at": now,
            "updated_at": now,
        }
        result = await db.prompts.insert_one(doc)
        doc["_id"] = result.inserted_id
        logger.info(f"Created prompt: {code} (v1)")
        return self._format_doc(doc)

    async def update_prompt(self, prompt_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        db = await self._get_db()
        await self.ensure_indexes()
        doc = await db.prompts.find_one({"_id": self._object_id(prompt_id)})
        if not doc:
            raise ValueError("提示词不存在")

        update_fields = {}
        for key in ["name", "description", "prompt_type", "blocks", "bind_tools", "tags", "enabled"]:
            if key in data and data[key] is not None:
                update_fields[key] = data[key]

        if not update_fields:
            return self._format_doc(doc)

        update_fields["updated_at"] = datetime.utcnow()
        await db.prompts.update_one(
            {"_id": self._object_id(prompt_id)},
            {"$set": update_fields},
        )
        logger.info(f"Updated prompt {prompt_id}")
        return await self.get_prompt(prompt_id)

    async def save_new_version(
        self, prompt_id: str, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        db = await self._get_db()
        await self.ensure_indexes()
        current = await db.prompts.find_one({"_id": self._object_id(prompt_id)})
        if not current:
            raise ValueError("源版本不存在")
        code = current["code"]

        pipeline = [
            {"$match": {"code": code}},
            {"$group": {"_id": "$code", "max_version": {"$max": "$version"}}},
        ]
        result = await db.prompts.aggregate(pipeline).to_list(length=1)
        max_version = result[0]["max_version"] if result else 0

        now = datetime.utcnow()
        new_doc = {
            "code": code,
            "name": data.get("name", current.get("name", "")),
            "description": data.get("description", current.get("description", "")),
            "prompt_type": data.get("prompt_type", current.get("prompt_type", "workflow")),
            "blocks": data.get("blocks", current.get("blocks", [])),
            "bind_tools": data.get("bind_tools", current.get("bind_tools", [])),
            "tags": data.get("tags", current.get("tags", [])),
            "enabled": data.get("enabled", current.get("enabled", True)),
            "is_system": current.get("is_system", False),
            "is_active": False,
            "version": max_version + 1,
            "agent_count": current.get("agent_count", 0),
            "created_at": now,
            "updated_at": now,
        }
        insert_result = await db.prompts.insert_one(new_doc)
        new_doc["_id"] = insert_result.inserted_id
        await self.activate_version(str(insert_result.inserted_id))
        logger.info(f"Saved new version for {code}: v{max_version + 1}")
        return await self.get_prompt(str(insert_result.inserted_id))

    async def activate_version(self, prompt_id: str) -> Dict[str, Any]:
        db = await self._get_db()
        await self.ensure_indexes()
        target = await db.prompts.find_one({"_id": self._object_id(prompt_id)})
        if not target:
            raise ValueError("版本不存在")
        code = target["code"]
        prompt_oid = self._object_id(prompt_id)
        previous_active = await db.prompts.find_one({"code": code, "is_active": True})
        now = datetime.utcnow()
        await db.prompts.update_many(
            {"code": code, "is_active": True},
            {"$set": {"is_active": False, "updated_at": now}},
        )
        try:
            await db.prompts.update_one(
                {"_id": prompt_oid},
                {"$set": {"is_active": True, "updated_at": now}},
            )
        except DuplicateKeyError:
            if previous_active:
                await db.prompts.update_one(
                    {"_id": previous_active["_id"]},
                    {"$set": {"is_active": True, "updated_at": datetime.utcnow()}},
                )
            raise ValueError("版本激活冲突，请刷新后重试")
        except Exception:
            if previous_active:
                await db.prompts.update_one(
                    {"_id": previous_active["_id"]},
                    {"$set": {"is_active": True, "updated_at": datetime.utcnow()}},
                )
            raise
        logger.info(f"Activated version {target['version']} for {code}")
        return await self.get_prompt(prompt_id)

    async def delete_version(self, prompt_id: str) -> bool:
        db = await self._get_db()
        await self.ensure_indexes()
        doc = await db.prompts.find_one({"_id": self._object_id(prompt_id)})
        if not doc:
            return False
        if doc.get("is_active"):
            raise ValueError("不能删除活跃版本，请先切换到其他版本")
        if doc.get("is_system"):
            raise ValueError("系统提示词版本不能删除")
        result = await db.prompts.delete_one({"_id": self._object_id(prompt_id)})
        if result.deleted_count > 0:
            logger.info(f"Deleted version {doc['version']} of {doc['code']}")
            return True
        return False

    async def delete_prompt_by_code(self, code: str) -> bool:
        db = await self._get_db()
        await self.ensure_indexes()
        system_count = await db.prompts.count_documents({"code": code, "is_system": True})
        if system_count > 0:
            raise ValueError("系统提示词不能删除")
        active = await db.prompts.find_one({"code": code, "is_active": True})
        if active and active.get("agent_count", 0) > 0:
            raise ValueError(f"提示词 '{active['name']}' 正被 {active['agent_count']} 个 Agent 使用，不能删除")
        result = await db.prompts.delete_many({"code": code})
        if result.deleted_count > 0:
            logger.info(f"Deleted all versions of prompt: {code}")
            return True
        return False

    async def toggle_prompt(self, prompt_id: str, enabled: bool) -> bool:
        db = await self._get_db()
        await self.ensure_indexes()
        result = await db.prompts.update_one(
            {"_id": self._object_id(prompt_id)},
            {"$set": {"enabled": enabled, "updated_at": datetime.utcnow()}},
        )
        return result.matched_count > 0

    async def render_prompt(
        self, prompt_id: str, variables: Dict[str, str] = None
    ) -> Dict[str, Any]:
        prompt = await self.get_prompt(prompt_id)
        if not prompt:
            raise ValueError("提示词不存在")

        rendered_blocks = []
        unresolved = set()
        for block in prompt["blocks"]:
            if block["type"] == "text":
                content = block.get("content", "")
                if variables:
                    for key, value in variables.items():
                        content = content.replace(f"{{{{{key}}}}}", str(value))
                unresolved.update(VARIABLE_PATTERN.findall(content))
                rendered_blocks.append({
                    "type": "text",
                    "label": block.get("label", ""),
                    "content": content,
                })
            elif block["type"] == "messages_placeholder":
                rendered_blocks.append({
                    "type": "messages_placeholder",
                    "label": block.get("label", ""),
                })

        return {
            "id": prompt["id"],
            "code": prompt["code"],
            "name": prompt["name"],
            "rendered_blocks": rendered_blocks,
            "unresolved_variables": sorted(unresolved),
        }

    async def render_prompt_by_code(
        self, code: str, variables: Dict[str, str] = None
    ) -> Dict[str, Any]:
        prompt = await self.get_active_prompt(code)
        if not prompt:
            raise ValueError(f"提示词 '{code}' 不存在或无活跃版本")
        return await self.render_prompt(prompt["id"], variables)

    async def get_all_tags(self) -> List[str]:
        db = await self._get_db()
        await self.ensure_indexes()
        tags = await db.prompts.distinct("tags")
        return sorted(tags)

    async def get_versions(self, code: str) -> List[Dict[str, Any]]:
        db = await self._get_db()
        await self.ensure_indexes()
        cursor = db.prompts.find({"code": code}).sort("version", -1)
        docs = await cursor.to_list(length=100)
        return [self._format_doc(d) for d in docs]

    async def derive_variables(self, tool_codes: List[str]) -> Dict[str, Any]:
        """从绑定工具推导出入参变量列表"""
        from app.services.tool_service import tool_service

        tool_params = []
        tool_outputs = []

        for code in tool_codes:
            tool = await tool_service.get_tool_by_code(code)
            if not tool:
                continue
            for param in tool.get("parameters", []):
                tool_params.append({
                    "name": param.get("name", ""),
                    "description": param.get("description", ""),
                    "source_tool": code,
                })
            schema = tool.get("output_schema")
            if schema and isinstance(schema, dict):
                for field_name, field_info in schema.get("properties", {}).items():
                    tool_outputs.append({
                        "name": field_name,
                        "description": field_info.get("description", ""),
                        "source_tool": code,
                    })

        return {
            "tool_params": tool_params,
            "tool_outputs": tool_outputs,
        }

    @staticmethod
    def extract_variables(blocks: List[Dict[str, Any]]) -> List[str]:
        variables = set()
        for block in blocks:
            if block.get("type") == "text":
                content = block.get("content", "")
                variables.update(VARIABLE_PATTERN.findall(content))
        return sorted(variables)


prompt_service = PromptService()
