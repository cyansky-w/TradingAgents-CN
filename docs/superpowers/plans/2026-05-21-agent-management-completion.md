# Agent Management Completion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete the existing Agent management module draft against the approved Agent management design and the 11 missing items identified in review.

**Architecture:** Keep the current backend service/router/frontend page structure. Normalize public API fields around `model_config` while preserving safe internal Pydantic aliases, make Agent runtime parameters enforce execution limits, and complete the Chat + Agent selection path from frontend to backend. Avoid broad rewrites; each task tightens one boundary and has focused tests.

**Tech Stack:** FastAPI, Pydantic v2, MongoDB/Motor, LangChain/LangGraph, Vue 3 Composition API, TypeScript, Element Plus, pytest.

---

## File Structure

- Modify: `app/models/agents.py` — expose `model_config` in serialized API payloads while retaining internal alias safety.
- Modify: `app/services/agent_service.py` — add model provider validation, `get_agent_by_name`, normalized formatting, and runtime helper behavior.
- Modify: `app/routers/agents.py` — enforce test-run timeout/recursion config and emit cleaner SSE events.
- Modify: `app/chat/service.py` — apply Agent runtime limits in streaming and wire non-streaming Chat to Agent when present.
- Modify: `frontend/src/api/agents.ts` — switch public TS contract to `model_config`, add test-run event types if needed.
- Modify: `frontend/src/views/AgentManagement/index.vue` — complete create/edit model config, prompt overview, SSE parsing, pagination/loading, and test-run UI.
- Modify: Chat frontend files under `frontend/src/views/Chat/` and related API module once located — add Agent selector and pass `agent_id` on conversation creation.
- Modify: `tests/services/test_agent_service.py` — cover provider validation, `get_agent_by_name`, and `model_config` output.
- Modify: `tests/routers/test_agents_router.py` — cover test-run runtime config and model field contract.
- Modify: `tests/chat/test_chat_agent_integration.py` — cover streaming/non-streaming Agent path.
- Add or modify frontend tests only if this repo already has Vue test setup; otherwise verify via dev server/browser.

---

### Task 1: Normalize Agent model configuration API contract

**Files:**
- Modify: `app/models/agents.py`
- Modify: `app/services/agent_service.py`
- Modify: `frontend/src/api/agents.ts`
- Test: `tests/services/test_agent_service.py`
- Test: `tests/routers/test_agents_router.py`

- [ ] **Step 1: Add failing backend tests for `model_config` public field**

Add assertions to existing service/router tests:

```python
# tests/services/test_agent_service.py

def test_format_doc_exposes_model_config_public_name():
    prompt_id = ObjectId()
    agent_id = ObjectId()
    db = _FakeAgentDb(agents=[{
        "_id": agent_id,
        "code": "market_analyst",
        "name": "市场分析师",
        "prompt_id": prompt_id,
        "model_config_agent": {"provider": "deepseek", "model": "deepseek-chat", "temperature": 0.3, "max_tokens": 4096},
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
```

- [ ] **Step 2: Run the targeted failing test**

Run:

```bash
MSYS_NO_PATHCONV=1 docker exec tradingagents-backend bash -lc "cd /app && python -m pytest -c tests/pytest.ini tests/services/test_agent_service.py::test_format_doc_exposes_model_config_public_name -q"
```

Expected: FAIL because `_format_doc` currently returns `model_config_agent`.

- [ ] **Step 3: Update backend formatting and input normalization**

In `app/services/agent_service.py`, make `_format_doc()` return public `model_config`:

```python
"model_config": doc.get("model_config_agent") or doc.get("model_config"),
```

Remove `"model_config_agent"` from formatted output. Add a helper:

```python
def _normalize_model_config_field(self, data: Dict[str, Any]) -> Dict[str, Any]:
    normalized = dict(data)
    if "model_config" in normalized and "model_config_agent" not in normalized:
        normalized["model_config_agent"] = normalized.pop("model_config")
    return normalized
```

Call it at the start of `create_agent()` and `update_agent()`.

- [ ] **Step 4: Update router schema serialization**

In `app/models/agents.py`, keep the internal field but configure alias output:

