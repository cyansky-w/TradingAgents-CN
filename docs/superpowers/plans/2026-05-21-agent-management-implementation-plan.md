# Agent Management Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build Agent 管理 so users can create, edit, seed, inspect, test-run, and optionally use managed Agents as runtime execution units backed by existing Prompt and Tool management.

**Architecture:** Agent records bind an enabled Prompt, model settings, runtime parameters, tags, and status. Prompt remains responsible for content, tool binding, and variable placeholders; Agent owns workflow output identity through `agent.code`, and runtime execution passes the full LLM output text as the Agent result. Backend work lands first with tests, then runtime/test-run, then frontend management UI, then optional Chat integration.

**Tech Stack:** FastAPI, Pydantic v2, Motor/MongoDB, LangChain/LangGraph, Vue 3 Composition API, Element Plus, TypeScript, pytest, vue-tsc.

**Commit note:** Do not create git commits unless the user explicitly authorizes commits in the execution session. Each task includes a checkpoint with exact files to stage when commit authorization exists.

---

## Scope Check

This plan implements the Agent 管理 module described in `docs/superpowers/specs/Agent 管理模块设计文档.md` after the updated prompt boundary decision:

- Prompt does not gain `output_schema`, `output_key`, or stored `variables`.
- Agent runtime output is complete LLM text.
- Workflow output identity defaults to `agent.code`.
- Structured extraction is deferred to future workflow mapping/post-processing.

The plan covers five testable increments:

1. Backend Agent schemas and CRUD service.
2. Runtime AgentSpec construction and tool wrapping.
3. Agent API and seed data.
4. Frontend API, routing, and management page.
5. Chat integration with `agent_id`.

---

## File Structure

### Backend files

- Create `app/models/agents.py`
  - Pydantic request models for Agent CRUD: `AgentModelConfig`, `AgentParameters`, `AgentCreate`, `AgentUpdate`.
- Create `app/services/agent_service.py`
  - MongoDB CRUD, prompt reference validation, prompt `agent_count` maintenance, tag/model lookup, usage tracking, runtime `AgentSpec` build.
- Create `app/services/agent_tool_adapter.py`
  - Converts tool metadata + handlers into LangChain `BaseTool` instances.
- Create `app/routers/agents.py`
  - REST endpoints under `/agents` for list/detail/create/update/delete/toggle/tags/models/seed/test-run.
- Create `app/agents/__init__.py`
  - Marks seed package.
- Create `app/agents/seed_agents.py`
  - Seeds system Agents by resolving active Prompt documents by code.
- Modify `app/main.py`
  - Import and register `agents_router.router` with `prefix="/api"`.
- Modify `app/chat/models.py`
  - Preserve `metadata` for `agent_id` on conversations.
- Modify `app/chat/schemas.py`
  - Add optional `agent_id` to `ConversationCreate` and `ConversationResponse` if frontend needs to display it.
- Modify `app/chat/service.py`
  - Store conversation `agent_id`; use `agent_service.build_agent()` when a conversation has `metadata.agent_id`.
- Modify `app/tools/handler_map.py`
  - Add `calls_llm` and `estimated_tokens` metadata to known LLM-calling tools.

### Backend tests

- Create `tests/services/test_agent_service.py`
  - CRUD, uniqueness, prompt validation, prompt counter maintenance, seed, runtime build unit tests with fake DB and monkeypatches.
- Create `tests/services/test_agent_tool_adapter.py`
  - Tool metadata to LangChain `BaseTool` wrapping tests.
- Create `tests/routers/test_agents_router.py`
  - API happy path and validation tests using monkeypatched auth/service.
- Create `tests/chat/test_chat_agent_integration.py`
  - Conversation `agent_id` persistence and stream path uses `AgentSpec` when present.

### Frontend files

- Create `frontend/src/api/agents.ts`
  - TypeScript types and API methods for Agent management.
- Create `frontend/src/views/AgentManagement/index.vue`
  - Left/right management page matching Tool/Prompt management style.
- Modify `frontend/src/router/index.ts`
  - Add `/agents` route under `BasicLayout`.
- Modify `frontend/src/components/Layout/SidebarMenu.vue`
  - Add `Agent 管理` under 管理中心 before 工具管理.
- Modify Chat frontend files only if current Chat UI supports conversation creation options in this repo; otherwise leave Chat UI unchanged and rely on API compatibility.

### Frontend verification

- Run `npm run type-check` from `frontend/`.
- Run `npm run build` from `frontend/`.
- For UI changes, start dev server with `npm run dev` from `frontend/` and manually verify the Agent 管理 route.

---

## Task 0: Implementation Safety and Impact Checks

**Files:**
- Read: `docs/superpowers/specs/Agent 管理模块设计文档.md`
- Read: `app/main.py`
- Read: `app/chat/service.py`
- Read: `app/services/prompt_service.py`
- Read: `app/services/tool_service.py`
- Read: `app/tools/handler_map.py`

- [ ] **Step 1: Confirm design source**

Read the current spec and confirm these implementation constraints before touching code:

```text
Prompt module remains unchanged for output contracts.
Agent output identity defaults to agent.code.
Agent runtime returns full LLM output text.
Prompt variables remain dynamic and are not stored on Agent.
```

- [ ] **Step 2: Run required GitNexus impact checks before symbol edits**

Project instructions require impact analysis before modifying functions/classes/methods. Before editing each existing symbol below, run the configured GitNexus impact tool for that symbol and record the direct callers/risk in the session:

```text
get_chat_llm_config
create_chat_llm
ChatService.create_conversation
ChatService.stream_response
HANDLER_MAP
TOOL_DEFINITIONS
FastAPI app router registration in app/main.py
```

If any result is HIGH or CRITICAL risk, stop and warn the user before editing.

- [ ] **Step 3: Create a short execution checklist**

Create session tasks for the implementation phases:

```text
1. Backend schemas
2. Agent service CRUD
3. Tool adapter and runtime build
4. Agent router and seed
5. Frontend API and page
6. Chat integration
7. Verification and review
```

---

## Task 1: Backend Agent Pydantic Models

**Files:**
- Create: `app/models/agents.py`
- Test: `tests/services/test_agent_service.py`

- [ ] **Step 1: Write failing model validation tests**

Create `tests/services/test_agent_service.py` with these initial tests:

```python
import pytest
from pydantic import ValidationError

from app.models.agents import AgentCreate, AgentModelConfig, AgentParameters, AgentUpdate


def test_agent_create_accepts_minimal_valid_payload():
    payload = AgentCreate(
        code="market_analyst",
        name="市场分析师",
        prompt_id="507f1f77bcf86cd799439011",
    )

    assert payload.code == "market_analyst"
    assert payload.name == "市场分析师"
    assert payload.description == ""
    assert payload.prompt_id == "507f1f77bcf86cd799439011"
    assert payload.model_config_agent is None
    assert payload.parameters.max_tool_calls == 10
    assert payload.parameters.timeout == 300
    assert payload.parameters.retry_on_failure is False
    assert payload.tags == []
    assert payload.is_chat is False
    assert payload.enabled is True


def test_agent_create_rejects_invalid_code():
    with pytest.raises(ValidationError):
        AgentCreate(code="Market-Analyst", name="市场分析师", prompt_id="507f1f77bcf86cd799439011")


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
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
pytest -c tests/pytest.ini tests/services/test_agent_service.py -v
```

Expected: FAIL with import error because `app.models.agents` does not exist.

- [ ] **Step 3: Implement `app/models/agents.py`**

Create `app/models/agents.py`:

```python
"""
Agent 管理请求 Schema
"""
from typing import List, Optional

from pydantic import BaseModel, Field


class AgentModelConfig(BaseModel):
    provider: Optional[str] = None
    model: Optional[str] = None
    temperature: float = Field(0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(4096, ge=1)


class AgentParameters(BaseModel):
    max_tool_calls: int = Field(10, ge=1)
    timeout: int = Field(300, ge=1)
    retry_on_failure: bool = False


class AgentCreate(BaseModel):
    code: str = Field(min_length=1, max_length=60, pattern=r"^[a-z][a-z0-9_]*$")
    name: str = Field(min_length=1, max_length=100)
    description: str = ""
    prompt_id: str
    model_config_agent: Optional[AgentModelConfig] = None
    parameters: AgentParameters = Field(default_factory=AgentParameters)
    tags: List[str] = []
    is_chat: bool = False
    enabled: bool = True


class AgentUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    prompt_id: Optional[str] = None
    model_config_agent: Optional[AgentModelConfig] = None
    parameters: Optional[AgentParameters] = None
    tags: Optional[List[str]] = None
    is_chat: Optional[bool] = None
    enabled: Optional[bool] = None
```

- [ ] **Step 4: Run model tests**

Run:

```bash
pytest -c tests/pytest.ini tests/services/test_agent_service.py -v
```

Expected: PASS for the five model tests.

- [ ] **Step 5: Checkpoint**

Files to stage if commits are authorized:

```bash
git add app/models/agents.py tests/services/test_agent_service.py
```

Commit message if authorized:

```text
feat(agents): add agent request models
```

---

## Task 2: Agent Service CRUD and Prompt Reference Counting

**Files:**
- Modify: `tests/services/test_agent_service.py`
- Create: `app/services/agent_service.py`

- [ ] **Step 1: Extend service tests with fake MongoDB collections**

Append these helpers to `tests/services/test_agent_service.py`:

```python
from datetime import datetime
from bson import ObjectId

from app.services.agent_service import AgentService


class _FakeCursor:
    def __init__(self, docs):
        self.docs = list(docs)
        self.skip_count = 0
        self.limit_count = len(self.docs)
        self.sort_args = None

    def sort(self, *args, **kwargs):
        self.sort_args = (args, kwargs)
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
            for value in doc.get(field, []):
                values.add(value)
        return list(values)

    def _apply_update(self, doc, update):
        for key, value in update.get("$set", {}).items():
            doc[key] = value
        for key, value in update.get("$inc", {}).items():
            doc[key] = doc.get(key, 0) + value

    def _matches(self, doc, query):
        for key, expected in query.items():
            if isinstance(expected, dict) and "$regex" in expected:
                import re
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
```

Append these tests:

```python
import asyncio


def _service_with_db(db):
    service = AgentService()
    service.db = db
    service._indexes_ensured = True
    return service


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


def test_delete_agent_rejects_system_agent():
    agent_id = ObjectId()
    db = _FakeAgentDb(agents=[{"_id": agent_id, "is_system": True}])
    service = _service_with_db(db)

    with pytest.raises(ValueError, match="系统 Agent 不能删除"):
        asyncio.run(service.delete_agent(str(agent_id)))
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
pytest -c tests/pytest.ini tests/services/test_agent_service.py -v
```

Expected: FAIL with import error because `app.services.agent_service` does not exist.

- [ ] **Step 3: Implement `AgentService` skeleton and formatting**

Create `app/services/agent_service.py`:

```python
"""
Agent 管理服务
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


def _iso(dt) -> str:
    if dt is None:
        return ""
    if isinstance(dt, str):
        return dt
    return dt.isoformat()


@dataclass(frozen=True)
class AgentSpec:
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

    def _format_doc(self, doc: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if doc is None:
            return None
        return {
            "id": str(doc.get("_id")),
            "code": doc.get("code", ""),
            "name": doc.get("name", ""),
            "description": doc.get("description", ""),
            "prompt_id": str(doc.get("prompt_id", "")),
            "model_config_agent": doc.get("model_config_agent"),
            "parameters": doc.get("parameters", {"max_tool_calls": 10, "timeout": 300, "retry_on_failure": False}),
            "tags": doc.get("tags", []),
            "is_chat": doc.get("is_chat", False),
            "is_system": doc.get("is_system", False),
            "enabled": doc.get("enabled", True),
            "usage_count": doc.get("usage_count", 0),
            "last_used_at": _iso(doc.get("last_used_at")),
            "created_at": _iso(doc.get("created_at")),
            "updated_at": _iso(doc.get("updated_at")),
        }
```

- [ ] **Step 4: Implement prompt validation and CRUD methods**

Add these methods to `AgentService` before the module singleton:

```python
    async def _get_enabled_prompt(self, prompt_id: str) -> Dict[str, Any]:
        db = await self._get_db()
        prompt_oid = self._prompt_object_id(prompt_id)
        prompt = await db.prompts.find_one({"_id": prompt_oid, "enabled": True, "is_active": True})
        if not prompt:
            raise ValueError("提示词不存在或未启用")
        return prompt

    async def _check_code_unique(self, code: str) -> bool:
        db = await self._get_db()
        return await db.agents.find_one({"code": code}) is None

    async def _check_name_unique(self, name: str) -> bool:
        db = await self._get_db()
        return await db.agents.find_one({"name": name}) is None

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
        docs = await db.agents.find(query).sort("name", 1).skip(skip).limit(page_size).to_list(length=page_size)
        return [self._format_doc(doc) for doc in docs], total

    async def get_agent(self, agent_id: str) -> Optional[Dict[str, Any]]:
        db = await self._get_db()
        await self.ensure_indexes()
        return self._format_doc(await db.agents.find_one({"_id": self._object_id(agent_id)}))

    async def get_agent_by_code(self, code: str) -> Optional[Dict[str, Any]]:
        db = await self._get_db()
        await self.ensure_indexes()
        return self._format_doc(await db.agents.find_one({"code": code}))

    async def create_agent(self, data: Dict[str, Any]) -> Dict[str, Any]:
        db = await self._get_db()
        await self.ensure_indexes()
        code = data.get("code", "")
        name = data.get("name", "")
        if not await self._check_code_unique(code):
            raise ValueError(f"编码 '{code}' 已存在")
        if not await self._check_name_unique(name):
            raise ValueError(f"名称 '{name}' 已存在")
        prompt = await self._get_enabled_prompt(data["prompt_id"])
        now = datetime.utcnow()
        doc = {
            "code": code,
            "name": name,
            "description": data.get("description", ""),
            "prompt_id": prompt["_id"],
            "model_config_agent": data.get("model_config_agent"),
            "parameters": data.get("parameters", {"max_tool_calls": 10, "timeout": 300, "retry_on_failure": False}),
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
        return self._format_doc(doc)

    async def update_agent(self, agent_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        db = await self._get_db()
        await self.ensure_indexes()
        agent_oid = self._object_id(agent_id)
        current = await db.agents.find_one({"_id": agent_oid})
        if not current:
            raise ValueError("Agent 不存在")
        update_fields = {}
        for key in ["name", "description", "model_config_agent", "parameters", "tags", "is_chat", "enabled"]:
            if key in data:
                update_fields[key] = data[key]
        if "prompt_id" in data:
            new_prompt = await self._get_enabled_prompt(data["prompt_id"])
            old_prompt_id = current.get("prompt_id")
            new_prompt_id = new_prompt["_id"]
            if old_prompt_id != new_prompt_id:
                await db.prompts.update_one({"_id": old_prompt_id}, {"$inc": {"agent_count": -1}})
                await db.prompts.update_one({"_id": new_prompt_id}, {"$inc": {"agent_count": 1}})
            update_fields["prompt_id"] = new_prompt_id
        if not update_fields:
            return self._format_doc(current)
        update_fields["updated_at"] = datetime.utcnow()
        await db.agents.update_one({"_id": agent_oid}, {"$set": update_fields})
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
        await db.prompts.update_one({"_id": current.get("prompt_id")}, {"$inc": {"agent_count": -1}})
        result = await db.agents.delete_one({"_id": agent_oid})
        return result.deleted_count > 0

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
        return sorted(tags)

    async def record_usage(self, agent_id: str) -> None:
        db = await self._get_db()
        await self.ensure_indexes()
        await db.agents.update_one(
            {"_id": self._object_id(agent_id)},
            {"$inc": {"usage_count": 1}, "$set": {"last_used_at": datetime.utcnow()}},
        )


agent_service = AgentService()
```

- [ ] **Step 5: Run service tests**

Run:

```bash
pytest -c tests/pytest.ini tests/services/test_agent_service.py -v
```

Expected: PASS for model and CRUD tests.

- [ ] **Step 6: Checkpoint**

Files to stage if commits are authorized:

```bash
git add app/services/agent_service.py tests/services/test_agent_service.py
```

Commit message if authorized:

```text
feat(agents): add agent CRUD service
```

---

## Task 3: Tool Adapter and Runtime AgentSpec Build

**Files:**
- Create: `app/services/agent_tool_adapter.py`
- Modify: `app/services/agent_service.py`
- Create: `tests/services/test_agent_tool_adapter.py`
- Modify: `tests/services/test_agent_service.py`

- [ ] **Step 1: Write tool adapter tests**

Create `tests/services/test_agent_tool_adapter.py`:

```python
import asyncio

import pytest

from app.services.agent_tool_adapter import build_args_schema, wrap_as_base_tool


def test_build_args_schema_maps_tool_parameters():
    schema = build_args_schema("sample_tool", [
        {"name": "ticker", "type": "string", "required": True, "description": "股票代码"},
        {"name": "look_back_days", "type": "integer", "required": False, "default": 30, "description": "回看天数"},
    ])

    fields = schema.model_fields
    assert "ticker" in fields
    assert "look_back_days" in fields
    assert fields["look_back_days"].default == 30


def test_wrap_as_base_tool_invokes_sync_handler():
    def handler(ticker: str):
        return f"data:{ticker}"

    tool = wrap_as_base_tool(handler, {
        "code": "get_data",
        "name": "获取数据",
        "description": "获取股票数据",
        "parameters": [{"name": "ticker", "type": "string", "required": True, "description": "股票代码"}],
    })

    assert tool.name == "get_data"
    assert tool.description == "获取股票数据"
    assert tool.invoke({"ticker": "000001"}) == "data:000001"


@pytest.mark.asyncio
async def test_wrap_as_base_tool_invokes_async_handler():
    async def handler(ticker: str):
        return f"async:{ticker}"

    tool = wrap_as_base_tool(handler, {
        "code": "get_data_async",
        "name": "获取数据",
        "description": "获取股票数据",
        "parameters": [{"name": "ticker", "type": "string", "required": True, "description": "股票代码"}],
    })

    assert await tool.ainvoke({"ticker": "000001"}) == "async:000001"
```

- [ ] **Step 2: Run adapter tests to verify failure**

Run:

```bash
pytest -c tests/pytest.ini tests/services/test_agent_tool_adapter.py -v
```

Expected: FAIL with import error because `agent_tool_adapter.py` does not exist.

- [ ] **Step 3: Implement `agent_tool_adapter.py`**

Create `app/services/agent_tool_adapter.py`:

```python
"""
Agent runtime tool adapter.
"""
from __future__ import annotations

import inspect
from typing import Any, Callable, Dict, List, Optional, Type

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field, create_model


_TYPE_MAP = {
    "string": str,
    "integer": int,
    "number": float,
    "boolean": bool,
    "array": list,
    "object": dict,
}


def build_args_schema(tool_code: str, parameters: List[Dict[str, Any]]) -> Type[BaseModel]:
    fields = {}
    for param in parameters:
        name = param.get("name", "")
        if not name:
            continue
        py_type = _TYPE_MAP.get(param.get("type", "string"), str)
        description = param.get("description") or ""
        required = param.get("required", True)
        default = ... if required else param.get("default", None)
        fields[name] = (py_type, Field(default, description=description))
    return create_model(f"{tool_code.title().replace('_', '')}Args", **fields)


def wrap_as_base_tool(handler: Callable, tool_meta: Dict[str, Any]):
    tool_code = tool_meta.get("code") or tool_meta.get("name") or getattr(handler, "name", "agent_tool")
    description = tool_meta.get("description") or tool_meta.get("name") or tool_code
    args_schema = build_args_schema(tool_code, tool_meta.get("parameters", []))

    async def coroutine(**kwargs):
        result = handler(**kwargs)
        if inspect.isawaitable(result):
            return await result
        return result

    def func(**kwargs):
        result = handler(**kwargs)
        if inspect.isawaitable(result):
            raise RuntimeError(f"Tool '{tool_code}' is async; use ainvoke")
        return result

    return StructuredTool.from_function(
        func=func,
        coroutine=coroutine,
        name=tool_code,
        description=description,
        args_schema=args_schema,
    )
```

- [ ] **Step 4: Run adapter tests**

Run:

```bash
pytest -c tests/pytest.ini tests/services/test_agent_tool_adapter.py -v
```

Expected: PASS.

- [ ] **Step 5: Write AgentSpec runtime build tests**

Append to `tests/services/test_agent_service.py`:

```python
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


def test_build_agent_returns_spec_with_agent_code(monkeypatch):
    prompt_id = ObjectId()
    agent_id = ObjectId()
    db = _FakeAgentDb(agents=[{
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
    }])
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
    assert len(spec.tools) == 0
```

- [ ] **Step 6: Run AgentSpec test to verify failure**

Run:

```bash
pytest -c tests/pytest.ini tests/services/test_agent_service.py::test_build_agent_returns_spec_with_agent_code -v
```

Expected: FAIL because `build_agent()` is not implemented.

- [ ] **Step 7: Implement `build_agent()`**

Add imports near the top of `app/services/agent_service.py`:

```python
from app.chat.llm_factory import create_chat_llm
from app.prompts.seed_prompts import PROMPT_SEEDS
from app.services.agent_tool_adapter import wrap_as_base_tool
from app.services.prompt_service import prompt_service
from app.services.tool_service import tool_service
from app.tools.handler_map import HANDLER_MAP
```

Add these methods to `AgentService`:

```python
    def _rendered_prompt_to_system(self, rendered_blocks: List[Dict[str, Any]]) -> Tuple[str, Optional[str]]:
        text_parts = []
        placeholder_label = None
        for block in rendered_blocks:
            if block.get("type") == "text":
                text_parts.append(block.get("content", ""))
            elif block.get("type") == "messages_placeholder":
                placeholder_label = block.get("label", "对话历史")
        return "\n\n".join(part for part in text_parts if part), placeholder_label

    async def _resolve_agent_tools(self, bind_tools: List[str]) -> List[Any]:
        tools = []
        for code in bind_tools:
            tool_meta = await tool_service.get_tool_by_code(code)
            if not tool_meta or not tool_meta.get("enabled", True):
                continue
            if tool_meta.get("type") != "builtin":
                continue
            handler_name = tool_meta.get("handler")
            handler = HANDLER_MAP.get(handler_name)
            if not handler:
                continue
            tools.append(wrap_as_base_tool(handler, tool_meta))
        return tools

    async def build_agent(self, agent_id: str, variables: Optional[Dict[str, str]] = None) -> AgentSpec:
        db = await self._get_db()
        await self.ensure_indexes()
        doc = await db.agents.find_one({"_id": self._object_id(agent_id)})
        if not doc:
            raise ValueError("Agent 不存在")
        if not doc.get("enabled", True):
            raise ValueError("Agent 未启用")
        prompt = await db.prompts.find_one({"_id": doc["prompt_id"], "enabled": True, "is_active": True})
        if not prompt:
            raise ValueError("绑定提示词不存在或未启用")
        rendered = await prompt_service.render_prompt(str(prompt["_id"]), variables or {})
        system_prompt, messages_placeholder = self._rendered_prompt_to_system(rendered.get("rendered_blocks", []))
        tools = await self._resolve_agent_tools(prompt.get("bind_tools", []))
        model_config = doc.get("model_config_agent") or {}
        provider = model_config.get("provider")
        model = model_config.get("model")
        llm_kwargs = {
            "streaming": True,
            "temperature": model_config.get("temperature", 0.7),
            "max_tokens": model_config.get("max_tokens", 4096),
        }
        if provider and model:
            llm_kwargs["provider"] = provider
            llm_kwargs["model"] = model
        llm = await create_chat_llm(**llm_kwargs)
        return AgentSpec(
            agent_id=str(doc["_id"]),
            agent_code=doc.get("code", ""),
            agent_name=doc.get("name", ""),
            system_prompt=system_prompt,
            messages_placeholder=messages_placeholder,
            tools=tools,
            llm=llm,
            parameters=AgentParameters(**doc.get("parameters", {})),
        )
```

- [ ] **Step 8: Run runtime tests**

Run:

```bash
pytest -c tests/pytest.ini tests/services/test_agent_tool_adapter.py tests/services/test_agent_service.py -v
```

Expected: PASS.

- [ ] **Step 9: Checkpoint**

Files to stage if commits are authorized:

```bash
git add app/services/agent_tool_adapter.py app/services/agent_service.py tests/services/test_agent_tool_adapter.py tests/services/test_agent_service.py
```

Commit message if authorized:

```text
feat(agents): build runtime agent specs
```

---

## Task 4: Agent Seed Data and Router API

**Files:**
- Create: `app/agents/__init__.py`
- Create: `app/agents/seed_agents.py`
- Create: `app/routers/agents.py`
- Modify: `app/main.py:31-34`, `app/main.py:770-771`
- Create: `tests/routers/test_agents_router.py`
- Modify: `tests/services/test_agent_service.py`

- [ ] **Step 1: Add seed service tests**

Append to `tests/services/test_agent_service.py`:

```python
def test_seed_agent_payload_uses_prompt_code_not_hardcoded_id():
    from app.agents.seed_agents import AGENT_SEEDS

    market = next(seed for seed in AGENT_SEEDS if seed["code"] == "market_analyst")

    assert market["prompt_code"] == "market_analyst_system"
    assert "prompt_id" not in market
```

- [ ] **Step 2: Create seed package and data**

Create `app/agents/__init__.py`:

```python
"""Agent seed package."""
```

Create `app/agents/seed_agents.py`:

```python
"""
Agent seed data.
"""
from __future__ import annotations

from typing import Dict

from app.services.agent_service import agent_service
from app.services.prompt_service import prompt_service


AGENT_SEEDS = [
    {
        "code": "market_analyst",
        "name": "市场分析师",
        "description": "分析市场整体走势、价格趋势和技术指标",
        "prompt_code": "market_analyst_system",
        "tags": ["分析", "技术面"],
        "is_chat": False,
    },
    {
        "code": "news_analyst",
        "name": "新闻分析师",
        "description": "分析新闻事件和宏观信息对标的的影响",
        "prompt_code": "news_analyst_system",
        "tags": ["分析", "新闻"],
        "is_chat": False,
    },
    {
        "code": "fundamentals_analyst",
        "name": "基本面分析师",
        "description": "分析财务、估值和公司基本面",
        "prompt_code": "fundamentals_analyst_system",
        "tags": ["分析", "基本面"],
        "is_chat": False,
    },
    {
        "code": "technical_analyst",
        "name": "技术分析师",
        "description": "分析技术指标、趋势和交易信号",
        "prompt_code": "technical_analyst_system",
        "tags": ["分析", "技术面"],
        "is_chat": False,
    },
    {
        "code": "smart_assistant",
        "name": "智能助手",
        "description": "通用 AI 聊天助手",
        "prompt_code": "smart_assistant_system",
        "tags": ["聊天", "助手"],
        "is_chat": True,
    },
]


async def seed_agents_to_db() -> Dict[str, object]:
    created = 0
    skipped = 0
    failed = []
    for seed in AGENT_SEEDS:
        try:
            existing = await agent_service.get_agent_by_code(seed["code"])
            if existing:
                skipped += 1
                continue
            prompt = await prompt_service.get_active_prompt(seed["prompt_code"])
            if not prompt or not prompt.get("enabled", True):
                failed.append(f"{seed['code']}: prompt {seed['prompt_code']} 不存在或未启用")
                continue
            await agent_service.create_agent({
                "code": seed["code"],
                "name": seed["name"],
                "description": seed["description"],
                "prompt_id": prompt["id"],
                "tags": seed["tags"],
                "is_chat": seed["is_chat"],
                "is_system": True,
                "enabled": True,
            })
            created += 1
        except Exception as exc:
            failed.append(f"{seed['code']}: {exc}")
    return {"created": created, "skipped": skipped, "failed": failed, "total": len(AGENT_SEEDS)}
```

- [ ] **Step 3: Write router tests**

Create `tests/routers/test_agents_router.py`:

```python
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers import agents


class _FakeAgentService:
    async def list_agents(self, **kwargs):
        return ([{"id": "agent-1", "code": "market_analyst", "name": "市场分析师"}], 1)

    async def get_agent(self, agent_id):
        if agent_id == "missing":
            return None
        return {"id": agent_id, "code": "market_analyst", "name": "市场分析师"}

    async def create_agent(self, data):
        return {"id": "agent-1", **data}

    async def update_agent(self, agent_id, data):
        return {"id": agent_id, "code": "market_analyst", **data}

    async def delete_agent(self, agent_id):
        return agent_id != "missing"

    async def toggle_agent(self, agent_id, enabled):
        return agent_id != "missing"

    async def get_all_tags(self):
        return ["分析"]


@pytest.fixture
def client(monkeypatch):
    app = FastAPI()
    app.include_router(agents.router, prefix="/api")
    monkeypatch.setattr(agents, "agent_service", _FakeAgentService())
    app.dependency_overrides[agents.get_current_user] = lambda: {"id": "user-1"}
    return TestClient(app)


def test_list_agents(client):
    response = client.get("/api/agents/")

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"]["total"] == 1
    assert body["data"]["items"][0]["code"] == "market_analyst"


def test_get_agent_missing_returns_404(client):
    response = client.get("/api/agents/missing")

    assert response.status_code == 404


def test_create_agent(client):
    response = client.post("/api/agents/", json={
        "code": "market_analyst",
        "name": "市场分析师",
        "prompt_id": "507f1f77bcf86cd799439011",
    })

    assert response.status_code == 200
    assert response.json()["data"]["code"] == "market_analyst"


def test_toggle_agent_requires_enabled(client):
    response = client.put("/api/agents/agent-1/toggle", json={})

    assert response.status_code == 400
```

- [ ] **Step 4: Run router tests to verify failure**

Run:

```bash
pytest -c tests/pytest.ini tests/routers/test_agents_router.py -v
```

Expected: FAIL because `app.routers.agents` does not exist.

- [ ] **Step 5: Implement `app/routers/agents.py`**

Create `app/routers/agents.py`:

```python
"""
Agent 管理 API
"""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

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
    search: Optional[str] = Query(None),
    tag: Optional[str] = Query(None),
    enabled: Optional[bool] = Query(None),
    is_chat: Optional[bool] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
):
    agents, total = await agent_service.list_agents(
        search=search,
        tag=tag,
        enabled=enabled,
        is_chat=is_chat,
        page=page,
        page_size=page_size,
    )
    return ok({"items": agents, "total": total, "page": page, "page_size": page_size})


@router.get("/tags")
async def get_all_tags(current_user: dict = Depends(get_current_user)):
    return ok(await agent_service.get_all_tags())


@router.get("/models")
async def get_available_models(current_user: dict = Depends(get_current_user)):
    from app.services.config_service import config_service

    return ok(await config_service.get_llm_providers())


@router.get("/{agent_id}")
async def get_agent(agent_id: str, current_user: dict = Depends(get_current_user)):
    agent = await agent_service.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent 不存在")
    return ok(agent)


@router.post("/")
async def create_agent(payload: AgentCreate, current_user: dict = Depends(get_current_user)):
    try:
        data = payload.model_dump(exclude_none=True)
        agent = await agent_service.create_agent(data)
        return ok(agent, "创建成功")
    except ValueError as exc:
        raise HTTPException(status_code=_agent_error_status(str(exc)), detail=str(exc))


@router.put("/{agent_id}")
async def update_agent(agent_id: str, payload: AgentUpdate, current_user: dict = Depends(get_current_user)):
    try:
        data = payload.model_dump(exclude_none=True)
        agent = await agent_service.update_agent(agent_id, data)
        return ok(agent, "更新成功")
    except ValueError as exc:
        raise HTTPException(status_code=_agent_error_status(str(exc)), detail=str(exc))


@router.delete("/{agent_id}")
async def delete_agent(agent_id: str, current_user: dict = Depends(get_current_user)):
    try:
        success = await agent_service.delete_agent(agent_id)
        if not success:
            raise HTTPException(status_code=404, detail="Agent 不存在")
        return ok({"id": agent_id}, "删除成功")
    except ValueError as exc:
        raise HTTPException(status_code=_agent_error_status(str(exc)), detail=str(exc))


@router.put("/{agent_id}/toggle")
async def toggle_agent(agent_id: str, payload: dict, current_user: dict = Depends(get_current_user)):
    enabled = payload.get("enabled")
    if enabled is None:
        raise HTTPException(status_code=400, detail="缺少 enabled 字段")
    success = await agent_service.toggle_agent(agent_id, enabled)
    if not success:
        raise HTTPException(status_code=404, detail="Agent 不存在")
    return ok({"id": agent_id, "enabled": enabled}, "状态更新成功")


@router.post("/seed")
async def seed_agents(current_user: dict = Depends(get_current_user)):
    from app.agents.seed_agents import seed_agents_to_db

    result = await seed_agents_to_db()
    return ok(result, "Agent 数据初始化完成")
```

- [ ] **Step 6: Register router in `app/main.py`**

Modify import section around existing tools/prompts imports:

```python
from app.routers import agents as agents_router
from app.routers import tools as tools_router
from app.routers import prompts as prompts_router
```

Modify router registration near `tools_router` and `prompts_router`:

```python
app.include_router(agents_router.router, prefix="/api", tags=["Agent 管理"])
app.include_router(tools_router.router, prefix="/api", tags=["工具管理"])
app.include_router(prompts_router.router, prefix="/api", tags=["提示词管理"])
```

- [ ] **Step 7: Run router and seed tests**

Run:

```bash
pytest -c tests/pytest.ini tests/routers/test_agents_router.py tests/services/test_agent_service.py::test_seed_agent_payload_uses_prompt_code_not_hardcoded_id -v
```

Expected: PASS.

- [ ] **Step 8: Checkpoint**

Files to stage if commits are authorized:

```bash
git add app/agents/__init__.py app/agents/seed_agents.py app/routers/agents.py app/main.py tests/routers/test_agents_router.py tests/services/test_agent_service.py
```

Commit message if authorized:

```text
feat(agents): expose agent management API
```

---

## Task 5: Agent Test-Run Endpoint

**Files:**
- Modify: `app/routers/agents.py`
- Modify: `tests/routers/test_agents_router.py`

- [ ] **Step 1: Write test-run router test**

Append to `tests/routers/test_agents_router.py`:

```python
def test_test_run_agent_builds_spec(client, monkeypatch):
    class _Spec:
        agent_id = "agent-1"
        agent_code = "market_analyst"
        agent_name = "市场分析师"
        system_prompt = "你是市场分析师。"
        messages_placeholder = "对话历史"
        tools = []
        parameters = type("Params", (), {"timeout": 300, "max_tool_calls": 10, "retry_on_failure": False})()

        class _Llm:
            async def astream(self, messages):
                yield type("Chunk", (), {"content": "测试输出"})()

        llm = _Llm()

    async def fake_build_agent(agent_id, variables=None):
        return _Spec()

    monkeypatch.setattr(agents.agent_service, "build_agent", fake_build_agent)

    response = client.post("/api/agents/agent-1/test-run", json={"message": "分析 000001", "variables": {}})

    assert response.status_code == 200
    assert "text/event-stream" in response.headers["content-type"]
```

- [ ] **Step 2: Run test to verify failure**

Run:

```bash
pytest -c tests/pytest.ini tests/routers/test_agents_router.py::test_test_run_agent_builds_spec -v
```

Expected: FAIL with 404 because `/test-run` endpoint is missing.

- [ ] **Step 3: Implement test-run endpoint**

Add imports to `app/routers/agents.py`:

```python
import json
from fastapi.responses import StreamingResponse
from langchain_core.messages import HumanMessage, SystemMessage
```

Add helper and endpoint before `/seed`:

```python
async def _agent_test_run_events(agent_id: str, payload: dict):
    try:
        spec = await agent_service.build_agent(agent_id, payload.get("variables") or {})
        messages = [SystemMessage(content=spec.system_prompt), HumanMessage(content=payload.get("message", ""))]
        if spec.tools:
            from langgraph.prebuilt import create_react_agent
            agent = create_react_agent(spec.llm, spec.tools)
            async for chunk in agent.astream({"messages": messages}, stream_mode="messages"):
                msg = chunk[0] if isinstance(chunk, tuple) else chunk
                content = getattr(msg, "content", "")
                if content and isinstance(content, str):
                    yield f"event: token\ndata: {json.dumps({'content': content}, ensure_ascii=False)}\n\n"
        else:
            async for chunk in spec.llm.astream(messages):
                content = getattr(chunk, "content", "")
                if content:
                    yield f"event: token\ndata: {json.dumps({'content': content}, ensure_ascii=False)}\n\n"
        await agent_service.record_usage(agent_id)
        yield f"event: done\ndata: {json.dumps({'agent_code': spec.agent_code}, ensure_ascii=False)}\n\n"
    except Exception as exc:
        logger.exception("Agent test run failed")
        yield f"event: error\ndata: {json.dumps({'message': str(exc)}, ensure_ascii=False)}\n\n"


@router.post("/{agent_id}/test-run")
async def test_run_agent(agent_id: str, payload: dict, current_user: dict = Depends(get_current_user)):
    message = payload.get("message")
    if not message:
        raise HTTPException(status_code=400, detail="缺少 message 字段")
    return StreamingResponse(_agent_test_run_events(agent_id, payload), media_type="text/event-stream")
```

- [ ] **Step 4: Run test-run tests**

Run:

```bash
pytest -c tests/pytest.ini tests/routers/test_agents_router.py -v
```

Expected: PASS.

- [ ] **Step 5: Checkpoint**

Files to stage if commits are authorized:

```bash
git add app/routers/agents.py tests/routers/test_agents_router.py
```

Commit message if authorized:

```text
feat(agents): add agent test run endpoint
```

---

## Task 6: Tool LLM-Cost Metadata

