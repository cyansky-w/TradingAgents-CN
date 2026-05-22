"""Tests for Agent service & models."""
from __future__ import annotations

import asyncio
import re
from datetime import datetime

import pytest
from bson import ObjectId
from pydantic import ValidationError

from app.models.agents import (
    AgentCreate,
    AgentModelConfig,
    AgentParameters,
    AgentUpdate,
)


# ── Pydantic Schema tests ─────────────────────────────────────


def test_agent_create_accepts_minimal_valid_payload():
    payload = AgentCreate(
        code="market_analyst",
        name="市场分析师",
        prompt_id="507f1f77bcf86cd799439011",
        message_template="请分析 {{ticker}}。",
    )

    assert payload.code == "market_analyst"
    assert payload.name == "市场分析师"
    assert payload.description == ""
    assert payload.prompt_id == "507f1f77bcf86cd799439011"
    assert payload.message_template == "请分析 {{ticker}}。"
    assert payload.model_config_agent is None
    assert payload.parameters.max_tool_calls == 10
    assert payload.parameters.timeout == 300
    assert payload.parameters.retry_on_failure is False
    assert payload.tags == []
    assert payload.is_chat is False
    assert payload.enabled is True


def test_agent_create_rejects_invalid_code():
    with pytest.raises(ValidationError):
        AgentCreate(code="Market-Analyst", name="市场分析师", prompt_id="507f1f77bcf86cd799439011", message_template="测试")


def test_agent_parameters_validate_ranges():
    assert AgentParameters(max_tool_calls=1, timeout=1).max_tool_calls == 1

    with pytest.raises(ValidationError):
        AgentParameters(max_tool_calls=0)

    with pytest.raises(ValidationError):
        AgentParameters(timeout=0)


def test_agent_model_config_allows_partial_values():
    config = AgentModelConfig(provider="deepseek")

    assert config.provider == "deepseek"
    assert config.model is None
    assert config.temperature == 0.7
    assert config.max_tokens == 4096


def test_agent_update_all_fields_optional():
    update = AgentUpdate()

    assert update.model_dump(exclude_none=True) == {}


def test_agent_create_accepts_model_config_alias():
    payload = AgentCreate(
        code="market_analyst",
        name="市场分析师",
        prompt_id="507f1f77bcf86cd799439011",
        message_template="请分析 {{ticker}}。",
        model_config={"provider": "deepseek", "model": "deepseek-chat"},
    )

    assert payload.model_config_agent is not None
    assert payload.model_config_agent.provider == "deepseek"
    assert payload.model_config_agent.model == "deepseek-chat"


# ── Fake Mongo collections / DB ──────────────────────────────


class _FakeCursor:
    def __init__(self, docs):
        self.docs = list(docs)
        self.skip_count = 0
        self.limit_count = len(self.docs)

    def sort(self, *args, **kwargs):
        return self

    def skip(self, value):
        self.skip_count = value
        return self

    def limit(self, value):
        self.limit_count = value
        return self

    async def to_list(self, length):
        end = self.skip_count + self.limit_count
        return self.docs[self.skip_count:end]


class _InsertResult:
    def __init__(self, inserted_id):
        self.inserted_id = inserted_id


class _UpdateResult:
    def __init__(self, matched_count=1, modified_count=1):
        self.matched_count = matched_count
        self.modified_count = modified_count


class _DeleteResult:
    def __init__(self, deleted_count):
        self.deleted_count = deleted_count