```python
model_config_agent: Optional[AgentModelConfig] = Field(default=None, alias="model_config")
```

When router calls `payload.model_dump(...)`, keep `by_alias=False` so service receives `model_config_agent`. Public responses come from service `_format_doc()` as `model_config`.

- [ ] **Step 5: Update frontend API types**

In `frontend/src/api/agents.ts`, rename public fields:

```ts
model_config?: AgentModelConfig | null
```

Use `model_config` in `Agent`, `AgentCreateDto`, and `AgentUpdateDto`. Remove `model_config_agent` from TypeScript public interfaces.

- [ ] **Step 6: Run contract tests**

Run:

```bash
MSYS_NO_PATHCONV=1 docker exec tradingagents-backend bash -lc "cd /app && python -m pytest -c tests/pytest.ini tests/services/test_agent_service.py tests/routers/test_agents_router.py -q"
```

Expected: PASS.

---

### Task 2: Validate Agent model provider configuration

**Files:**
- Modify: `app/services/agent_service.py`
- Test: `tests/services/test_agent_service.py`

- [ ] **Step 1: Add failing tests for invalid provider and partial model config**

Add tests that monkeypatch provider lookup:

```python
def test_create_agent_rejects_unknown_model_provider(monkeypatch):
    prompt_id = ObjectId()
    db = _FakeAgentDb(prompts=[{"_id": prompt_id, "enabled": True, "is_active": True, "agent_count": 0}])
    service = _service_with_db(db)

    async def fake_provider_names():
        return {"deepseek"}

    monkeypatch.setattr(service, "_get_configured_provider_names", fake_provider_names)

    with pytest.raises(ValueError, match="模型厂商未配置"):
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
```

- [ ] **Step 2: Run failing tests**

Run:

```bash
MSYS_NO_PATHCONV=1 docker exec tradingagents-backend bash -lc "cd /app && python -m pytest -c tests/pytest.ini tests/services/test_agent_service.py::test_create_agent_rejects_unknown_model_provider tests/services/test_agent_service.py::test_create_agent_allows_partial_model_config_as_default -q"
```

Expected: first test FAIL because validation is missing.

- [ ] **Step 3: Implement provider validation**

In `app/services/agent_service.py`, add:

```python
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
```

Call before insert/update when `model_config_agent` is present.

- [ ] **Step 4: Run service tests**

Run:

```bash
MSYS_NO_PATHCONV=1 docker exec tradingagents-backend bash -lc "cd /app && python -m pytest -c tests/pytest.ini tests/services/test_agent_service.py -q"
```

Expected: PASS.

---

### Task 3: Add `get_agent_by_name()` service method

**Files:**
- Modify: `app/services/agent_service.py`
- Test: `tests/services/test_agent_service.py`

- [ ] **Step 1: Add failing test**

```python
def test_get_agent_by_name_returns_formatted_agent():
    prompt_id = ObjectId()
    agent_id = ObjectId()
    db = _FakeAgentDb(agents=[{
        "_id": agent_id,
        "code": "smart_assistant",
        "name": "智能助手",
        "prompt_id": prompt_id,
        "enabled": True,
        "is_chat": True,
        "tags": ["聊天"],
    }])
    service = _service_with_db(db)

    agent = asyncio.run(service.get_agent_by_name("智能助手"))

    assert agent["id"] == str(agent_id)
    assert agent["code"] == "smart_assistant"
```

- [ ] **Step 2: Run failing test**

Run:

```bash
MSYS_NO_PATHCONV=1 docker exec tradingagents-backend bash -lc "cd /app && python -m pytest -c tests/pytest.ini tests/services/test_agent_service.py::test_get_agent_by_name_returns_formatted_agent -q"
```

Expected: FAIL with missing method.

- [ ] **Step 3: Implement method**

```python
async def get_agent_by_name(self, name: str) -> Optional[Dict[str, Any]]:
    db = await self._get_db()
    await self.ensure_indexes()
    doc = await db.agents.find_one({"name": name})
    return self._format_doc(doc)
```

- [ ] **Step 4: Run service tests**

Run:

```bash
MSYS_NO_PATHCONV=1 docker exec tradingagents-backend bash -lc "cd /app && python -m pytest -c tests/pytest.ini tests/services/test_agent_service.py -q"
```

Expected: PASS.

---

### Task 4: Enforce Agent runtime parameters in test-run and streaming Chat

**Files:**
- Modify: `app/routers/agents.py`
- Modify: `app/chat/service.py`
- Test: `tests/routers/test_agents_router.py`
- Test: `tests/chat/test_chat_agent_integration.py`

- [ ] **Step 1: Add router test for recursion config**

Monkeypatch `create_react_agent` and assert `astream(..., config={"recursion_limit": max_tool_calls})` is used when tools exist.

```python
def test_test_run_passes_recursion_limit_for_tool_agents(client, monkeypatch, fake_service):
    captured = {}

    class _Spec:
        agent_code = "market_analyst"
        system_prompt = "你是市场分析师。"
        tools = [object()]
        class _Params:
            timeout = 300
            max_tool_calls = 3
            retry_on_failure = False
        parameters = _Params()
        llm = object()

    async def fake_build_agent(agent_id, variables=None):
        return _Spec()

    class _FakeAgent:
        async def astream(self, payload, stream_mode=None, config=None):
            captured["config"] = config
            return
            yield

    monkeypatch.setattr(fake_service, "build_agent", fake_build_agent, raising=False)
    monkeypatch.setattr("langgraph.prebuilt.create_react_agent", lambda llm, tools: _FakeAgent())

    response = client.post("/api/agents/agent-1/test-run", json={"message": "hello"})

    assert response.status_code == 200
    assert captured["config"] == {"recursion_limit": 3}
```

- [ ] **Step 2: Add chat integration assertion for recursion config**

In `tests/chat/test_chat_agent_integration.py`, add a tool-agent variant and monkeypatch `langgraph.prebuilt.create_react_agent` similarly.

- [ ] **Step 3: Run failing tests**

Run:

```bash
MSYS_NO_PATHCONV=1 docker exec tradingagents-backend bash -lc "cd /app && python -m pytest -c tests/pytest.ini tests/routers/test_agents_router.py tests/chat/test_chat_agent_integration.py -q"
```

Expected: FAIL because config is not passed.

- [ ] **Step 4: Implement recursion limit and timeout**

In `app/routers/agents.py`, import `asyncio`. For tool agents:

```python
async for chunk in agent.astream(
    {"messages": messages},
    stream_mode="messages",
    config={"recursion_limit": spec.parameters.max_tool_calls},
):
    ...
```

Wrap the whole generator execution path with timeout by moving execution into an inner async generator and consuming with `asyncio.timeout(spec.parameters.timeout)`:

```python
async with asyncio.timeout(spec.parameters.timeout):
    async for event in _stream_agent_events(spec, messages):
        yield event
```

In `app/chat/service.py`, pass the same config when `agent_spec` exists and tools are used:

```python
stream_config = {"recursion_limit": agent_spec.parameters.max_tool_calls} if agent_spec else None
async for chunk in agent.astream({"messages": langchain_messages}, stream_mode="messages", config=stream_config):
    ...
```

For direct `llm.astream`, wrap Agent path with `asyncio.timeout(agent_spec.parameters.timeout)`.

- [ ] **Step 5: Run runtime tests**

Run:

```bash
MSYS_NO_PATHCONV=1 docker exec tradingagents-backend bash -lc "cd /app && python -m pytest -c tests/pytest.ini tests/routers/test_agents_router.py tests/chat/test_chat_agent_integration.py -q"
```

Expected: PASS.

---

### Task 5: Implement retry-on-failure wrapper for Agent tools

**Files:**
- Modify: `app/services/agent_tool_adapter.py`
- Modify: `app/services/agent_service.py`
- Test: `tests/services/test_agent_tool_adapter.py`
- Test: `tests/services/test_agent_service.py`

- [ ] **Step 1: Add failing adapter test**