**Files:**
- Modify: `app/tools/handler_map.py`
- Modify: `app/services/tool_service.py`
- Modify: `frontend/src/api/tools.ts`
- Test: existing tool service tests in `tests/services/test_tool_service_search.py`

- [ ] **Step 1: Add metadata expectations to tool service test**

Append to `tests/services/test_tool_service_search.py`:

```python
def test_format_doc_includes_calls_llm_metadata():
    service = ToolService()
    doc = {
        "_id": "tool-1",
        "code": "get_stock_news_openai",
        "name": "get_stock_news_openai",
        "description": "AI news",
        "type": "builtin",
        "calls_llm": True,
        "estimated_tokens": 2000,
    }

    formatted = service._format_doc(doc)

    assert formatted["calls_llm"] is True
    assert formatted["estimated_tokens"] == 2000
```

- [ ] **Step 2: Run test to verify failure**

Run:

```bash
pytest -c tests/pytest.ini tests/services/test_tool_service_search.py::test_format_doc_includes_calls_llm_metadata -v
```

Expected: FAIL because `_format_doc()` does not return the new fields.

- [ ] **Step 3: Update tool metadata formatting**

In `app/services/tool_service.py`, add fields to `_format_doc()` return dict:

```python
"calls_llm": doc.get("calls_llm", False),
"estimated_tokens": doc.get("estimated_tokens", 0),
```

- [ ] **Step 4: Mark known LLM-calling tools**

In `app/tools/handler_map.py`, add these fields to the tool definition dictionaries for known tools:

```python
"calls_llm": True,
"estimated_tokens": 2000,
```

Apply to these codes:

```text
get_stock_news_openai
get_global_news_openai
get_stock_news_unified
get_realtime_stock_news
```

Also change seed defaults around line 113 so docs without explicit values retain defaults:

```python
"output_schema": None,
"agent_count": 0,
"calls_llm": tool_def.get("calls_llm", False),
"estimated_tokens": tool_def.get("estimated_tokens", 0),
```

- [ ] **Step 5: Update frontend tool type**

In `frontend/src/api/tools.ts`, extend `Tool`:

```ts
calls_llm: boolean
estimated_tokens: number
```

- [ ] **Step 6: Run tests and type-check**

Run:

```bash
pytest -c tests/pytest.ini tests/services/test_tool_service_search.py -v
```

Expected: PASS.

Run:

```bash
cd frontend && npm run type-check
```

Expected: PASS.

- [ ] **Step 7: Checkpoint**

Files to stage if commits are authorized:

```bash
git add app/tools/handler_map.py app/services/tool_service.py frontend/src/api/tools.ts tests/services/test_tool_service_search.py
```

Commit message if authorized:

```text
feat(tools): expose llm cost metadata
```

---

## Task 7: Frontend Agent API and Route/Menu

**Files:**
- Create: `frontend/src/api/agents.ts`
- Modify: `frontend/src/router/index.ts`
- Modify: `frontend/src/components/Layout/SidebarMenu.vue`

- [ ] **Step 1: Create Agent API module**

Create `frontend/src/api/agents.ts`:

```ts
import { ApiClient } from './request'
import type { ApiResponse } from './request'

export interface AgentModelConfig {
  provider?: string
  model?: string
  temperature?: number
  max_tokens?: number
}

export interface AgentParameters {
  max_tool_calls: number
  timeout: number
  retry_on_failure: boolean
}

export interface Agent {
  id: string
  code: string
  name: string
  description: string
  prompt_id: string
  model_config_agent?: AgentModelConfig | null
  parameters: AgentParameters
  tags: string[]
  is_chat: boolean
  is_system: boolean
  enabled: boolean
  usage_count: number
  last_used_at?: string
  created_at: string
  updated_at: string
}

export interface AgentListParams {
  search?: string
  tag?: string
  enabled?: boolean
  is_chat?: boolean
  page?: number
  page_size?: number
}

export interface AgentListResult {
  items: Agent[]
  total: number
  page: number
  page_size: number
}

export interface AgentCreateDto {
  code: string
  name: string
  description?: string
  prompt_id: string
  model_config_agent?: AgentModelConfig | null
  parameters?: Partial<AgentParameters>
  tags?: string[]
  is_chat?: boolean
  enabled?: boolean
}

export interface AgentUpdateDto {
  name?: string
  description?: string
  prompt_id?: string
  model_config_agent?: AgentModelConfig | null
  parameters?: Partial<AgentParameters>
  tags?: string[]
  is_chat?: boolean
  enabled?: boolean
}

export interface AgentSeedResult {
  created: number
  skipped: number
  failed: string[]
  total: number
}

export const agentsApi = {
  async list(params?: AgentListParams): Promise<ApiResponse<AgentListResult>> {
    return await ApiClient.get<AgentListResult>('/api/agents/', params)
  },

  async get(id: string): Promise<ApiResponse<Agent>> {
    return await ApiClient.get<Agent>(`/api/agents/${id}`)
  },

  async create(payload: AgentCreateDto): Promise<ApiResponse<Agent>> {
    return await ApiClient.post<Agent>('/api/agents/', payload)
  },

  async update(id: string, payload: AgentUpdateDto): Promise<ApiResponse<Agent>> {
    return await ApiClient.put<Agent>(`/api/agents/${id}`, payload)
  },

  async remove(id: string): Promise<ApiResponse<{ id: string }>> {
    return await ApiClient.delete<{ id: string }>(`/api/agents/${id}`)
  },

  async toggle(id: string, enabled: boolean): Promise<ApiResponse<{ id: string; enabled: boolean }>> {
    return await ApiClient.put<{ id: string; enabled: boolean }>(`/api/agents/${id}/toggle`, { enabled })
  },

  async getTags(): Promise<ApiResponse<string[]>> {
    return await ApiClient.get<string[]>('/api/agents/tags')
  },

  async seed(): Promise<ApiResponse<AgentSeedResult>> {
    return await ApiClient.post<AgentSeedResult>('/api/agents/seed')
  }
}
```

- [ ] **Step 2: Add route**

In `frontend/src/router/index.ts`, add a route near `/tools` and `/prompts` routes. Use this exact route object:

```ts
{
  path: '/agents',
  name: 'AgentManagement',
  component: BasicLayout,
  meta: { title: 'Agent 管理', icon: 'UserFilled', requiresAuth: true },
  children: [
    {
      path: '',
      name: 'AgentManagementHome',
      component: () => import('@/views/AgentManagement/index.vue'),
      meta: { title: 'Agent 管理', requiresAuth: true }
    }
  ]
},
```

- [ ] **Step 3: Add sidebar menu item**

In `frontend/src/components/Layout/SidebarMenu.vue`, import `UserFilled` from `@element-plus/icons-vue`.

Add this as the first item under 管理中心:

```vue
<el-menu-item index="/agents">
  <el-icon><UserFilled /></el-icon>
  <template #title>Agent 管理</template>
</el-menu-item>
```

- [ ] **Step 4: Run frontend type-check to verify missing view failure**

Run:

```bash
cd frontend && npm run type-check
```

Expected: FAIL because `@/views/AgentManagement/index.vue` does not exist.

- [ ] **Step 5: Checkpoint**

Files to stage if commits are authorized after Task 8 creates the view:

```bash
git add frontend/src/api/agents.ts frontend/src/router/index.ts frontend/src/components/Layout/SidebarMenu.vue
```

Commit message if authorized after Task 8:

```text
feat(frontend): add agent management route and api
```

---

## Task 8: Frontend Agent Management Page

**Files:**
- Create: `frontend/src/views/AgentManagement/index.vue`

- [ ] **Step 1: Create initial Agent management page**

Create `frontend/src/views/AgentManagement/index.vue` with this first complete version:

```vue
<template>
  <div class="agent-management">
    <div class="page-header">
      <h2>Agent 管理</h2>
      <div class="header-actions">
        <el-button type="primary" @click="showCreateDialog">
          <el-icon><Plus /></el-icon> 新建
        </el-button>
        <el-button @click="handleSeed" :loading="seedLoading">
          <el-icon><Refresh /></el-icon> 初始化种子
        </el-button>
      </div>
    </div>

    <el-row :gutter="20" class="flex-1">
      <el-col :span="7">
        <div class="filter-section">
          <el-input v-model="searchText" placeholder="搜索 Agent..." prefix-icon="Search" clearable @input="handleSearch" />
          <div class="filter-row">
            <el-select v-model="filterTag" placeholder="标签" clearable @change="loadAgents()">
              <el-option v-for="tag in allTags" :key="tag" :label="tag" :value="tag" />
            </el-select>
            <el-select v-model="filterEnabled" placeholder="状态" clearable @change="loadAgents()">
              <el-option label="已启用" :value="true" />
              <el-option label="已禁用" :value="false" />
            </el-select>
          </div>
          <div class="filter-row">
            <el-select v-model="filterIsChat" placeholder="类型" clearable @change="loadAgents()">
              <el-option label="工作流 Agent" :value="false" />
              <el-option label="聊天助手" :value="true" />
            </el-select>
          </div>
        </div>

        <el-scrollbar class="agent-list">
          <div
            v-for="agent in agents"
            :key="agent.id"
            class="agent-item"
            :class="{ active: selectedAgent?.id === agent.id }"
            @click="selectAgent(agent)"
          >
            <div class="agent-item-header">
              <span class="agent-name">{{ agent.name }}</span>
              <el-switch :model-value="agent.enabled" size="small" @click.stop @change="(val: any) => handleToggle(agent, !!val)" />
            </div>
            <div class="agent-item-meta">
              <el-tag size="small" :type="agent.is_chat ? 'success' : 'primary'">{{ agent.is_chat ? 'chat' : 'workflow' }}</el-tag>
              <el-tag v-if="agent.is_system" size="small" type="info">系统</el-tag>
            </div>
            <div class="agent-code mono">{{ agent.code }}</div>
            <div class="agent-item-tags">
              <el-tag v-for="tag in agent.tags.slice(0, 3)" :key="tag" size="small" type="info" class="mini-tag">{{ tag }}</el-tag>
            </div>
          </div>
          <el-empty v-if="agents.length === 0 && !listLoading" description="暂无 Agent" />
        </el-scrollbar>
      </el-col>

      <el-col :span="17">
        <div v-if="selectedAgent" class="detail-panel">
          <div class="detail-header">
            <div class="detail-title-row">
              <el-input v-if="editing" v-model="editForm.name" class="edit-name-input" />
              <h3 v-else>{{ selectedAgent.name }}</h3>
              <div class="detail-badges">
                <el-tag :type="selectedAgent.is_chat ? 'success' : 'primary'">{{ selectedAgent.is_chat ? '聊天助手' : '工作流 Agent' }}</el-tag>
                <el-tag v-if="selectedAgent.is_system" type="info">系统 Agent</el-tag>
              </div>
            </div>
          </div>

          <div class="detail-body">
            <div class="section">
              <h4>基本信息</h4>
              <el-form label-width="110px" size="small">
                <el-form-item label="编码"><span class="mono">{{ selectedAgent.code }}</span></el-form-item>
                <el-form-item label="输出名"><span class="mono">{{ selectedAgent.code }}</span></el-form-item>
                <el-form-item label="名称"><el-input v-if="editing" v-model="editForm.name" /><span v-else>{{ selectedAgent.name }}</span></el-form-item>
                <el-form-item label="描述"><el-input v-if="editing" v-model="editForm.description" type="textarea" :rows="2" /><span v-else>{{ selectedAgent.description || '-' }}</span></el-form-item>
                <el-form-item label="聊天助手"><el-switch v-if="editing" v-model="editForm.is_chat" /><span v-else>{{ selectedAgent.is_chat ? '是' : '否' }}</span></el-form-item>
              </el-form>
            </div>

            <div class="section">
              <h4>提示词绑定</h4>
              <el-select v-if="editing" v-model="editForm.prompt_id" filterable placeholder="选择提示词" style="width: 100%">
                <el-option v-for="prompt in promptOptions" :key="prompt.id" :label="`${prompt.name} v${prompt.version}`" :value="prompt.id" />
              </el-select>
              <span v-else>{{ currentPromptName }}</span>
            </div>

            <div class="section">
              <h4>提示词规格概览</h4>
              <el-collapse>
                <el-collapse-item title="绑定工具" name="tools">
                  <el-tag v-for="toolCode in selectedPrompt?.bind_tools || []" :key="toolCode" class="tag-chip">{{ toolCode }}</el-tag>
                  <span v-if="!selectedPrompt || selectedPrompt.bind_tools.length === 0" class="text-muted">未绑定工具</span>
                </el-collapse-item>
                <el-collapse-item title="工作流输出" name="output">
                  <div>输出名：<span class="mono">{{ selectedAgent.code }}</span></div>
                  <div class="text-muted">Agent 执行后的完整 LLM 输出文本会以该名称传递给工作流下游节点。</div>
                </el-collapse-item>
              </el-collapse>
            </div>

            <div class="section">
              <h4>模型配置</h4>
              <el-switch v-if="editing" v-model="useDefaultModel" active-text="使用系统默认" />
              <span v-else>{{ selectedAgent.model_config_agent ? '自定义模型' : '系统默认' }}</span>
              <div v-if="editing && !useDefaultModel" class="model-grid">
                <el-input v-model="editForm.model_config_agent.provider" placeholder="provider" />
                <el-input v-model="editForm.model_config_agent.model" placeholder="model" />
                <el-input-number v-model="editForm.model_config_agent.temperature" :min="0" :max="2" :step="0.1" />
                <el-input-number v-model="editForm.model_config_agent.max_tokens" :min="1" />
              </div>
            </div>

            <div class="section">
              <h4>运行参数</h4>
              <el-form label-width="110px" size="small">
                <el-form-item label="最大工具调用"><el-input-number v-if="editing" v-model="editForm.parameters.max_tool_calls" :min="1" /><span v-else>{{ selectedAgent.parameters.max_tool_calls }}</span></el-form-item>
                <el-form-item label="超时秒数"><el-input-number v-if="editing" v-model="editForm.parameters.timeout" :min="1" /><span v-else>{{ selectedAgent.parameters.timeout }}</span></el-form-item>
                <el-form-item label="失败重试"><el-switch v-if="editing" v-model="editForm.parameters.retry_on_failure" /><span v-else>{{ selectedAgent.parameters.retry_on_failure ? '是' : '否' }}</span></el-form-item>
              </el-form>
            </div>

            <div class="section">
              <h4>标签</h4>
              <el-select v-if="editing" v-model="editForm.tags" multiple filterable allow-create default-first-option style="width: 100%">
                <el-option v-for="tag in allTags" :key="tag" :label="tag" :value="tag" />
              </el-select>
              <div v-else>
                <el-tag v-for="tag in selectedAgent.tags" :key="tag" class="tag-chip">{{ tag }}</el-tag>
                <span v-if="selectedAgent.tags.length === 0" class="text-muted">无标签</span>
              </div>
            </div>
          </div>

          <div class="detail-footer">
            <template v-if="editing">
              <el-button type="primary" @click="handleSave" :loading="saveLoading">保存</el-button>
              <el-button @click="cancelEdit">取消</el-button>
            </template>
            <template v-else>
              <el-button type="primary" @click="startEdit">编辑</el-button>
              <el-button type="success" @click="showTestDialog">测试运行</el-button>
              <el-button v-if="!selectedAgent.is_system" type="danger" @click="handleDelete">删除</el-button>
            </template>
          </div>
        </div>
        <el-empty v-else description="选择左侧 Agent 查看详情" />
      </el-col>
    </el-row>

    <el-dialog v-model="createVisible" title="新建 Agent" width="640px" destroy-on-close>
      <el-form :model="createForm" label-width="100px" size="small">
        <el-form-item label="编码" required><el-input v-model="createForm.code" placeholder="market_analyst" /></el-form-item>
        <el-form-item label="名称" required><el-input v-model="createForm.name" /></el-form-item>
        <el-form-item label="描述"><el-input v-model="createForm.description" type="textarea" :rows="2" /></el-form-item>
        <el-form-item label="提示词" required>
          <el-select v-model="createForm.prompt_id" filterable placeholder="选择提示词" style="width: 100%">
            <el-option v-for="prompt in promptOptions" :key="prompt.id" :label="`${prompt.name} v${prompt.version}`" :value="prompt.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="聊天助手"><el-switch v-model="createForm.is_chat" /></el-form-item>
        <el-form-item label="标签">
          <el-select v-model="createForm.tags" multiple filterable allow-create default-first-option style="width: 100%">
            <el-option v-for="tag in allTags" :key="tag" :label="tag" :value="tag" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createVisible = false">取消</el-button>
        <el-button type="primary" @click="handleCreate" :loading="createLoading">创建</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="testVisible" title="测试运行" width="760px" destroy-on-close>
      <el-input v-model="testMessage" type="textarea" :rows="4" placeholder="请输入测试消息" />
      <div class="test-actions"><el-button type="primary" @click="handleTestRun" :loading="testLoading">发送</el-button></div>
      <pre class="test-output">{{ testOutput }}</pre>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Refresh } from '@element-plus/icons-vue'
import { agentsApi } from '@/api/agents'
import type { Agent, AgentCreateDto } from '@/api/agents'
import { promptsApi } from '@/api/prompts'
import type { Prompt } from '@/api/prompts'

const agents = ref<Agent[]>([])
const selectedAgent = ref<Agent | null>(null)
const selectedPrompt = ref<Prompt | null>(null)
const promptOptions = ref<Prompt[]>([])
const allTags = ref<string[]>([])
const total = ref(0)
const listLoading = ref(false)
const saveLoading = ref(false)
const createLoading = ref(false)
const seedLoading = ref(false)
const testLoading = ref(false)
const editing = ref(false)
const createVisible = ref(false)
const testVisible = ref(false)
const searchText = ref('')
const filterTag = ref('')
const filterEnabled = ref<boolean | string>('')
const filterIsChat = ref<boolean | string>('')
const testMessage = ref('')
const testOutput = ref('')
const useDefaultModel = ref(true)
let searchTimer: ReturnType<typeof setTimeout>

const editForm = reactive({
  name: '',
  description: '',
  prompt_id: '',
  model_config_agent: { provider: '', model: '', temperature: 0.7, max_tokens: 4096 },
  parameters: { max_tool_calls: 10, timeout: 300, retry_on_failure: false },
  tags: [] as string[],
  is_chat: false,
  enabled: true
})

const createForm = reactive<AgentCreateDto>({
  code: '',
  name: '',
  description: '',
  prompt_id: '',
  tags: [],
  is_chat: false,
  enabled: true
})

const currentPromptName = computed(() => selectedPrompt.value ? `${selectedPrompt.value.name} v${selectedPrompt.value.version}` : '-')

async function loadAgents() {
  listLoading.value = true
  try {
    const res = await agentsApi.list({
      search: searchText.value || undefined,
      tag: filterTag.value || undefined,
      enabled: filterEnabled.value === '' ? undefined : Boolean(filterEnabled.value),
      is_chat: filterIsChat.value === '' ? undefined : Boolean(filterIsChat.value),
      page: 1,
      page_size: 100
    })
    if (res.success) {
      agents.value = res.data.items
      total.value = res.data.total
      if (!selectedAgent.value && agents.value.length > 0) selectAgent(agents.value[0])
    }
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '加载 Agent 列表失败')
  } finally {
    listLoading.value = false
  }
}

async function loadPrompts() {
  const res = await promptsApi.list({ enabled: true, page: 1, page_size: 100 })
  if (res.success) promptOptions.value = res.data.items
}

async function loadTags() {
  const res = await agentsApi.getTags()
  if (res.success) allTags.value = res.data
}

async function selectAgent(agent: Agent) {
  if (editing.value) cancelEdit()
  selectedAgent.value = agent
  fillEditForm(agent)
  selectedPrompt.value = promptOptions.value.find(prompt => prompt.id === agent.prompt_id) || null
  if (!selectedPrompt.value && agent.prompt_id) {
    const res = await promptsApi.get(agent.prompt_id)
    if (res.success) selectedPrompt.value = res.data
  }
}

function fillEditForm(agent: Agent) {
  editForm.name = agent.name
  editForm.description = agent.description
  editForm.prompt_id = agent.prompt_id
  editForm.parameters = { ...agent.parameters }
  editForm.tags = [...agent.tags]
  editForm.is_chat = agent.is_chat
  editForm.enabled = agent.enabled
  useDefaultModel.value = !agent.model_config_agent
  editForm.model_config_agent = agent.model_config_agent
    ? { provider: agent.model_config_agent.provider || '', model: agent.model_config_agent.model || '', temperature: agent.model_config_agent.temperature ?? 0.7, max_tokens: agent.model_config_agent.max_tokens ?? 4096 }
    : { provider: '', model: '', temperature: 0.7, max_tokens: 4096 }
}

function handleSearch() {
  clearTimeout(searchTimer)
  searchTimer = setTimeout(() => loadAgents(), 300)
}

function startEdit() {
  if (!selectedAgent.value) return
  fillEditForm(selectedAgent.value)
  editing.value = true
}

function cancelEdit() {
  editing.value = false
  if (selectedAgent.value) fillEditForm(selectedAgent.value)
}

function showCreateDialog() {
  createForm.code = ''
  createForm.name = ''
  createForm.description = ''
  createForm.prompt_id = ''
  createForm.tags = []
  createForm.is_chat = false
  createVisible.value = true
}

async function handleCreate() {
  createLoading.value = true
  try {
    const res = await agentsApi.create(createForm)
    if (res.success) {
      ElMessage.success('创建成功')
      createVisible.value = false
      await loadAgents()
      selectAgent(res.data)
    }
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '创建失败')
  } finally {
    createLoading.value = false
  }
}

async function handleSave() {
  if (!selectedAgent.value) return
  saveLoading.value = true
  try {
    const res = await agentsApi.update(selectedAgent.value.id, {
      name: editForm.name,
      description: editForm.description,
      prompt_id: editForm.prompt_id,
      model_config_agent: useDefaultModel.value ? null : editForm.model_config_agent,
      parameters: editForm.parameters,
      tags: editForm.tags,
      is_chat: editForm.is_chat,
      enabled: editForm.enabled
    })
    if (res.success) {
      ElMessage.success('保存成功')
      selectedAgent.value = res.data
      fillEditForm(res.data)
      editing.value = false
      await loadAgents()
    }
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '保存失败')
  } finally {
    saveLoading.value = false
  }
}

async function handleToggle(agent: Agent, enabled: boolean) {
  try {
    const res = await agentsApi.toggle(agent.id, enabled)
    if (res.success) agent.enabled = enabled
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '操作失败')
  }
}

async function handleDelete() {
  if (!selectedAgent.value) return
  await ElMessageBox.confirm(`确认删除 Agent「${selectedAgent.value.name}」？`, '删除确认', { type: 'warning' })
  await agentsApi.remove(selectedAgent.value.id)
  ElMessage.success('删除成功')
  selectedAgent.value = null
  await loadAgents()
}

async function handleSeed() {
  seedLoading.value = true
  try {
    const res = await agentsApi.seed()
    if (res.success) {
      ElMessage.success(`创建 ${res.data.created} 个，跳过 ${res.data.skipped} 个`)
      await loadAgents()
      await loadTags()
    }
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '初始化失败')
  } finally {
    seedLoading.value = false
  }
}

function showTestDialog() {
  testMessage.value = ''
  testOutput.value = ''
  testVisible.value = true
}

async function handleTestRun() {
  if (!selectedAgent.value || !testMessage.value.trim()) return
  testLoading.value = true
  testOutput.value = ''
  try {
    const response = await fetch(`/api/agents/${selectedAgent.value.id}/test-run`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: testMessage.value, variables: {} })
    })
    const reader = response.body?.getReader()
    const decoder = new TextDecoder()
    if (!reader) return
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      testOutput.value += decoder.decode(value, { stream: true })
    }
  } catch (e: any) {
    ElMessage.error(e?.message || '测试运行失败')
  } finally {
    testLoading.value = false
  }
}

watch(() => editForm.prompt_id, async (promptId) => {
  selectedPrompt.value = promptOptions.value.find(prompt => prompt.id === promptId) || null
})

onMounted(async () => {
  await Promise.all([loadPrompts(), loadTags()])
  await loadAgents()
})
</script>

<style scoped lang="scss">
.agent-management { display: flex; flex-direction: column; height: 100%; gap: 16px; }
.page-header { display: flex; align-items: center; justify-content: space-between; }
.header-actions { display: flex; gap: 8px; }
.filter-section { display: flex; flex-direction: column; gap: 8px; margin-bottom: 12px; }
.filter-row { display: flex; gap: 8px; }
.agent-list { height: calc(100vh - 230px); }
.agent-item { padding: 12px; border: 1px solid var(--el-border-color); border-radius: 8px; margin-bottom: 10px; cursor: pointer; }
.agent-item.active { border-color: var(--el-color-primary); background: var(--el-color-primary-light-9); }
.agent-item-header, .detail-title-row { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.agent-name { font-weight: 600; }
.agent-item-meta, .agent-item-tags, .detail-badges { display: flex; gap: 6px; margin-top: 6px; flex-wrap: wrap; }
.agent-code, .mono { font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; }
.detail-panel { border: 1px solid var(--el-border-color); border-radius: 8px; display: flex; flex-direction: column; height: calc(100vh - 160px); }
.detail-header, .detail-footer { padding: 16px; border-bottom: 1px solid var(--el-border-color); }
.detail-footer { border-top: 1px solid var(--el-border-color); border-bottom: none; display: flex; justify-content: flex-end; gap: 8px; }
.detail-body { padding: 16px; overflow: auto; flex: 1; }
.section { margin-bottom: 20px; }
.section h4 { margin: 0 0 12px; }
.tag-chip { margin: 0 6px 6px 0; }
.text-muted { color: var(--el-text-color-secondary); }
.model-grid { display: grid; grid-template-columns: 1fr 1fr 160px 160px; gap: 8px; margin-top: 12px; }
.test-actions { margin: 12px 0; }
.test-output { min-height: 180px; padding: 12px; border: 1px solid var(--el-border-color); border-radius: 6px; white-space: pre-wrap; }
</style>
```