class _FakeCollection:
    def __init__(self, docs=None):
        self.docs = list(docs or [])
        self.indexes = []

    async def create_index(self, *args, **kwargs):
        self.indexes.append((args, kwargs))

    async def count_documents(self, query):
        return len([doc for doc in self.docs if self._matches(doc, query)])

    def find(self, query):
        return _FakeCursor([doc for doc in self.docs if self._matches(doc, query)])

    async def find_one(self, query):
        for doc in self.docs:
            if self._matches(doc, query):
                return doc
        return None

    async def insert_one(self, doc):
        inserted = dict(doc)
        inserted.setdefault("_id", ObjectId())
        self.docs.append(inserted)
        return _InsertResult(inserted["_id"])

    async def update_one(self, query, update):
        doc = await self.find_one(query)
        if not doc:
            return _UpdateResult(matched_count=0, modified_count=0)
        self._apply_update(doc, update)
        return _UpdateResult()

    async def delete_one(self, query):
        for index, doc in enumerate(self.docs):
            if self._matches(doc, query):
                self.docs.pop(index)
                return _DeleteResult(1)
        return _DeleteResult(0)

    async def distinct(self, field):
        values = set()
        for doc in self.docs:
            field_value = doc.get(field, [])
            if isinstance(field_value, list):
                for value in field_value:
                    values.add(value)
            elif field_value is not None:
                values.add(field_value)
        return list(values)

    def _apply_update(self, doc, update):
        for key, value in update.get("$set", {}).items():
            doc[key] = value
        for key, value in update.get("$inc", {}).items():
            doc[key] = doc.get(key, 0) + value

    def _matches(self, doc, query):
        for key, expected in query.items():
            if key == "$or":
                if not any(self._matches(doc, condition) for condition in expected):
                    return False
                continue
            if isinstance(expected, dict) and "$regex" in expected:
                flags = re.IGNORECASE if "i" in expected.get("$options", "") else 0
                if not re.search(expected["$regex"], str(doc.get(key, "")), flags):
                    return False
                continue
            if doc.get(key) != expected:
                return False
        return True


class _FakeAgentDb:
    def __init__(self, prompts=None, agents=None):
        self.prompts = _FakeCollection(prompts)
        self.agents = _FakeCollection(agents)


# ── Service-level helpers ─────────────────────────────────────


def _service_with_db(db):
    from app.services.agent_service import AgentService

    service = AgentService()
    service.db = db
    service._indexes_ensured = True
    return service


# ── CRUD tests ───────────────────────────────────────────────


def test_format_doc_exposes_model_config_public_name():
    prompt_id = ObjectId()
    agent_id = ObjectId()
    db = _FakeAgentDb(agents=[{
        "_id": agent_id,
        "code": "market_analyst",
        "name": "市场分析师",
        "prompt_id": prompt_id,
        "model_config_agent": {
            "provider": "deepseek",
            "model": "deepseek-chat",
            "temperature": 0.3,
            "max_tokens": 4096,
        },
        "parameters": {"max_tool_calls": 10, "timeout": 300, "retry_on_failure": False},
        "tags": [],
        "is_chat": False,
        "is_system": False,
        "enabled": True,
        "usage_count": 0,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    }])
    service = _service_with_db(db)

    agent = asyncio.run(service.get_agent(str(agent_id)))

    assert agent["model_config"] == {
        "provider": "deepseek",
        "model": "deepseek-chat",
        "temperature": 0.3,
        "max_tokens": 4096,
    }
    assert "model_config_agent" not in agent


def test_get_agent_by_name_returns_formatted_agent():
    prompt_id = ObjectId()
    agent_id = ObjectId()
    db = _FakeAgentDb(agents=[{
        "_id": agent_id,
        "code": "smart_assistant",
        "name": "智能助手",
        "description": "通用聊天助手",
        "prompt_id": prompt_id,
        "model_config_agent": {"provider": "deepseek", "model": "deepseek-chat"},
        "parameters": {"max_tool_calls": 10, "timeout": 300, "retry_on_failure": False},
        "tags": ["聊天"],
        "is_chat": True,
        "is_system": False,
        "enabled": True,
        "usage_count": 2,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    }])
    service = _service_with_db(db)

    agent = asyncio.run(service.get_agent_by_name("智能助手"))

    assert agent == {
        "id": str(agent_id),
        "code": "smart_assistant",
        "name": "智能助手",
        "description": "通用聊天助手",
        "prompt_id": str(prompt_id),
        "message_template": "",
        "model_config": {"provider": "deepseek", "model": "deepseek-chat"},
        "parameters": {"max_tool_calls": 10, "timeout": 300, "retry_on_failure": False},
        "tags": ["聊天"],
        "is_chat": True,
        "is_system": False,
        "enabled": True,
        "usage_count": 2,
        "last_used_at": "",
        "created_at": agent["created_at"],
        "updated_at": agent["updated_at"],
    }
    assert "model_config_agent" not in agent


def test_create_agent_validates_prompt_and_increments_prompt_count():
    prompt_id = ObjectId()
    db = _FakeAgentDb(prompts=[{
        "_id": prompt_id,
        "code": "market_analyst_system",
        "name": "市场分析提示词",
        "enabled": True,
        "is_active": True,
        "agent_count": 0,
    }])
    service = _service_with_db(db)

    agent = asyncio.run(service.create_agent({
        "code": "market_analyst",
        "name": "市场分析师",
        "prompt_id": str(prompt_id),
        "tags": ["分析"],
    }))

    assert agent["code"] == "market_analyst"
    assert agent["prompt_id"] == str(prompt_id)
    assert db.prompts.docs[0]["agent_count"] == 1