```python
@pytest.mark.asyncio
async def test_wrapped_tool_retries_once_when_enabled():
    calls = {"count": 0}

    async def flaky_tool(symbol: str):
        calls["count"] += 1
        if calls["count"] == 1:
            raise RuntimeError("temporary")
        return "ok"

    tool = wrap_as_base_tool(
        flaky_tool,
        {
            "code": "flaky_tool",
            "name": "Flaky Tool",
            "description": "test",
            "parameters": [{"name": "symbol", "type": "string", "required": True}],
        },
        retry_on_failure=True,
    )

    result = await tool.ainvoke({"symbol": "000001"})

    assert result == "ok"
    assert calls["count"] == 2
```

- [ ] **Step 2: Run failing test**

Run:

```bash
MSYS_NO_PATHCONV=1 docker exec tradingagents-backend bash -lc "cd /app && python -m pytest -c tests/pytest.ini tests/services/test_agent_tool_adapter.py::test_wrapped_tool_retries_once_when_enabled -q"
```

Expected: FAIL because `wrap_as_base_tool` has no retry parameter.

- [ ] **Step 3: Implement optional retry**

Change signature:

```python
def wrap_as_base_tool(handler: Callable, tool_meta: Dict[str, Any], retry_on_failure: bool = False) -> StructuredTool:
```

Update coroutine and sync func:

```python
async def coroutine(**kwargs):
    try:
        result = handler(**kwargs)
        if inspect.isawaitable(result):
            return await result
        return result
    except Exception:
        if not retry_on_failure:
            raise
        result = handler(**kwargs)
        if inspect.isawaitable(result):
            return await result
        return result
```

For sync `func`, do the same without awaiting.

- [ ] **Step 4: Pass Agent parameter into tool resolution**

In `app/services/agent_service.py`, change `_resolve_agent_tools(bind_tools)` to accept `retry_on_failure: bool`, and call:

```python
tools = await self._resolve_agent_tools(
    prompt.get("bind_tools", []),
    retry_on_failure=AgentParameters(**doc.get("parameters", {})).retry_on_failure,
)
```

- [ ] **Step 5: Run adapter and service tests**

Run:

```bash
MSYS_NO_PATHCONV=1 docker exec tradingagents-backend bash -lc "cd /app && python -m pytest -c tests/pytest.ini tests/services/test_agent_tool_adapter.py tests/services/test_agent_service.py -q"
```

Expected: PASS.

---

### Task 6: Complete Chat frontend Agent selection path

**Files:**
- Locate and modify: `frontend/src/views/Chat/index.vue`
- Locate and modify: chat API module under `frontend/src/api/`
- Modify: `frontend/src/api/agents.ts` if shared Agent type is needed

- [ ] **Step 1: Locate conversation creation code**

Search:

```bash
grep -R "createConversation\|ConversationCreate\|conversation" frontend/src/views/Chat frontend/src/api
```

Use the dedicated Grep tool if working inside Claude Code.

- [ ] **Step 2: Add Agent list loading to Chat page**

Import:

```ts
import { agentsApi } from '@/api/agents'
import type { Agent } from '@/api/agents'
```

Add state:

```ts
const chatAgents = ref<Agent[]>([])
const selectedAgentId = ref<string>('')
```

Load enabled chat agents:

```ts
async function loadChatAgents() {
  const res = await agentsApi.list({ enabled: true, is_chat: true, page: 1, page_size: 100 })
  if (res.success) chatAgents.value = res.data.items
}
```

Call it in `onMounted` alongside existing Chat initialization.

- [ ] **Step 3: Add selector near new chat controls**

Add an Element Plus select:

```vue
<el-select v-model="selectedAgentId" clearable placeholder="选择 Agent" class="agent-select">
  <el-option v-for="agent in chatAgents" :key="agent.id" :label="agent.name" :value="agent.id" />
</el-select>
```

- [ ] **Step 4: Pass `agent_id` when creating a conversation**

When calling conversation creation API, include:

```ts
agent_id: selectedAgentId.value || undefined
```

- [ ] **Step 5: Verify manually in browser**

Start frontend dev server and create a new conversation with an Agent selected. Expected: backend conversation metadata contains `agent_id`, and streaming response uses Agent prompt/tools.

---

### Task 7: Wire non-streaming Chat through Agent when present