- [ ] **Step 2: Run frontend type-check**

Run:

```bash
cd frontend && npm run type-check
```

Expected: PASS.

- [ ] **Step 3: Run frontend build**

Run:

```bash
cd frontend && npm run build
```

Expected: PASS.

- [ ] **Step 4: Manual UI verification**

Run:

```bash
cd frontend && npm run dev
```

Manual checks:

```text
1. Open the Vite URL shown by the dev server.
2. Log in if the app requires auth.
3. Open 管理中心 → Agent 管理.
4. Confirm list area renders without console errors.
5. Click 初始化种子 and confirm success/error toast is readable.
6. Create a test Agent using an enabled Prompt.
7. Select the Agent and confirm output name equals Agent code.
8. Edit name/tags/runtime parameters and save.
9. Toggle enabled state from the list.
10. Open test-run dialog and submit a short message.
```

- [ ] **Step 5: Checkpoint**

Files to stage if commits are authorized:

```bash
git add frontend/src/api/agents.ts frontend/src/views/AgentManagement/index.vue frontend/src/router/index.ts frontend/src/components/Layout/SidebarMenu.vue
```

Commit message if authorized:

```text
feat(frontend): add agent management page
```

---

## Task 9: Chat Integration With Managed Agents

**Files:**
- Modify: `app/chat/models.py`
- Modify: `app/chat/schemas.py`
- Modify: `app/chat/service.py`
- Create: `tests/chat/test_chat_agent_integration.py`

- [ ] **Step 1: Write chat integration tests**

Create `tests/chat/test_chat_agent_integration.py`:

```python
import pytest

from app.chat.models import Conversation
from app.chat.schemas import ConversationCreate
from app.chat.service import ChatService


class _FakeMemory:
    async def add_to_buffer(self, *args, **kwargs):
        return None

    async def get_buffer(self, *args, **kwargs):
        return []

    async def recall_long_term(self, *args, **kwargs):
        return []


class _FakeConversations:
    def __init__(self):
        self.docs = []

    async def insert_one(self, doc):
        self.docs.append(doc)

    async def find_one(self, query):
        for doc in self.docs:
            if all(doc.get(key) == value for key, value in query.items()):
                return doc
        return None

    async def update_one(self, query, update):
        return None


class _FakeMessages:
    async def insert_one(self, doc):
        return None


class _ChatServiceForTest(ChatService):
    def __init__(self):
        super().__init__(_FakeMemory())
        self._conversations = _FakeConversations()
        self._messages = _FakeMessages()

    @property
    def conversations_col(self):
        return self._conversations

    @property
    def messages_col(self):
        return self._messages


@pytest.mark.asyncio
async def test_create_conversation_stores_agent_id_in_metadata():
    service = _ChatServiceForTest()

    conv = await service.create_conversation("user-1", ConversationCreate(title="Agent Chat", agent_id="agent-1"))

    assert conv.metadata["agent_id"] == "agent-1"
    assert service._conversations.docs[0]["metadata"]["agent_id"] == "agent-1"
```