def test_create_agent_accepts_public_model_config_field():
    prompt_id = ObjectId()
    db = _FakeAgentDb(prompts=[{
        "_id": prompt_id,
        "enabled": True,
        "is_active": True,
        "agent_count": 0,
    }])
    service = _service_with_db(db)

    async def fake_provider_names():
        return {"deepseek"}

    service._get_configured_provider_names = fake_provider_names

    agent = asyncio.run(service.create_agent({
        "code": "smart_assistant",
        "name": "智能助手",
        "prompt_id": str(prompt_id),
        "model_config": {"provider": "deepseek", "model": "deepseek-chat"},
    }))

    assert agent["model_config"] == {
        "provider": "deepseek",
        "model": "deepseek-chat",
    }
    assert db.agents.docs[0]["model_config_agent"] == {
        "provider": "deepseek",
        "model": "deepseek-chat",
    }


def test_create_agent_rejects_unknown_model_provider(monkeypatch):
    prompt_id = ObjectId()
    db = _FakeAgentDb(prompts=[{"_id": prompt_id, "enabled": True, "is_active": True, "agent_count": 0}])
    service = _service_with_db(db)

    async def fake_provider_names():
        return {"deepseek"}

    monkeypatch.setattr(service, "_get_configured_provider_names", fake_provider_names)

    with pytest.raises(ValueError, match="模型厂商未配置: missing"):
        asyncio.run(service.create_agent({
            "code": "market_analyst",
            "name": "市场分析师",
            "prompt_id": str(prompt_id),
            "model_config_agent": {"provider": "missing", "model": "missing-model"},
        }))



def test_create_agent_allows_partial_model_config_as_default(monkeypatch):
    prompt_id = ObjectId()
    db = _FakeAgentDb(prompts=[{"_id": prompt_id, "enabled": True, "is_active": True, "agent_count": 0}])
    service = _service_with_db(db)

    async def fake_provider_names():
        raise AssertionError("partial provider/model should not require validation")

    monkeypatch.setattr(service, "_get_configured_provider_names", fake_provider_names)

    agent = asyncio.run(service.create_agent({
        "code": "market_analyst",
        "name": "市场分析师",
        "prompt_id": str(prompt_id),
        "model_config_agent": {"provider": "deepseek"},
    }))

    assert agent["code"] == "market_analyst"
    assert agent["model_config"] == {"provider": "deepseek"}



def test_create_agent_rejects_disabled_prompt():
    prompt_id = ObjectId()
    db = _FakeAgentDb(prompts=[{"_id": prompt_id, "enabled": False, "is_active": True}])
    service = _service_with_db(db)

    with pytest.raises(ValueError, match="提示词不存在或未启用"):
        asyncio.run(service.create_agent({
            "code": "market_analyst",
            "name": "市场分析师",
            "prompt_id": str(prompt_id),
        }))


def test_create_agent_rejects_duplicate_code():
    prompt_id = ObjectId()
    db = _FakeAgentDb(
        prompts=[{"_id": prompt_id, "enabled": True, "is_active": True, "agent_count": 0}],
        agents=[{
            "_id": ObjectId(),
            "code": "market_analyst",
            "name": "已存在",
            "prompt_id": prompt_id,
        }],
    )
    service = _service_with_db(db)

    with pytest.raises(ValueError, match="编码"):
        asyncio.run(service.create_agent({
            "code": "market_analyst",
            "name": "市场分析师",
            "prompt_id": str(prompt_id),
        }))


def test_update_agent_moves_prompt_reference_count():
    old_prompt_id = ObjectId()
    new_prompt_id = ObjectId()
    agent_id = ObjectId()
    db = _FakeAgentDb(
        prompts=[
            {"_id": old_prompt_id, "enabled": True, "is_active": True, "agent_count": 1},
            {"_id": new_prompt_id, "enabled": True, "is_active": True, "agent_count": 0},
        ],
        agents=[{
            "_id": agent_id,
            "code": "market_analyst",
            "name": "市场分析师",
            "prompt_id": old_prompt_id,
            "enabled": True,
            "is_system": False,
            "tags": [],
            "parameters": {"max_tool_calls": 10, "timeout": 300, "retry_on_failure": False},
            "usage_count": 0,
        }],
    )
    service = _service_with_db(db)

    updated = asyncio.run(service.update_agent(str(agent_id), {"prompt_id": str(new_prompt_id)}))

    assert updated["prompt_id"] == str(new_prompt_id)
    assert db.prompts.docs[0]["agent_count"] == 0
    assert db.prompts.docs[1]["agent_count"] == 1