**Files:**
- Modify: `app/chat/service.py`
- Test: `tests/chat/test_chat_agent_integration.py`

- [ ] **Step 1: Add failing non-streaming test**

```python
@pytest.mark.asyncio
async def test_send_message_uses_agent_prompt_when_conversation_has_agent(monkeypatch):
    service = _ChatServiceForTest()
    conv = Conversation(user_id="user-1", title="Agent Chat", metadata={"agent_id": "agent-1"})
    await service.conversations_col.insert_one(conv.model_dump())

    class _Llm:
        async def ainvoke(self, messages):
            assert messages[0].content == "agent-system"
            class _Response:
                content = "agent-response"
                response_metadata = {}
            return _Response()

    class _Spec:
        system_prompt = "agent-system"
        tools = []
        llm = _Llm()

    class _FakeAgentService:
        async def build_agent(self, agent_id, variables=None):
            return _Spec()
        async def record_usage(self, agent_id):
            return None

    import app.services.agent_service as agent_module
    monkeypatch.setattr(agent_module, "agent_service", _FakeAgentService())

    response = await service.send_message("user-1", ChatRequest(conversation_id=conv.id, message="hello", stream=False))

    assert response.content == "agent-response"
```

- [ ] **Step 2: Run failing test**

Run:

```bash
MSYS_NO_PATHCONV=1 docker exec tradingagents-backend bash -lc "cd /app && python -m pytest -c tests/pytest.ini tests/chat/test_chat_agent_integration.py::test_send_message_uses_agent_prompt_when_conversation_has_agent -q"
```

Expected: FAIL because `send_message()` ignores Agent.

- [ ] **Step 3: Implement Agent path in `send_message()`**

In `send_message()`, after saving user message, load conversation and optional Agent:

```python
conv = await self.get_conversation(user_id, data.conversation_id)
agent_id = (conv.metadata or {}).get("agent_id") if conv else None
agent_spec = None
if agent_id:
    from app.services.agent_service import agent_service
    agent_spec = await agent_service.build_agent(agent_id)
```

Use `agent_spec.system_prompt` and `agent_spec.llm` when present. If tools are present, invoke `create_react_agent` with recursion config and timeout; otherwise direct `llm.ainvoke()`.

- [ ] **Step 4: Run chat integration tests**

Run:

```bash
MSYS_NO_PATHCONV=1 docker exec tradingagents-backend bash -lc "cd /app && python -m pytest -c tests/pytest.ini tests/chat/test_chat_agent_integration.py -q"
```

Expected: PASS.

---

### Task 8: Improve Agent test-run frontend SSE UI

**Files:**
- Modify: `frontend/src/views/AgentManagement/index.vue`
- Modify: `frontend/src/api/agents.ts` if adding helper types

- [ ] **Step 1: Add typed test-run state**

Replace raw `testOutput` only state with:

```ts
interface TestRunEntry {
  type: 'token' | 'tool_call' | 'tool_result' | 'done' | 'error'
  content: string
}

const testEntries = ref<TestRunEntry[]>([])
const testOutput = computed(() => testEntries.value.map(entry => entry.content).join(''))
const testToolCallCount = computed(() => testEntries.value.filter(entry => entry.type === 'tool_call').length)
```

- [ ] **Step 2: Parse SSE chunks**

Add parser state:

```ts
let sseBuffer = ''

function handleSseChunk(chunk: string) {
  sseBuffer += chunk
  const parts = sseBuffer.split('\n\n')
  sseBuffer = parts.pop() || ''
  for (const part of parts) {
    const eventLine = part.split('\n').find(line => line.startsWith('event:'))
    const dataLine = part.split('\n').find(line => line.startsWith('data:'))
    if (!eventLine || !dataLine) continue
    const event = eventLine.replace('event:', '').trim() as TestRunEntry['type']
    const data = JSON.parse(dataLine.replace('data:', '').trim())
    appendTestEvent(event, data)
  }
}
```

Add event renderer:

```ts
function appendTestEvent(event: TestRunEntry['type'], data: any) {
  if (event === 'token') testEntries.value.push({ type: event, content: data.content || data.token || '' })
  if (event === 'tool_call') testEntries.value.push({ type: event, content: `\n\n调用工具：${data.name} ${JSON.stringify(data.args || {})}\n` })
  if (event === 'tool_result') testEntries.value.push({ type: event, content: `工具返回：${data.content || data.result || ''}\n` })
  if (event === 'error') testEntries.value.push({ type: event, content: `\n错误：${data.message || data.error || '未知错误'}\n` })
  if (event === 'done') testEntries.value.push({ type: event, content: '\n\n执行完成\n' })
}
```

- [ ] **Step 3: Update dialog template**

Render entries with classes:

```vue
<div class="test-output">
  <div v-if="testEntries.length === 0" class="text-muted">等待输出…</div>
  <div v-for="(entry, index) in testEntries" :key="index" :class="`test-entry test-entry-${entry.type}`">
    {{ entry.content }}
  </div>
</div>
<div class="text-muted mt-8">工具调用：{{ testToolCallCount }} 次</div>
```

- [ ] **Step 4: Add stop support**

Add:

```ts
let testAbortController: AbortController | null = null
```

Before fetch:

```ts
testAbortController = new AbortController()
```

Pass `signal: testAbortController.signal`. Add stop button:

```vue
<el-button @click="stopTestRun" :disabled="!testLoading">停止</el-button>
```

Function:

```ts
function stopTestRun() {
  testAbortController?.abort()
  testLoading.value = false
}
```

- [ ] **Step 5: Verify manually**

Open Agent 管理 → 测试运行. Expected: token streams as text; tool calls/results are rendered as separate lines; stop button aborts the request.

---

### Task 9: Complete Agent create/edit forms and prompt overview

**Files:**
- Modify: `frontend/src/views/AgentManagement/index.vue`
- Modify: `frontend/src/api/agents.ts`

- [ ] **Step 1: Update all field references to `model_config`**

Replace in AgentManagement page:

```ts
selectedAgent.model_config_agent
editForm.model_config_agent
```

with public naming:

```ts
selectedAgent.model_config
editForm.model_config
```

Keep local form object named `model_config`.

- [ ] **Step 2: Add create model config controls**

Add state:

```ts
const createUseDefaultModel = ref(true)
```

Extend create form:

```ts
model_config: { provider: '', model: '', temperature: 0.7, max_tokens: 4096 },
parameters: { max_tool_calls: 10, timeout: 300, retry_on_failure: false },
```

Add dialog fields mirroring edit model controls. Submit:

```ts
const payload = {
  ...createForm,
  model_config: createUseDefaultModel.value ? null : createForm.model_config,
}
```

- [ ] **Step 3: Add prompt view link**

Near prompt select/display, add a button:

```vue
<el-button size="small" text type="primary" :disabled="!selectedPrompt" @click="openPromptDetail">查看</el-button>
```

Function:

```ts
function openPromptDetail() {
  if (!selectedPrompt.value) return
  window.open(`/prompts?prompt_id=${selectedPrompt.value.id}`, '_blank')
}
```

- [ ] **Step 4: Add variables overview**

Compute variables from prompt blocks and tool parameters:

```ts
const promptTextVariables = computed(() => {
  const blocks = selectedPrompt.value?.blocks ?? []
  const names = new Set<string>()
  for (const block of blocks) {
    const content = block.content || ''
    for (const match of content.matchAll(/{{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*}}/g)) {
      names.add(match[1])
    }
  }
  return [...names].sort()
})

const toolInputVariables = computed(() => {
  const names = new Set<string>()
  for (const code of selectedPrompt.value?.bind_tools ?? []) {
    for (const param of toolMetaMap.value[code]?.parameters ?? []) {
      names.add(param.name)
    }
  }
  return [...names].sort()
})
```

Render a collapse item for variables.

- [ ] **Step 5: Verify form behavior manually**

Create an Agent with default model, then create/edit one with custom provider/model. Expected: payload uses `model_config`, saved detail reloads with same values.

---

### Task 10: Add lightweight frontend Agent list pagination/loading-more

**Files:**
- Modify: `frontend/src/views/AgentManagement/index.vue`

