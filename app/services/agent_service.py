"""
Agent 管理服务

负责 agents 集合 CRUD、提示词反向计数维护，以及运行时 AgentSpec 构建。
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from bson import ObjectId
from bson.errors import InvalidId

from app.core.database import get_mongo_db
from app.models.agents import AgentParameters

logger = logging.getLogger(__name__)


def _iso(dt: Any) -> str:
    if dt is None:
        return ""
    if isinstance(dt, str):
        return dt
    return dt.isoformat()


@dataclass(frozen=True)
class AgentSpec:
    """运行时 Agent 规格 — 不可变。"""

    agent_id: str
    agent_code: str
    agent_name: str
    system_prompt: str
    messages_placeholder: Optional[str]
    tools: List[Any]
    llm: Any
    parameters: AgentParameters


class AgentService:
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
        await db.agents.create_index("code", unique=True, name="uniq_agent_code")
        await db.agents.create_index("name", unique=True, name="uniq_agent_name")
        await db.agents.create_index("tags", name="idx_agent_tags")
        await db.agents.create_index("is_chat", name="idx_agent_is_chat")
        await db.agents.create_index("enabled", name="idx_agent_enabled")
        self._indexes_ensured = True
        logger.info("Agent collection indexes ensured")

    # ── Helpers ───────────────────────────────────────────

    def _object_id(self, value: str) -> ObjectId:
        try:
            return ObjectId(value)
        except (InvalidId, TypeError):
            raise ValueError("无效的 Agent ID")

    def _prompt_object_id(self, value: str) -> ObjectId:
        try:
            return ObjectId(value)
        except (InvalidId, TypeError):
            raise ValueError("无效的提示词 ID")

    def _resolved_model_config(self, doc: Dict[str, Any]) -> Any:
        if "model_config_agent" in doc:
            return doc.get("model_config_agent")
        return doc.get("model_config")

    def _format_doc(self, doc: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if doc is None:
            return None
        return {
            "id": str(doc.get("_id")),
            "code": doc.get("code", ""),
            "name": doc.get("name", ""),
            "description": doc.get("description", ""),
            "prompt_id": str(doc.get("prompt_id", "")),
            "model_config": self._resolved_model_config(doc),
            "parameters": doc.get(
                "parameters",
                {"max_tool_calls": 10, "timeout": 300, "retry_on_failure": False},
            ),
            "tags": doc.get("tags", []),
            "is_chat": doc.get("is_chat", False),
            "is_system": doc.get("is_system", False),
            "enabled": doc.get("enabled", True),
            "usage_count": doc.get("usage_count", 0),
            "last_used_at": _iso(doc.get("last_used_at")),
            "created_at": _iso(doc.get("created_at")),
            "updated_at": _iso(doc.get("updated_at")),
        }

    def _normalize_model_config_field(self, data: Dict[str, Any]) -> Dict[str, Any]:
        normalized = dict(data)
        if "model_config" in normalized and "model_config_agent" not in normalized:
            normalized["model_config_agent"] = normalized.pop("model_config")
        return normalized

    async def _get_enabled_prompt(self, prompt_id: str) -> Dict[str, Any]:
        db = await self._get_db()
        prompt_oid = self._prompt_object_id(prompt_id)
        prompt = await db.prompts.find_one({"_id": prompt_oid, "enabled": True, "is_active": True})
        if not prompt:
            raise ValueError("提示词不存在或未启用")
        return prompt

    async def _get_configured_provider_names(self) -> set[str]:
        from app.services.config_service import ConfigService

        providers = await ConfigService().get_llm_providers()
        return {provider.name for provider in providers}

    async def _validate_model_config(self, model_config: Optional[Dict[str, Any]]) -> None:
        if not model_config:
            return
        provider = model_config.get("provider")
        model = model_config.get("model")
        if not provider or not model:
            return
        provider_names = await self._get_configured_provider_names()
        if provider not in provider_names:
            raise ValueError(f"模型厂商未配置: {provider}")

    async def _check_code_unique(self, code: str) -> bool:
        db = await self._get_db()
        return await db.agents.find_one({"code": code}) is None

    async def _check_name_unique(self, name: str) -> bool:
        db = await self._get_db()
        return await db.agents.find_one({"name": name}) is None

    # ── CRUD ──────────────────────────────────────────────

    async def list_agents(
        self,
        *,
        search: Optional[str] = None,
        tag: Optional[str] = None,
        enabled: Optional[bool] = None,
        is_chat: Optional[bool] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[Dict[str, Any]], int]:
        db = await self._get_db()
        await self.ensure_indexes()
        query: Dict[str, Any] = {}
        if tag:
            query["tags"] = tag
        if enabled is not None:
            query["enabled"] = enabled
        if is_chat is not None:
            query["is_chat"] = is_chat
        if search:
            query["$or"] = [
                {"name": {"$regex": search, "$options": "i"}},
                {"code": {"$regex": search, "$options": "i"}},
                {"description": {"$regex": search, "$options": "i"}},
            ]
        total = await db.agents.count_documents(query)
        skip = (page - 1) * page_size
        cursor = db.agents.find(query).sort("name", 1).skip(skip).limit(page_size)
        docs = await cursor.to_list(length=page_size)
        return [self._format_doc(doc) for doc in docs], total

    async def get_agent(self, agent_id: str) -> Optional[Dict[str, Any]]:
        db = await self._get_db()
        await self.ensure_indexes()
        doc = await db.agents.find_one({"_id": self._object_id(agent_id)})
        return self._format_doc(doc)

    async def get_agent_by_code(self, code: str) -> Optional[Dict[str, Any]]:
        db = await self._get_db()
        await self.ensure_indexes()
        doc = await db.agents.find_one({"code": code})
        return self._format_doc(doc)

    async def get_agent_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        db = await self._get_db()
        await self.ensure_indexes()
        doc = await db.agents.find_one({"name": name})
        return self._format_doc(doc)

    async def create_agent(self, data: Dict[str, Any]) -> Dict[str, Any]:
        data = self._normalize_model_config_field(data)
        db = await self._get_db()
        await self.ensure_indexes()
        code = data.get("code", "")
        name = data.get("name", "")
        if not await self._check_code_unique(code):
            raise ValueError(f"编码 '{code}' 已存在")
        if not await self._check_name_unique(name):
            raise ValueError(f"名称 '{name}' 已存在")
        await self._validate_model_config(data.get("model_config_agent"))
        prompt = await self._get_enabled_prompt(data["prompt_id"])
        now = datetime.utcnow()
        doc = {
            "code": code,
            "name": name,
            "description": data.get("description", ""),
            "prompt_id": prompt["_id"],
            "model_config_agent": data.get("model_config_agent"),
            "parameters": data.get(
                "parameters",
                {"max_tool_calls": 10, "timeout": 300, "retry_on_failure": False},
            ),
            "tags": data.get("tags", []),
            "is_chat": data.get("is_chat", False),
            "is_system": data.get("is_system", False),
            "enabled": data.get("enabled", True),
            "usage_count": 0,
            "last_used_at": None,
            "created_at": now,
            "updated_at": now,
        }
        result = await db.agents.insert_one(doc)
        doc["_id"] = result.inserted_id
        await db.prompts.update_one({"_id": prompt["_id"]}, {"$inc": {"agent_count": 1}})
        logger.info(f"Created agent: {code}")
        return self._format_doc(doc)

    async def update_agent(self, agent_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        data = self._normalize_model_config_field(data)
        db = await self._get_db()
        await self.ensure_indexes()
        agent_oid = self._object_id(agent_id)
        current = await db.agents.find_one({"_id": agent_oid})
        if not current:
            raise ValueError("Agent 不存在")

        update_fields: Dict[str, Any] = {}
        for key in ("name", "description", "model_config_agent", "parameters", "tags", "is_chat", "enabled"):
            if key in data:
                update_fields[key] = data[key]

        if "model_config_agent" in update_fields:
            await self._validate_model_config(update_fields.get("model_config_agent"))

        # 名称唯一性校验（仅当名称发生变更）
        new_name = update_fields.get("name")
        if new_name and new_name != current.get("name"):
            existing = await db.agents.find_one({"name": new_name})
            if existing and existing.get("_id") != agent_oid:
                raise ValueError(f"名称 '{new_name}' 已存在")

        if "prompt_id" in data:
            new_prompt = await self._get_enabled_prompt(data["prompt_id"])
            old_prompt_id = current.get("prompt_id")
            new_prompt_id = new_prompt["_id"]
            if old_prompt_id != new_prompt_id:
                if old_prompt_id is not None:
                    await db.prompts.update_one({"_id": old_prompt_id}, {"$inc": {"agent_count": -1}})
                await db.prompts.update_one({"_id": new_prompt_id}, {"$inc": {"agent_count": 1}})
            update_fields["prompt_id"] = new_prompt_id

        if not update_fields:
            return self._format_doc(current)

        update_fields["updated_at"] = datetime.utcnow()
        await db.agents.update_one({"_id": agent_oid}, {"$set": update_fields})
        logger.info(f"Updated agent: {agent_id}")
        return await self.get_agent(agent_id)

    async def delete_agent(self, agent_id: str) -> bool:
        db = await self._get_db()
        await self.ensure_indexes()
        agent_oid = self._object_id(agent_id)
        current = await db.agents.find_one({"_id": agent_oid})
        if not current:
            return False
        if current.get("is_system"):
            raise ValueError("系统 Agent 不能删除")
        prompt_id = current.get("prompt_id")
        if prompt_id is not None:
            await db.prompts.update_one({"_id": prompt_id}, {"$inc": {"agent_count": -1}})
        result = await db.agents.delete_one({"_id": agent_oid})
        if result.deleted_count > 0:
            logger.info(f"Deleted agent: {current.get('code')}")
            return True
        return False

    async def toggle_agent(self, agent_id: str, enabled: bool) -> bool:
        db = await self._get_db()
        await self.ensure_indexes()
        result = await db.agents.update_one(
            {"_id": self._object_id(agent_id)},
            {"$set": {"enabled": enabled, "updated_at": datetime.utcnow()}},
        )
        return result.matched_count > 0

    async def get_all_tags(self) -> List[str]:
        db = await self._get_db()
        await self.ensure_indexes()
        tags = await db.agents.distinct("tags")
        return sorted([tag for tag in tags if tag])

    async def record_usage(self, agent_id: str) -> None:
        db = await self._get_db()
        await self.ensure_indexes()
        await db.agents.update_one(
            {"_id": self._object_id(agent_id)},
            {"$inc": {"usage_count": 1}, "$set": {"last_used_at": datetime.utcnow()}},
        )

    # ── Runtime build ─────────────────────────────────────

    def _rendered_prompt_to_system(
        self, rendered_blocks: List[Dict[str, Any]]
    ) -> Tuple[str, Optional[str]]:
        text_parts: List[str] = []
        placeholder_label: Optional[str] = None
        for block in rendered_blocks:
            block_type = block.get("type")
            if block_type == "text":
                text_parts.append(block.get("content", ""))
            elif block_type == "messages_placeholder":
                placeholder_label = block.get("label", "对话历史") or "对话历史"
        return "\n\n".join(part for part in text_parts if part), placeholder_label

    async def _resolve_agent_tools(self, bind_tools: List[str], retry_on_failure: bool = False) -> List[Any]:
        from app.services.agent_tool_adapter import wrap_as_base_tool

        tools: List[Any] = []
        for code in bind_tools or []:
            tool_meta = await tool_service.get_tool_by_code(code)
            if not tool_meta or not tool_meta.get("enabled", True):
                logger.warning(f"build_agent: skip disabled/missing tool {code}")
                continue
            if tool_meta.get("type") != "builtin":
                logger.warning(f"build_agent: skip non-builtin tool {code}")
                continue
            handler_name = tool_meta.get("handler")
            handler = HANDLER_MAP.get(handler_name) if handler_name else None
            if not handler:
                logger.warning(f"build_agent: handler '{handler_name}' missing for tool {code}")
                continue
            tools.append(wrap_as_base_tool(handler, tool_meta, retry_on_failure=retry_on_failure))
        return tools

    async def build_agent(
        self,
        agent_id: str,
        variables: Optional[Dict[str, str]] = None,
    ) -> AgentSpec:
        db = await self._get_db()
        await self.ensure_indexes()
        doc = await db.agents.find_one({"_id": self._object_id(agent_id)})
        if not doc:
            raise ValueError("Agent 不存在")
        if not doc.get("enabled", True):
            raise ValueError("Agent 未启用")

        prompt = await db.prompts.find_one({
            "_id": doc["prompt_id"],
            "enabled": True,
            "is_active": True,
        })
        if not prompt:
            raise ValueError("绑定提示词不存在或未启用")

        rendered = await prompt_service.render_prompt(str(prompt["_id"]), variables or {})
        system_prompt, messages_placeholder = self._rendered_prompt_to_system(
            rendered.get("rendered_blocks", [])
        )
        parameters = AgentParameters(**doc.get("parameters", {}))
        tools = await self._resolve_agent_tools(
            prompt.get("bind_tools", []),
            retry_on_failure=parameters.retry_on_failure,
        )

        model_config = self._resolved_model_config(doc) or {}
        provider = model_config.get("provider")
        model = model_config.get("model")
        llm_kwargs: Dict[str, Any] = {
            "streaming": True,
            "temperature": model_config.get("temperature", 0.7),
            "max_tokens": model_config.get("max_tokens", 4096),
        }
        if provider and model:
            llm_kwargs["provider"] = provider
            llm_kwargs["model"] = model
        # DeepSeek 工具调用场景需禁用 thinking，避免 reasoning_content 400 错误
        if tools:
            effective_model = model
            if not effective_model:
                try:
                    _, default_model, _, _, _ = await get_chat_llm_config()
                    effective_model = default_model
                    logger.info(f"build_agent: resolved default model for thinking check: {effective_model}")
                except Exception as exc:
                    logger.warning(f"build_agent: failed to resolve default model: {exc}")
            if effective_model and "deepseek" in effective_model.lower():
                llm_kwargs["extra_body"] = {"thinking": {"type": "disabled"}}
                logger.info(f"build_agent: disabled DeepSeek thinking for tool-calling agent {doc.get('code')}")
        llm = await create_chat_llm(**llm_kwargs)

        return AgentSpec(
            agent_id=str(doc["_id"]),
            agent_code=doc.get("code", ""),
            agent_name=doc.get("name", ""),
            system_prompt=system_prompt,
            messages_placeholder=messages_placeholder,
            tools=tools,
            llm=llm,
            parameters=parameters,
        )


# ── Imports kept after class definition to allow monkeypatch in tests ────

from app.chat.llm_factory import create_chat_llm, get_chat_llm_config  # noqa: E402
from app.services.prompt_service import prompt_service  # noqa: E402
from app.services.tool_service import tool_service  # noqa: E402
from app.tools.handler_map import HANDLER_MAP  # noqa: E402


agent_service = AgentService()