def test_update_agent_accepts_public_model_config_field():
    prompt_id = ObjectId()
    agent_id = ObjectId()
    db = _FakeAgentDb(
        prompts=[{"_id": prompt_id, "enabled": True, "is_active": True, "agent_count": 1}],
        agents=[{
            "_id": agent_id,
            "code": "market_analyst",
            "name": "市场分析师",
            "prompt_id": prompt_id,
            "model_config_agent": {"provider": "deepseek", "model": "deepseek-chat"},
            "enabled": True,
            "is_system": False,
            "tags": [],
            "parameters": {"max_tool_calls": 10, "timeout": 300, "retry_on_failure": False},
            "usage_count": 0,
        }],
    )
    service = _service_with_db(db)

    async def fake_provider_names():
        return {"openai", "deepseek"}

    service._get_configured_provider_names = fake_provider_names

    updated = asyncio.run(service.update_agent(str(agent_id), {
        "model_config": {"provider": "openai", "model": "gpt-4.1"},
    }))

    assert updated["model_config"] == {
        "provider": "openai",
        "model": "gpt-4.1",
    }
    assert "model_config_agent" not in updated
    assert db.agents.docs[0]["model_config_agent"] == {
        "provider": "openai",
        "model": "gpt-4.1",
    }



def test_update_agent_rejects_unknown_model_provider(monkeypatch):
    prompt_id = ObjectId()
    agent_id = ObjectId()
    db = _FakeAgentDb(
        prompts=[{"_id": prompt_id, "enabled": True, "is_active": True, "agent_count": 1}],
        agents=[{
            "_id": agent_id,
            "code": "market_analyst",
            "name": "市场分析师",
            "prompt_id": prompt_id,
            "enabled": True,
            "is_system": False,
            "tags": [],
            "parameters": {"max_tool_calls": 10, "timeout": 300, "retry_on_failure": False},
            "usage_count": 0,
        }],
    )
    service = _service_with_db(db)

    async def fake_provider_names():
        return {"deepseek"}

    monkeypatch.setattr(service, "_get_configured_provider_names", fake_provider_names)

    with pytest.raises(ValueError, match="模型厂商未配置: openai"):
        asyncio.run(service.update_agent(str(agent_id), {
            "model_config_agent": {"provider": "openai", "model": "gpt-4.1"},
        }))



def test_update_agent_allows_partial_model_config_as_default(monkeypatch):
    prompt_id = ObjectId()
    agent_id = ObjectId()
    db = _FakeAgentDb(
        prompts=[{"_id": prompt_id, "enabled": True, "is_active": True, "agent_count": 1}],
        agents=[{
            "_id": agent_id,
            "code": "market_analyst",
            "name": "市场分析师",
            "prompt_id": prompt_id,
            "enabled": True,
            "is_system": False,
            "tags": [],
            "parameters": {"max_tool_calls": 10, "timeout": 300, "retry_on_failure": False},
            "usage_count": 0,
        }],
    )
    service = _service_with_db(db)

    async def fake_provider_names():
        raise AssertionError("partial provider/model should not require validation")

    monkeypatch.setattr(service, "_get_configured_provider_names", fake_provider_names)

    updated = asyncio.run(service.update_agent(str(agent_id), {
        "model_config_agent": {"model": "gpt-4.1"},
    }))

    assert updated["model_config"] == {"model": "gpt-4.1"}



def test_update_agent_clears_model_config_with_public_null():
    prompt_id = ObjectId()
    agent_id = ObjectId()
    db = _FakeAgentDb(
        prompts=[{"_id": prompt_id, "enabled": True, "is_active": True, "agent_count": 1}],
        agents=[{
            "_id": agent_id,
            "code": "market_analyst",
            "name": "市场分析师",
            "prompt_id": prompt_id,
            "model_config_agent": {"provider": "deepseek", "model": "deepseek-chat"},
            "enabled": True,
            "is_system": False,
            "tags": [],
            "parameters": {"max_tool_calls": 10, "timeout": 300, "retry_on_failure": False},
            "usage_count": 0,
        }],
    )
    service = _service_with_db(db)

    updated = asyncio.run(service.update_agent(str(agent_id), {"model_config": None}))

    assert updated["model_config"] is None
    assert "model_config_agent" not in updated
    assert db.agents.docs[0]["model_config_agent"] is None