- [ ] **Step 1: Add paging state**

```ts
const page = ref(1)
const pageSize = ref(20)
const hasMoreAgents = computed(() => agents.value.length < total.value)
```

- [ ] **Step 2: Update `loadAgents` to support reset/append**

```ts
async function loadAgents(reset = true) {
  if (reset) page.value = 1
  listLoading.value = true
  try {
    const res = await agentsApi.list({
      search: searchText.value || undefined,
      tag: filterTag.value || undefined,
      enabled: filterEnabled.value === '' ? undefined : Boolean(filterEnabled.value),
      is_chat: filterIsChat.value === '' ? undefined : Boolean(filterIsChat.value),
      page: page.value,
      page_size: pageSize.value
    })
    if (res.success) {
      agents.value = reset ? res.data.items : [...agents.value, ...res.data.items]
      total.value = res.data.total
      if (!selectedAgent.value && agents.value.length > 0) await selectAgent(agents.value[0])
    }
  } finally {
    listLoading.value = false
  }
}
```

- [ ] **Step 3: Add load-more button**

```vue
<el-button v-if="hasMoreAgents" text :loading="listLoading" @click="loadMoreAgents">加载更多</el-button>
<div v-else class="text-muted">已加载全部 {{ total }} 个</div>
```

Function:

```ts
async function loadMoreAgents() {
  page.value += 1
  await loadAgents(false)
}
```

- [ ] **Step 4: Update filter/search calls**

Change filter callbacks to `loadAgents(true)` and search debounce to `loadAgents(true)`.

- [ ] **Step 5: Verify manually**

Seed or create more than 20 agents. Expected: first page shows 20; load more appends results.

---

### Task 11: Full verification and UI smoke test

**Files:**
- No new implementation files unless failures require fixes.

- [ ] **Step 1: Run backend Agent test suite**

Run:

```bash
MSYS_NO_PATHCONV=1 docker exec tradingagents-backend bash -lc "cd /app && python -m pytest -c tests/pytest.ini tests/services/test_agent_service.py tests/services/test_agent_tool_adapter.py tests/routers/test_agents_router.py tests/chat/test_chat_agent_integration.py tests/services/test_tool_service_search.py -q"
```

Expected: PASS.

- [ ] **Step 2: Run lint/type checks available in repo**

Run backend lint:

```bash
MSYS_NO_PATHCONV=1 docker exec tradingagents-backend bash -lc "cd /app && ruff check app tests"
```

Expected: PASS or only pre-existing unrelated findings documented.

Run frontend checks using the package scripts in `frontend/package.json`.

- [ ] **Step 3: Start frontend and backend if not already running**

Use existing project commands. Do not kill unrelated processes. If an existing dev server is running, reuse it.

- [ ] **Step 4: Browser smoke test**

Verify:

1. Agent 管理 opens from sidebar.
2. Seed button returns created/skipped summary.
3. Create Agent with default model.
4. Edit Agent with custom model and save.
5. Prompt overview shows tools, variables, and workflow output.
6. Test-run streams token output and displays tool events when a tool-bound prompt is used.
7. Chat page allows selecting an Agent when starting a new conversation.
8. Chat response uses selected Agent behavior.
9. Disable/enable toggle persists.
10. Delete is blocked for system Agent and allowed for non-system Agent.

- [ ] **Step 5: Run GitNexus change detection before commit**

Project instruction requires `gitnexus_detect_changes()` before committing. If the GitNexus MCP tool is unavailable in the current tool list, report that explicitly and do not claim GitNexus verification was performed.

- [ ] **Step 6: Final review**

Check `git diff` and confirm changes are limited to Agent management, Chat Agent integration, and related tests.

---

## Self-Review

- Spec coverage: The plan covers runtime parameters, Chat integration, test-run SSE, model config, prompt overview, provider validation, service methods, frontend pagination, and verification.
- Placeholder scan: No TBD/TODO placeholders are present; each task has concrete files, commands, and expected outcomes.
- Type consistency: Public frontend/backend API uses `model_config`; internal Pydantic/service may keep `model_config_agent` only as implementation detail.