- [ ] **Step 2: Run test to verify failure**

Run:

```bash
pytest -c tests/pytest.ini tests/chat/test_chat_agent_integration.py -v
```

Expected: FAIL because `ConversationCreate` has no `agent_id` and service does not store it.

- [ ] **Step 3: Add `agent_id` to chat schema**

In `app/chat/schemas.py`, change `ConversationCreate`:

```python
class ConversationCreate(BaseModel):
    title: str = "New Chat"
    model_provider: str = ""
    model_name: str = ""
    system_prompt: str = ""
    agent_id: Optional[str] = None
```

If frontend needs to display the selected Agent later, also add to `ConversationResponse`:

```python
agent_id: Optional[str] = None
```

- [ ] **Step 4: Store agent metadata in `create_conversation()`**

In `app/chat/service.py`, change `create_conversation()` construction:

```python
conv = Conversation(
    user_id=user_id,
    title=data.title or "New Chat",
    model_provider=data.model_provider,
    model_name=data.model_name,
    system_prompt=data.system_prompt,
    metadata={"agent_id": data.agent_id} if data.agent_id else {},
)
```

Update `ConversationResponse` builders in `app/chat/service.py` and `app/chat/router.py` if `agent_id` was added to response:

```python
agent_id=(doc.get("metadata") or {}).get("agent_id")
```

- [ ] **Step 5: Run metadata test**

Run:

```bash
pytest -c tests/pytest.ini tests/chat/test_chat_agent_integration.py::test_create_conversation_stores_agent_id_in_metadata -v
```

Expected: PASS.

- [ ] **Step 6: Write stream integration test with fake AgentSpec**

Append to `tests/chat/test_chat_agent_integration.py`:

```python
@pytest.mark.asyncio
async def test_stream_response_uses_agent_service_when_conversation_has_agent(monkeypatch):
    service = _ChatServiceForTest()
    conv = Conversation(user_id="user-1", title="Agent Chat", metadata={"agent_id": "agent-1"})
    await service.conversations_col.insert_one(conv.model_dump())

    class _Spec:
        agent_id = "agent-1"
        agent_code = "market_analyst"
        agent_name = "市场分析师"
        system_prompt = "你是市场分析师。"
        messages_placeholder = "对话历史"
        tools = []
        parameters = type("Params", (), {"timeout": 300, "max_tool_calls": 10, "retry_on_failure": False})()

        class _Llm:
            async def astream(self, messages):
                yield type("Chunk", (), {"content": "agent-output"})()

        llm = _Llm()

    class _FakeAgentService:
        async def build_agent(self, agent_id, variables=None):
            assert agent_id == "agent-1"
            return _Spec()

        async def record_usage(self, agent_id):
            assert agent_id == "agent-1"

    monkeypatch.setattr("app.chat.service.agent_service", _FakeAgentService())

    events = []
    async for event in service.stream_response("user-1", conv.id, "hello"):
        events.append(event)
        if event["event"] == "done":
            break

    assert any(event["event"] == "token" and event["data"]["content"] == "agent-output" for event in events)
```

- [ ] **Step 7: Run stream test to verify failure**

Run:

```bash
pytest -c tests/pytest.ini tests/chat/test_chat_agent_integration.py::test_stream_response_uses_agent_service_when_conversation_has_agent -v
```

Expected: FAIL because `stream_response()` does not import/use `agent_service`.

- [ ] **Step 8: Modify `ChatService.stream_response()`**

Add import to `app/chat/service.py`:

```python
from app.services.agent_service import agent_service
```

In `stream_response()` after loading `conv` and before building messages, branch on `agent_id`:

```python
agent_id = (conv.metadata or {}).get("agent_id") if conv else None
agent_spec = None
if agent_id:
    agent_spec = await agent_service.build_agent(agent_id)
    system_prompt = agent_spec.system_prompt
else:
    system_prompt = await self._get_system_prompt(conversation_id)
```

Then replace tool/LLM creation block with:

```python
if agent_spec:
    tools = agent_spec.tools or None
    llm = agent_spec.llm
else:
    tools = tool_registry.get_all() if not tool_registry.empty else None
    llm = await create_chat_llm(
        streaming=True,
        temperature=0.7,
        max_tokens=4096,
        extra_body={"thinking": {"type": "disabled"}} if tools else None,
    )
```

After saving assistant message, record usage when `agent_id` exists:

```python
if agent_id:
    await agent_service.record_usage(agent_id)
```

- [ ] **Step 9: Run chat integration tests**

Run:

```bash
pytest -c tests/pytest.ini tests/chat/test_chat_agent_integration.py -v
```

Expected: PASS.

- [ ] **Step 10: Checkpoint**

Files to stage if commits are authorized:

```bash
git add app/chat/models.py app/chat/schemas.py app/chat/service.py tests/chat/test_chat_agent_integration.py
```

Commit message if authorized:

```text
feat(chat): allow conversations to use managed agents
```

---

## Task 10: Full Verification and Review

**Files:**
- Verify all changed backend and frontend files.

- [ ] **Step 1: Run backend unit tests for changed areas**

Run:

```bash
pytest -c tests/pytest.ini tests/services/test_agent_service.py tests/services/test_agent_tool_adapter.py tests/routers/test_agents_router.py tests/chat/test_chat_agent_integration.py tests/services/test_tool_service_search.py -v
```

Expected: PASS.

- [ ] **Step 2: Run broader backend smoke tests**

Run:

```bash
pytest -c tests/pytest.ini tests/services tests/routers tests/chat -v
```

Expected: PASS or only known unrelated failures. If unrelated failures appear, record the exact failing test names and error messages before continuing.

- [ ] **Step 3: Run frontend type-check**

Run:

```bash
cd frontend && npm run type-check
```

Expected: PASS.

- [ ] **Step 4: Run frontend production build**

Run:

```bash
cd frontend && npm run build
```

Expected: PASS.

- [ ] **Step 5: Manual UI verification**

Run:

```bash
cd frontend && npm run dev
```

Manual verification checklist:

```text
1. Agent 管理 menu item appears under 管理中心.
2. /agents route loads without console errors.
3. Seed button calls /api/agents/seed and reports created/skipped/failed.
4. Agent list displays code/name/tags/enabled state.
5. Detail panel shows output name equal to Agent code.
6. Create, edit, toggle, and delete flows show success/error messages.
7. Prompt selector lists enabled prompts.
8. Bound tools overview displays prompt.bind_tools.
9. Test-run dialog streams events without crashing the page.
```

- [ ] **Step 6: Run security and consistency review**

Check these items manually in the diff:

```text
1. No API keys, tokens, or secrets are logged or committed.
2. Agent code is immutable after creation.
3. Agent delete decrements prompt.agent_count.
4. Agent prompt change decrements old prompt and increments new prompt.
5. System Agent delete is blocked.
6. Prompt output schema was not added.
7. Variables were not added as stored prompt or agent fields.
8. agent.code is used only as output identity, not as a user-controlled code execution path.
9. Tool handler execution only resolves handlers from HANDLER_MAP.
10. Chat behavior without agent_id remains unchanged.
```

- [ ] **Step 7: Request code review**

Use `superpowers:requesting-code-review` or an OMC `code-reviewer` agent to review the completed implementation against this plan and `docs/superpowers/specs/Agent 管理模块设计文档.md`.

- [ ] **Step 8: Final status report**

Report the exact verification evidence:

```text
Backend changed-area tests: command + pass/fail count
Frontend type-check: command + exit status
Frontend build: command + exit status
Manual UI: checked items + gaps
Code review: findings + fixes or accepted risks
```

---

## Self-Review

### Spec coverage

- Prompt module boundary is covered by not adding prompt `output_schema`, `output_key`, or stored `variables`.
- Agent data model is covered by Tasks 1 and 2.
- Agent CRUD and prompt reference count maintenance are covered by Task 2.
- Agent runtime build and `agent.code` output identity are covered by Task 3.
- Agent API, model lookup, seed, and test-run are covered by Tasks 4 and 5.
- Tool `calls_llm` metadata is covered by Task 6.
- Frontend route, menu, API, list/detail/edit/create/test-run are covered by Tasks 7 and 8.
- Chat integration with `agent_id` is covered by Task 9.
- Verification and review are covered by Task 10.

### Placeholder scan

This plan intentionally defers future structured extraction to a later module because the approved design excludes it from Prompt and Agent base models. No implementation task contains placeholder wording or unspecified “handle edge cases” language.

### Type consistency

- Backend uses `model_config_agent` consistently to match the design document.
- Runtime `AgentSpec` uses `agent_code`, not `output_schema`.
- Frontend types use `model_config_agent`, `parameters`, `is_chat`, and `enabled` consistently with backend payloads.
- Prompt variables remain dynamic and are not represented as Agent fields.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-05-21-agent-management-implementation-plan.md`. Two execution options:

**1. Subagent-Driven (recommended)** - dispatch a fresh subagent per task, review between tasks, fast iteration.

**2. Inline Execution** - execute tasks in this session using executing-plans, batch execution with checkpoints.

Which approach?