def test_update_agent_clear_prefers_internal_model_config_agent_over_legacy_field():
    prompt_id = ObjectId()
    agent_id = ObjectId()
    db = _FakeAgentDb(
        prompts=[{"_id": prompt_id, "enabled": True, "is_active": True, "agent_count": 1}],
        agents=[{
            "_id": agent_id,
            "code": "market_analyst",
            "name": "市场分析师",
            "prompt_id": prompt_id,
            "model_config": {"provider": "legacy", "model": "legacy-model"},
            "model_config_agent": {"provider": "deepseek", "model": "deepseek-chat"},
            "enabled": True,
            "is_system": False,
            "tags": [],
            "parameters": {"max_tool_calls": 10, "timeout": 300, "retry_on_failure": False},
            "usage_count": 0,
        }],
    )
    service = _service_with_db(db)

    updated = asyncio.run(service.update_agent(str(agent_id), {"model_config": None}))

    assert updated["model_config"] is None
    assert "model_config_agent" not in updated
    assert db.agents.docs[0]["model_config_agent"] is None


def test_delete_agent_rejects_system_agent():
    agent_id = ObjectId()
    db = _FakeAgentDb(agents=[{"_id": agent_id, "is_system": True}])
    service = _service_with_db(db)

    with pytest.raises(ValueError, match="系统 Agent 不能删除"):
        asyncio.run(service.delete_agent(str(agent_id)))


def test_delete_agent_decrements_prompt_count():
    prompt_id = ObjectId()
    agent_id = ObjectId()
    db = _FakeAgentDb(
        prompts=[{"_id": prompt_id, "enabled": True, "is_active": True, "agent_count": 1}],
        agents=[{
            "_id": agent_id,
            "code": "market_analyst",
            "is_system": False,
            "prompt_id": prompt_id,
        }],
    )
    service = _service_with_db(db)

    success = asyncio.run(service.delete_agent(str(agent_id)))

    assert success is True
    assert db.prompts.docs[0]["agent_count"] == 0
    assert db.agents.docs == []


def test_list_agents_supports_filters():
    prompt_id = ObjectId()
    db = _FakeAgentDb(
        prompts=[{"_id": prompt_id, "enabled": True, "is_active": True, "agent_count": 2}],
        agents=[
            {
                "_id": ObjectId(),
                "code": "market_analyst",
                "name": "市场分析师",
                "prompt_id": prompt_id,
                "enabled": True,
                "is_chat": False,
                "tags": ["分析"],
            },
            {
                "_id": ObjectId(),
                "code": "smart_assistant",
                "name": "智能助手",
                "prompt_id": prompt_id,
                "enabled": True,
                "is_chat": True,
                "tags": ["聊天"],
            },
        ],
    )
    service = _service_with_db(db)

    items, total = asyncio.run(service.list_agents(is_chat=True))

    assert total == 1
    assert items[0]["code"] == "smart_assistant"


def test_toggle_agent_updates_enabled_flag():
    agent_id = ObjectId()
    db = _FakeAgentDb(agents=[{
        "_id": agent_id,
        "code": "market_analyst",
        "enabled": True,
    }])
    service = _service_with_db(db)

    success = asyncio.run(service.toggle_agent(str(agent_id), False))

    assert success is True
    assert db.agents.docs[0]["enabled"] is False


def test_get_all_tags_returns_sorted_unique():
    prompt_id = ObjectId()
    db = _FakeAgentDb(agents=[
        {"_id": ObjectId(), "code": "a", "tags": ["分析", "盯盘"], "prompt_id": prompt_id},
        {"_id": ObjectId(), "code": "b", "tags": ["盯盘", "新闻"], "prompt_id": prompt_id},
    ])
    service = _service_with_db(db)

    tags = asyncio.run(service.get_all_tags())

    assert tags == sorted({"分析", "盯盘", "新闻"})


def test_record_usage_increments_counter_and_sets_last_used_at():
    agent_id = ObjectId()
    db = _FakeAgentDb(agents=[{
        "_id": agent_id,
        "code": "market_analyst",
        "usage_count": 4,
    }])
    service = _service_with_db(db)

    asyncio.run(service.record_usage(str(agent_id)))

    assert db.agents.docs[0]["usage_count"] == 5
    assert isinstance(db.agents.docs[0]["last_used_at"], datetime)


# ── Runtime spec tests ────────────────────────────────────────


class _FakePromptService:
    async def render_prompt(self, prompt_id, variables=None):
        return {
            "id": prompt_id,
            "code": "market_analyst_system",
            "name": "市场分析提示词",
            "rendered_blocks": [
                {"type": "text", "label": "系统角色", "content": "你是市场分析师。"},
                {"type": "messages_placeholder", "label": "对话历史"},
            ],
            "unresolved_variables": [],
        }


class _FakeToolService:
    async def get_tool_by_code(self, code):
        return {
            "code": code,
            "name": code,
            "description": "测试工具",
            "type": "builtin",
            "handler": "fake_handler",
            "parameters": [],
            "enabled": True,
        }


class _FakeLlm:
    pass


def test_build_agent_ignores_legacy_model_config_when_internal_field_is_none(monkeypatch):
    prompt_id = ObjectId()
    agent_id = ObjectId()
    db = _FakeAgentDb(
        prompts=[{
            "_id": prompt_id,
            "enabled": True,
            "is_active": True,
            "bind_tools": [],
            "agent_count": 1,
        }],
        agents=[{
            "_id": agent_id,
            "code": "market_analyst",
            "name": "市场分析师",
            "description": "",
            "prompt_id": prompt_id,
            "model_config": {"provider": "legacy", "model": "legacy-model"},
            "model_config_agent": None,
            "parameters": {"max_tool_calls": 10, "timeout": 300, "retry_on_failure": False},
            "tags": [],
            "is_chat": False,
            "is_system": False,
            "enabled": True,
            "usage_count": 0,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        }],
    )
    service = _service_with_db(db)
    captured_kwargs = {}

    async def fake_create_chat_llm(**kwargs):
        captured_kwargs.update(kwargs)
        return _FakeLlm()

    monkeypatch.setattr("app.services.agent_service.prompt_service", _FakePromptService())
    monkeypatch.setattr("app.services.agent_service.tool_service", _FakeToolService())
    monkeypatch.setattr("app.services.agent_service.HANDLER_MAP", {"fake_handler": lambda: "ok"})
    monkeypatch.setattr("app.services.agent_service.create_chat_llm", fake_create_chat_llm)

    spec = asyncio.run(service.build_agent(str(agent_id)))

    assert spec.agent_id == str(agent_id)
    assert "provider" not in captured_kwargs
    assert "model" not in captured_kwargs


def test_build_agent_returns_spec_with_agent_code(monkeypatch):
    prompt_id = ObjectId()
    agent_id = ObjectId()
    db = _FakeAgentDb(
        prompts=[{
            "_id": prompt_id,
            "enabled": True,
            "is_active": True,
            "bind_tools": [],
            "agent_count": 1,
        }],
        agents=[{
            "_id": agent_id,
            "code": "market_analyst",
            "name": "市场分析师",
            "description": "",
            "prompt_id": prompt_id,
            "model_config_agent": None,
            "parameters": {"max_tool_calls": 10, "timeout": 300, "retry_on_failure": False},
            "tags": [],
            "is_chat": False,
            "is_system": False,
            "enabled": True,
            "usage_count": 0,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        }],
    )
    service = _service_with_db(db)

    async def fake_create_chat_llm(**kwargs):
        return _FakeLlm()

    monkeypatch.setattr("app.services.agent_service.prompt_service", _FakePromptService())
    monkeypatch.setattr("app.services.agent_service.tool_service", _FakeToolService())
    monkeypatch.setattr("app.services.agent_service.HANDLER_MAP", {"fake_handler": lambda: "ok"})
    monkeypatch.setattr("app.services.agent_service.create_chat_llm", fake_create_chat_llm)

    spec = asyncio.run(service.build_agent(str(agent_id), variables={"ticker": "000001"}))

    assert spec.agent_id == str(agent_id)
    assert spec.agent_code == "market_analyst"
    assert spec.agent_name == "市场分析师"
    assert spec.system_prompt == "你是市场分析师。"
    assert spec.messages_placeholder == "对话历史"
    assert spec.tools == []


def test_build_agent_resolves_bound_tools(monkeypatch):
    prompt_id = ObjectId()
    agent_id = ObjectId()
    db = _FakeAgentDb(
        prompts=[{
            "_id": prompt_id,
            "enabled": True,
            "is_active": True,
            "bind_tools": ["get_data"],
            "agent_count": 1,
        }],
        agents=[{
            "_id": agent_id,
            "code": "market_analyst",
            "name": "市场分析师",
            "description": "",
            "prompt_id": prompt_id,
            "model_config_agent": {"provider": "deepseek", "model": "deepseek-chat"},
            "parameters": {"max_tool_calls": 10, "timeout": 300, "retry_on_failure": False},
            "tags": [],
            "is_chat": False,
            "is_system": False,
            "enabled": True,
            "usage_count": 0,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        }],
    )
    service = _service_with_db(db)

    async def fake_create_chat_llm(**kwargs):
        return _FakeLlm()

    class _ToolWithBuiltin:
        async def get_tool_by_code(self, code):
            return {
                "code": code,
                "name": code,
                "description": "工具描述",
                "type": "builtin",
                "handler": "fake_handler",
                "parameters": [{"name": "ticker", "type": "string", "required": True, "description": "代码"}],
                "enabled": True,
            }

    monkeypatch.setattr("app.services.agent_service.prompt_service", _FakePromptService())
    monkeypatch.setattr("app.services.agent_service.tool_service", _ToolWithBuiltin())
    monkeypatch.setattr("app.services.agent_service.HANDLER_MAP", {"fake_handler": lambda ticker: f"ok:{ticker}"})
    monkeypatch.setattr("app.services.agent_service.create_chat_llm", fake_create_chat_llm)

    spec = asyncio.run(service.build_agent(str(agent_id)))

    assert len(spec.tools) == 1
    assert spec.tools[0].name == "get_data"


def test_build_agent_passes_retry_on_failure_to_wrapped_tools(monkeypatch):
    prompt_id = ObjectId()
    agent_id = ObjectId()
    db = _FakeAgentDb(
        prompts=[{
            "_id": prompt_id,
            "enabled": True,
            "is_active": True,
            "bind_tools": ["get_data"],
            "agent_count": 1,
        }],
        agents=[{
            "_id": agent_id,
            "code": "market_analyst",
            "name": "市场分析师",
            "description": "",
            "prompt_id": prompt_id,
            "model_config_agent": {"provider": "deepseek", "model": "deepseek-chat"},
            "parameters": {"max_tool_calls": 10, "timeout": 300, "retry_on_failure": True},
            "tags": [],
            "is_chat": False,
            "is_system": False,
            "enabled": True,
            "usage_count": 0,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        }],
    )
    service = _service_with_db(db)
    captured = {}

    async def fake_create_chat_llm(**kwargs):
        return _FakeLlm()

    class _ToolWithBuiltin:
        async def get_tool_by_code(self, code):
            return {
                "code": code,
                "name": code,
                "description": "工具描述",
                "type": "builtin",
                "handler": "fake_handler",
                "parameters": [],
                "enabled": True,
            }

    def fake_wrap_as_base_tool(handler, tool_meta, retry_on_failure=False):
        captured["retry_on_failure"] = retry_on_failure
        captured["tool_code"] = tool_meta["code"]
        return type("_Tool", (), {"name": tool_meta["code"]})()

    monkeypatch.setattr("app.services.agent_service.prompt_service", _FakePromptService())
    monkeypatch.setattr("app.services.agent_service.tool_service", _ToolWithBuiltin())
    monkeypatch.setattr("app.services.agent_service.HANDLER_MAP", {"fake_handler": lambda: "ok"})
    monkeypatch.setattr("app.services.agent_service.create_chat_llm", fake_create_chat_llm)
    monkeypatch.setattr("app.services.agent_tool_adapter.wrap_as_base_tool", fake_wrap_as_base_tool)

    spec = asyncio.run(service.build_agent(str(agent_id)))

    assert len(spec.tools) == 1
    assert captured == {"retry_on_failure": True, "tool_code": "get_data"}


# ── Seed test ─────────────────────────────────────────────────


def test_seed_agent_payload_uses_prompt_code_not_hardcoded_id():
    from app.agents.seed_agents import AGENT_SEEDS

    market = next(seed for seed in AGENT_SEEDS if seed["code"] == "market_analyst")

    assert market["prompt_code"] == "market_analyst_system"
    assert "prompt_id" not in market
