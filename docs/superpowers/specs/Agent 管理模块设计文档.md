## 1. 提示词管理模块边界（前置结论）

提示词管理模块本阶段**不新增出参定义字段**，也不恢复 `variables` 入库。

原因：当前工作流的数据传递模型是 LangGraph 共享 state，节点之间传递的是完整 LLM 输出文本，并由工作流节点/Agent 的稳定标识决定写入哪个 state key。即使未来通过 prompt、模型 response format 或后处理让 LLM 输出 JSON，工作流也仍需额外的数据映射、字段路径引用、版本兼容和缺失字段处理能力；这些属于工作流编排/后处理层，不应放在提示词管理层。

### 1.1 Prompt 职责

Prompt 继续只负责定义 Agent 如何生成内容：

| 字段 | 说明 |
|------|------|
| `blocks` | 提示词文本块和对话历史占位符 |
| `bind_tools` | 该提示词允许 Agent 使用的工具集合 |
| `prompt_type` | `chat` / `workflow`，用于运行时上下文注入差异 |
| `tags` / `enabled` / `version` | 管理、筛选、启停和版本控制 |

明确不做：

- 不在 Prompt 中新增 `output_schema`
- 不在 Prompt 中新增 `output_key`
- 不把变量定义 `variables` 入库
- 不让 Prompt 决定工作流 state 字段名

变量仍按现有提示词管理设计动态推导：

- 工具入参：来自绑定工具的 `parameters`
- 工具出参：来自绑定工具的 `output_schema`
- 手写变量：从 text block 中的 `{{variable}}` 正则提取

### 1.2 Agent 输出槽

Agent 是工作流节点的执行单元，因此 Agent 的输出槽由 Agent 自身决定。

默认规则：

```text
workflow_state[agent.code] = agent_result.content
```

示例：

```json
{
  "market_analyst": "完整市场分析报告文本...",
  "news_analyst": "完整新闻分析报告文本...",
  "risk_manager": "完整风险决策文本..."
}
```

工作流下游节点引用上游结果时，引用的是上游 Agent 的 `code` 对应的完整文本输出。

### 1.3 与当前工作流的对应关系

当前内置工作流使用硬编码 state 字段：

| 当前字段 | 含义 | 未来动态 Agent 对应 |
|----------|------|-------------------|
| `market_report` | 市场分析师完整文本报告 | `market_analyst` |
| `news_report` | 新闻分析师完整文本报告 | `news_analyst` |
| `fundamentals_report` | 基本面分析师完整文本报告 | `fundamentals_analyst` |
| `sentiment_report` | 情绪分析师完整文本报告 | `social_media_analyst` |
| `investment_plan` | 研究经理完整文本结论 | `research_manager` |
| `trader_investment_plan` | 交易员完整文本计划 | `trader` |
| `final_trade_decision` | 风险经理完整文本决策 | `risk_manager` |

后续工作流管理模块可以在图编排层维护节点输出映射，例如：

```json
{
  "node_id": "node_market_1",
  "agent_code": "market_analyst",
  "output_key": "market_analyst"
}
```

但这属于工作流节点配置，不属于 Prompt 配置。

### 1.4 结构化输出的后续位置

如果未来需要从完整 LLM 输出中提取固定字段，应作为独立能力实现：

- 工作流数据映射节点
- 后处理解析节点
- Agent 测试运行中的结构化提取预览
- 最终决策类专用解析器

这些能力可以读取 Agent 完整输出，再产生新的结构化 state 字段；不改变 Prompt 管理模块的职责。

# Agent 管理模块设计文档

---

## 2. 定位

Agent 是 AI 执行单元，是工具管理和提示词管理的消费者、工作流管理的基础构件。

```
工具管理 ──┐
           ├──→ Agent 管理 ──→ 工作流管理
提示词管理 ──┘
```

Agent 将**提示词**（内容 + 绑定工具）+ **模型配置** + **运行参数**组装为一个可运行的执行规格（AgentSpec），供 Chat、工作流、测试运行统一消费。

```
提示词管理 ──→ 定义: 内容 + 绑定工具 + 运行时变量占位符
                   │
                   ▼
              Agent 管理 ──→ 组装: 提示词 + 工具 + 模型配置 + 运行参数
                   │
                   ▼
              工作流管理 ──→ 执行 Agent → 以 agent.code 写入完整文本输出 → 下游节点引用
```

---

## 3. 数据模型

### MongoDB 集合: `agents`

```json
{
  "_id": ObjectId,
  "code": "market_analyst",
  "name": "市场分析师",
  "description": "分析市场整体走势、板块轮动、资金流向",

  "prompt_id": ObjectId,

  "model_config": {
    "provider": "deepseek",
    "model": "deepseek-chat",
    "temperature": 0.3,
    "max_tokens": 4096
  },

  "parameters": {
    "max_tool_calls": 10,
    "timeout": 300,
    "retry_on_failure": false
  },

  "tags": ["分析", "盯盘"],
  "is_chat": false,
  "is_system": true,
  "enabled": true,

  "usage_count": 0,
  "last_used_at": null,

  "created_at": datetime,
  "updated_at": datetime
}
```

### 字段说明

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `code` | string | 是 | 唯一编码，`^[a-z][a-z0-9_]*$`，最大 60 字符 |
| `name` | string | 是 | 显示名称，唯一，最大 100 字符 |
| `description` | string | 否 | Agent 描述 |
| `prompt_id` | ObjectId | 是 | 绑定的提示词 ID，必须存在且启用 |
| `model_config` | object | 否 | 模型配置，不填走系统默认模型 |
| `parameters` | object | 否 | 运行参数，有默认值 |
| `tags` | [string] | 否 | 标签，用于筛选 |
| `is_chat` | bool | 否 | 是否为聊天助手类 Agent，默认 false |
| `is_system` | bool | 否 | 系统内置 Agent 不可删除，默认 false |
| `enabled` | bool | 否 | 启用状态，默认 true |
| `usage_count` | int | 否 | 被调用次数统计 |
| `last_used_at` | datetime | 否 | 最后调用时间 |

### 嵌套模型

#### ModelConfig — 模型配置（全部可选）

```json
{
  "provider": "deepseek",
  "model": "deepseek-chat",
  "temperature": 0.3,
  "max_tokens": 4096
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `provider` | string? | 模型厂家，如 `deepseek` `openai` `qwen`。不填走系统默认 |
| `model` | string? | 模型名称，如 `deepseek-chat` `gpt-4o`。不填走系统默认 |
| `temperature` | float? | 温度，默认 0.7 |
| `max_tokens` | int? | 最大输出 token，默认 4096 |

`provider` 和 `model` 同时填写时生效；都不填或只填一个时，走 `llm_factory.get_chat_llm_config()` 的默认链路（`CHAT_DEFAULT_MODEL` → `system_configs` → fallback）。

#### Parameters — 运行参数

```json
{
  "max_tool_calls": 10,
  "timeout": 300,
  "retry_on_failure": false
}
```

| 字段 | 类型 | 默认 | 说明 |
|------|------|------|------|
| `max_tool_calls` | int | 10 | 单次执行最大工具调用次数，映射为 LangGraph `recursion_limit` |
| `timeout` | int | 300 | 整体执行超时（秒） |
| `retry_on_failure` | bool | false | 工具调用失败是否自动重试一次 |

> Agent 的工作流输出默认使用 `code` 作为输出槽名称。
> Agent 执行结果是完整 LLM 文本，工作流运行时写入 `workflow_state[agent.code]`。
> 固定字段提取属于后续工作流数据映射/后处理能力，不放在提示词管理或 Agent 基础模型中。

---

## 4. Pydantic Schema

文件: `app/models/agents.py`

```
AgentModelConfig        — 模型配置，全部 optional
AgentParameters         — 运行参数，有默认值
AgentCreate             — 创建请求
AgentUpdate             — 更新请求，全部 optional
```

### AgentCreate

```python
class AgentCreate(BaseModel):
    code: str              # ^[a-z][a-z0-9_]*$, max 60
    name: str              # max 100
    description: str = ""
    prompt_id: str         # 必填，会校验存在性
    model_config_agent: Optional[AgentModelConfig] = None
    parameters: AgentParameters = AgentParameters()
    tags: List[str] = []
    is_chat: bool = False
    enabled: bool = True
```

### AgentUpdate

```python
class AgentUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    prompt_id: Optional[str] = None
    model_config_agent: Optional[AgentModelConfig] = None
    parameters: Optional[AgentParameters] = None
    tags: Optional[List[str]] = None
    is_chat: Optional[bool] = None
    enabled: Optional[bool] = None
```

> 注：`code` 不可修改，`is_system` 不可通过 API 修改。

---

## 5. 服务层

文件: `app/services/agent_service.py`

### 4.1 基础 CRUD

与 `tool_service.py` / `prompt_service.py` 保持一致的单例模式。

| 方法 | 说明 |
|------|------|
| `ensure_indexes()` | code unique, name unique, tags 索引, is_chat 索引 |
| `list_agents(...)` | 分页 + 搜索 + 按标签/状态/is_chat 筛选 |
| `get_agent(agent_id)` | 按 ID 查详情 |
| `get_agent_by_code(code)` | 按 code 查 |
| `get_agent_by_name(name)` | 按 name 查 |
| `create_agent(data)` | 创建，**校验 prompt_id 存在性** |
| `update_agent(agent_id, data)` | 更新，**维护 prompt 关联计数** |
| `delete_agent(agent_id)` | 删除，系统 Agent 不可删，**清除 prompt 关联计数** |
| `toggle_agent(agent_id, enabled)` | 启用/禁用 |
| `get_all_tags()` | 标签列表 |

### 4.2 关联计数维护

Agent 引用 Prompt。创建/更新/删除 Agent 时，维护 prompts 的 `agent_count` 反向计数。

> 注意：工具绑定由提示词的 `bind_tools` 决定，Agent 不再直接引用 tool_ids，因此无需维护 tools 的关联计数。

#### 创建 Agent

```
1. 校验 prompt_id → prompt 存在且启用
2. 插入 agent 文档
3. db.prompts.update_one({"_id": prompt_id}, {$inc: {"agent_count": 1}})
```

#### 更新 Agent

```
1. 读取旧 agent_doc
2. 如果 prompt_id 变更:
   - db.prompts.update_one({"_id": old_prompt_id}, {$inc: {"agent_count": -1}})
   - db.prompts.update_one({"_id": new_prompt_id}, {$inc: {"agent_count": 1}})
3. 更新 agent 文档
```

#### 删除 Agent

```
1. 读取 agent_doc
2. 校验 is_system → 不可删
3. db.prompts.update_one({"_id": prompt_id}, {$inc: {"agent_count": -1}})
4. 删除 agent 文档
```

### 4.3 运行时构建

核心方法：将 Agent 配置转为可执行对象。

#### build_agent()

```python
async def build_agent(
    self,
    agent_id: str,
    variables: Optional[Dict[str, str]] = None,
) -> AgentSpec:
```

流程：

```
1. 加载 agent_doc
   └─ 校验: enabled?

2. 解析 prompt_id → 提示词 + 工具
   ├─ prompt_service.render_prompt(prompt_id, variables)
   │  └─ 返回 system_prompt + messages_placeholder key
   └─ 从 prompt.bind_tools 解析工具列表
      ├─ builtin  → HANDLER_MAP[handler] → wrap_as_base_tool(callable, meta)
      ├─ rpc      → RPCToolWrapper (预留)
      └─ remote   → HTTPToolWrapper (预留)

3. 解析 model_config → LLM
   ├─ 指定了 provider+model → create_chat_llm(provider, model, ...)
   └─ 未指定 → create_chat_llm() 走默认链路

4. 组装 AgentSpec
```

#### AgentSpec

```python
class AgentSpec:
    """Agent 的运行时规格 — 不可变，可传递给 Chat / 工作流"""
    agent_id: str
    agent_code: str                # 工作流默认输出槽名称
    agent_name: str
    system_prompt: str
    messages_placeholder: Optional[str]
    tools: List[BaseTool]          # 从 prompt.bind_tools 解析
    llm: BaseChatModel
    parameters: AgentParameters
```

#### wrap_as_base_tool()

将 `handler_map` 中的 `Callable` + 工具元数据（参数定义、描述）包装为 LangChain `BaseTool`：

```python
def wrap_as_base_tool(
    handler: Callable,
    tool_meta: Dict,
) -> BaseTool:
    """
    将 (Callable, 参数定义) → LangChain BaseTool

    - 从 tool_meta.parameters 构造 args_schema (Pydantic Model)
    - 从 tool_meta.description 设置描述
    - handler 作为 _run / _arun 的实现
    """
```

### 4.4 使用统计

```python
async def record_usage(self, agent_id: str) -> None:
    """记录一次调用"""
    await db.agents.update_one(
        {"_id": ObjectId(agent_id)},
        {"$inc": {"usage_count": 1}, "$set": {"last_used_at": datetime.utcnow()}}
    )
```

### 4.5 模型选项查询

为前端 Agent 编辑面板的"模型选择器"提供数据，直接复用现有方法：

```python
async def get_available_models(self) -> List[Dict]:
    """
    返回已配置的模型列表，按 provider 分组。
    直接调用 config_service.get_available_models()。
    """
```

---

## 6. API 层

文件: `app/routers/agents.py`

前缀: `/agents`，标签: `Agent 管理`

### 端点列表

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/` | 列表（分页、搜索、筛选） |
| GET | `/tags` | 标签列表 |
| GET | `/models` | 可用模型列表（给前端选择器用） |
| GET | `/{agent_id}` | Agent 详情 |
| POST | `/` | 创建 Agent |
| PUT | `/{agent_id}` | 更新 Agent |
| DELETE | `/{agent_id}` | 删除 Agent |
| PUT | `/{agent_id}/toggle` | 启用/禁用 |
| POST | `/{agent_id}/test-run` | 测试运行（SSE 流式输出） |
| POST | `/seed` | 种子数据初始化 |

### GET / — 列表

```python
@router.get("/")
async def list_agents(
    search: Optional[str] = None,       # 搜索 name/code/description
    tag: Optional[str] = None,          # 标签筛选
    enabled: Optional[bool] = None,     # 启用状态
    is_chat: Optional[bool] = None,     # 聊天类型
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
):
```

### POST / — 创建

```python
@router.post("/")
async def create_agent(
    payload: AgentCreate,
    current_user: dict = Depends(get_current_user),
):
    # 校验:
    #   1. code / name 唯一性
    #   2. prompt_id 存在且启用
    #   3. provider/model 如果填了，校验 provider 已配置
```

### PUT /{agent_id} — 更新

```python
@router.put("/{agent_id}")
async def update_agent(
    agent_id: str,
    payload: AgentUpdate,
    current_user: dict = Depends(get_current_user),
):
    # 校验同创建
    # 维护关联计数（prompt 的 agent_count）
```

### POST /{agent_id}/test-run — 测试运行

```python
@router.post("/{agent_id}/test-run")
async def test_run_agent(
    agent_id: str,
    payload: dict,  # {"message": "...", "variables": {}}
    current_user: dict = Depends(get_current_user),
):
    """
    测试运行 Agent，SSE 流式输出。

    流程:
    1. build_agent(agent_id, variables)
    2. 用 AgentSpec 构建 create_react_agent(spec.llm, spec.tools)
    3. 注入 system_prompt + test message
    4. 流式返回 token / tool_call / tool_result / done / error
    """
```

复用 `chat/sse.py` 的 SSE 基础设施。

### POST /seed — 种子初始化

```python
@router.post("/seed")
async def seed_agents(current_user: dict = Depends(get_current_user)):
    # 调用 app/agents/seed_agents.py
```

---

## 7. 种子数据

文件: `app/agents/seed_agents.py`

策略：按 `code` 查询，存在则跳过，不存在则插入，标记 `is_system=True`。

### 预设 Agent

| code | name | 提示词 | is_chat | 说明 |
|------|------|--------|---------|------|
| `market_analyst` | 市场分析师 | 市场分析提示词 | false | 分析大盘走势 |
| `news_analyst` | 新闻分析师 | 新闻分析提示词 | false | 新闻舆情分析 |
| `fundamentals_analyst` | 基本面分析师 | 基本面提示词 | false | 财务报表分析 |
| `technical_analyst` | 技术分析师 | 技术分析提示词 | false | 技术面分析 |
| `smart_assistant` | 智能助手 | 聊天助手提示词 | true | Chat 默认 Agent |

> 工具绑定由提示词的 `bind_tools` 字段决定，种子数据无需单独指定 tool_ids。

种子数据中 `prompt_id` 需要在运行时从 DB 按名称解析为 ObjectId，不能硬编码 ID。

```python
async def seed_agents_to_db() -> Dict[str, int]:
    for agent_def in AGENT_SEEDS:
        # 运行时解析 prompt
        prompt = await prompt_service.get_active_prompt(agent_def["prompt_code"])
        # 插入（工具由 prompt.bind_tools 决定，无需额外处理）
        ...
```

---

## 8. 与现有系统的集成

### 7.1 模型配置 — 复用 llm_factory

完全复用现有链路，零新增代码：

```
Agent model_config
    │
    ├─ provider+model 都填了
    │   └─ create_chat_llm(provider, model, temperature, max_tokens)
    │       └─ _resolve_provider_credentials(provider_name)
    │           └─ config_service.get_llm_providers() → 查 DB 拿 api_key + base_url
    │
    └─ 都没填 / 部分填写
        └─ create_chat_llm() 不传 provider/model
            └─ get_chat_llm_config()
                └─ settings.CHAT_DEFAULT_MODEL → system_configs → fallback
```

### 7.2 Chat 系统改造

当前 `chat/service.py` 硬编码了 Agent 构建。需要改造为支持指定 `agent_id`：

**ConversationCreate 增加字段：**

```python
class ConversationCreate(BaseModel):
    title: str = "New Chat"
    model_provider: str = ""
    model_name: str = ""
    system_prompt: str = ""
    agent_id: Optional[str] = None   # 新增：指定 Agent
```

**stream_response 改造：**

```python
async def stream_response(self, user_id, conversation_id, message):
    # 查 conversation 的 agent_id
    conv = await self.get_conversation(user_id, conversation_id)
    
    if conv and conv.metadata.get("agent_id"):
        # 走 Agent 管理
        spec = await agent_service.build_agent(conv.metadata["agent_id"])
        llm = spec.llm
        tools = spec.tools
        system_prompt = spec.system_prompt
    else:
        # 保持原有默认行为
        tools = tool_registry.get_all() if not tool_registry.empty else None
        llm = await create_chat_llm(streaming=True, ...)
        system_prompt = await self._get_system_prompt(conversation_id)
    
    # 后续逻辑不变
    if tools:
        agent = create_react_agent(llm, tools)
        ...
```

向后兼容：未指定 `agent_id` 的会话行为完全不变。

### 7.3 工具 calls_llm 标记

给工具元数据增加标记，用于前端提示：

```json
{
  "code": "get_stock_news_openai",
  "calls_llm": true,
  "estimated_tokens": 2000
}
```

- `calls_llm: true` — 此工具内部会调用 LLM，可能产生额外 token 消耗
- `estimated_tokens` — 预估消耗，仅供前端展示参考

在 Agent 详情面板展示继承的工具列表时，标记为 `calls_llm` 的工具显示提示图标："此工具内部调用大模型，可能产生额外消耗"。

**更新范围**：`handler_map.py` 的 `TOOL_DEFINITIONS` 中，对 `get_stock_news_openai`、`get_global_news_openai`、`get_stock_news_unified` 等工具增加 `calls_llm` 字段。

---

## 9. 运行时安全防护

针对工具内部嵌套调用（工具内调 LLM、工具内调其他工具）的意外问题：

### 8.1 最大工具调用次数

Agent 的 `parameters.max_tool_calls` 映射为 LangGraph 的 `recursion_limit`：

```python
agent = create_react_agent(llm, tools)
# 通过配置控制 agent → tool → agent 的循环次数
```

超出限制时 LangGraph 自动终止，返回错误信息。

### 8.2 执行超时

整个 Agent 执行包裹在 `asyncio.wait_for` 中：

```python
try:
    result = await asyncio.wait_for(
        agent.ainvoke({"messages": messages}),
        timeout=spec.parameters.timeout,
    )
except asyncio.TimeoutError:
    # 返回超时提示，不崩溃
```

### 8.3 工具内部调用 LLM 的知情提示

通过 `calls_llm` 标记，前端在 Agent 详情面板展示继承的工具列表时，让用户知道该工具会产生额外 LLM 调用。不限制执行，只做知情告知。

### 8.4 retry_on_failure

工具调用失败时的行为：

- `false`（默认）：失败直接返回错误信息给 Agent，Agent 自行决定如何处理
- `true`：自动重试一次，两次都失败再返回错误

---

## 10. 文件清单

| 文件 | 类型 | 说明 |
|------|------|------|
| `app/models/agents.py` | 新建 | Pydantic Schema |
| `app/services/agent_service.py` | 新建 | 核心服务（CRUD + 关联维护 + 运行时构建） |
| `app/routers/agents.py` | 新建 | API 路由 |
| `app/agents/__init__.py` | 新建 | 包初始化 |
| `app/agents/seed_agents.py` | 新建 | 种子数据 |
| `app/chat/service.py` | 修改 | 支持 agent_id，向后兼容 |
| `app/chat/schemas.py` | 修改 | ConversationCreate 增加 agent_id |
| `app/tools/handler_map.py` | 修改 | TOOL_DEFINITIONS 增加 calls_llm 字段 |
| `app/main.py` | 修改 | 注册 agents router |
| `frontend/src/views/AgentManagement/index.vue` | 新建 | Agent 管理页面 |
| `frontend/src/api/agents.ts` | 新建 | Agent API 模块 |
| `frontend/src/router/index.ts` | 修改 | 添加 /agents 路由 |
| `frontend/src/components/Layout/SidebarMenu.vue` | 修改 | 管理中心分组添加 Agent 管理菜单 |

---

## 11. 开发顺序

```
Step 1: app/models/agents.py          — Schema 定义
Step 2: app/services/agent_service.py  — CRUD + 关联计数
Step 3: app/routers/agents.py          — API 路由（不含 test-run）
Step 4: app/agents/seed_agents.py      — 种子数据
Step 5: 运行时构建                      — build_agent + wrap_as_base_tool
Step 6: test-run 端点                   — SSE 测试运行
Step 7: Chat 集成                       — chat/service.py 改造
Step 8: handler_map 更新               — calls_llm 标记
```

每一步可独立测试，不依赖后续步骤。

---

## 12. 前端交互与页面设计

### 11.1 整体架构

遵循管理中心统一的**左右分栏布局**（与工具管理、提示词管理一致）：
- 左侧 (el-col :span="6")：筛选 + Agent 列表
- 右侧 (el-col :span="18")：详情查看 / 编辑表单

技术栈：Vue 3 Composition API (`<script setup lang="ts">`) + Element Plus + Tailwind CSS + TypeScript。

### 11.2 页面布局原型

```
┌── Agent 管理 ────────────────────────── [+ 新建] [初始化种子] ───┐
│                                                                    │
│  ┌─ 筛选 ──────────────────────────────────────────────────────┐   │
│  │ [🔍 搜索 Agent 名称/编码...]                                │   │
│  │ [标签 ▾]  [状态 ▾]  [类型 ▾ 普通/聊天助手]                   │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                    │
│  ┌─ 列表 (span=6) ───────┐  ┌─ 详情/编辑 (span=18) ───────────┐  │
│  │                        │  │                                   │  │
│  │  ┌──────────────────┐  │  │  (未选中时显示 el-empty)         │  │
│  │  │ ● 市场分析师      │  │  │  "请从左侧选择一个 Agent"       │  │
│  │  │   DeepSeek   [●]  │  │  │                                   │  │
│  │  │   [分析][盯盘]    │  │  │  ── 选中后展示编辑面板 ──        │  │
│  │  └──────────────────┘  │  │                                   │  │
│  │  ┌──────────────────┐  │  │  ┌─────────────────────────────┐ │  │
│  │  │ ● 新闻分析师      │  │  │  │  基本信息编辑面板            │ │  │
│  │  │   GPT-4o    [●]  │  │  │  │  (见 11.3 详细原型)         │ │  │
│  │  │   [分析][新闻]    │  │  │  └─────────────────────────────┘ │  │
│  │  └──────────────────┘  │  │                                   │  │
│  │  ┌──────────────────┐  │  │                                   │  │
│  │  │ ● 智能助手        │  │  │                                   │  │
│  │  │   DeepSeek   [●]  │  │  │                                   │  │
│  │  │   [聊天][系统]    │  │  │                                   │  │
│  │  └──────────────────┘  │  │                                   │  │
│  │  ┌──────────────────┐  │  │                                   │  │
│  │  │ ○ 技术分析师      │  │  │                                   │  │
│  │  │   Qwen     [○]   │  │  │                                   │  │
│  │  │   [分析][技术]    │  │  │                                   │  │
│  │  └──────────────────┘  │  │                                   │  │
│  │                        │  │                                   │  │
│  │  已加载全部 5 个       │  │                                   │  │
│  └────────────────────────┘  └───────────────────────────────────┘  │
└────────────────────────────────────────────────────────────────────┘
```

### 11.3 右侧详情编辑面板

```
┌─ 详情/编辑 ──────────────────────────────────────────────────────┐
│                                                                    │
│  ┌─ 市场分析师 ────────────── [系统] [●启用] ─────────────────┐    │
│  └────────────────────────────────────────────────────────────┘    │
│                                                                    │
│  ━━ 基本信息 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━    │
│  编码:    market_analyst                              (只读)       │
│  名称:    [市场分析师            ]                                  │
│  描述:    [分析市场整体走势、板块轮动、资金流向              ]      │
│  类型:    ☐ 聊天助手                                                │
│                                                                    │
│  ━━ 提示词绑定 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━    │
│  选择提示词:  [市场分析提示词 v3  ▾]                  [查看 ↗]     │
│               ↑ 下拉列出所有已启用 Prompt，显示 name + version     │
│                                                                    │
│  ━━ 提示词规格概览（只读，来自绑定的提示词）━━━━━━━━━━━━━━━━━━    │
│                                                                    │
│  ── 绑定工具 (3个) ──────────────────────────────────── [展开] ── │
│  ┌──────────────────────────────────────────────────────────────┐ │
│  │ 📊 行情数据查询    [数据]  builtin                           │ │
│  │ 📊 市场概况查询    [数据]  builtin                           │ │
│  │ 📈 技术指标计算    [分析]  builtin                           │ │
│  │                                                              │ │
│  │ ⚠ 新闻情绪分析    [分析]  ⚡内部调用大模型                    │ │
│  │         ↑ calls_llm 标记，仅展示提醒                          │ │
│  └──────────────────────────────────────────────────────────────┘ │
│  工具由提示词 bind_tools 决定，如需调整请编辑提示词                  │
│                                                                    │
│  ── 可用变量（来自绑定提示词动态推导）─────────────── [展开] ──  │
│  ┌──────────────────────────────────────────────────────────────┐ │
│  │ 工具入参: date, symbol                                      │ │
│  │ 工具出参: market_data, indicators                           │ │
│  │ 文本占位符: company_name, current_date                      │ │
│  └──────────────────────────────────────────────────────────────┘ │
│                                                                    │
│  ━━ 工作流输出（只读）━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━    │
│  ┌──────────────────────────────────────────────────────────────┐ │
│  │ 输出名: market_analyst                                      │ │
│  │ 来源: Agent code                                            │ │
│  │ 内容: Agent 执行后的完整 LLM 输出文本                         │ │
│  └──────────────────────────────────────────────────────────────┘ │
│  工作流下游节点通过 Agent code 引用上游完整输出                    │
│                                                                    │
│  ━━ 模型配置 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━    │
│  [●] 使用系统默认              ← el-switch 开关                    │
│                                                                    │
│  ── 开关关闭时展开自定义配置 ──                                    │
│  模型厂商:  [DeepSeek ▾]          ← 联动，选厂商后过滤模型列表     │
│  模型名称:  [deepseek-chat  ▾]    ← 数据来自 GET /agents/models    │
│  温度:      [●───────○──] 0.3    ← el-slider, 0.0 - 2.0          │
│  最大输出:  [4096    ] tokens    ← el-input-number                 │
│                                                                    │
│  ━━ 运行参数 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━    │
│  最大工具调用: [10  ]   超时(秒): [300 ]   失败重试: [○]           │
│                                                                    │
│  ━━ 标签 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━    │
│  [分析] [盯盘] [+ 添加标签]                                        │
│  ↑ el-select multiple filterable allow-create                     │
│                                                                    │
│  ━━ 统计 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━    │
│  调用 24 次 | 最后调用 2026-05-20 14:32 | 创建 2026-05-01         │
│                                                                    │
│  ━━ 操作 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━    │
│  [💾 保存]  [▶ 测试运行]  [🗑 删除(系统Agent不可删)]                │
│                                                                    │
└────────────────────────────────────────────────────────────────────┘
```

### 11.4 新建 Agent 对话框 (el-dialog)

```
┌── 新建 Agent ───────────────────────────────────── [✕] ──────────┐
│                                                                    │
│  编码:      [market_analyst     ]  仅小写字母/数字/下划线          │
│  名称:      [市场分析师          ]                                  │
│  描述:      [分析市场整体走势... ]                                  │
│                                                                    │
│  提示词:    [请选择提示词     ▾]  ← 必填，下拉选择                  │
│                                                                    │
│  模型:      [●] 使用系统默认                                       │
│             [ ] 自定义: [厂商▾] [模型▾] 温度[0.7] tokens[4096]     │
│                                                                    │
│  类型:      [ ] 聊天助手                                           │
│  标签:      [+ 添加]                                               │
│                                                                    │
│  ─────────────────────────────────────────────────────────────     │
│                                        [取消]  [创建]              │
└────────────────────────────────────────────────────────────────────┘
```

### 11.5 测试运行对话框 (el-dialog)

```
┌── 测试运行: 市场分析师 ──────────────────────────── [✕] ──────────┐
│                                                                    │
│  ━━ 变量填充（来自提示词动态占位符）━━━━━━━━━━━━━━━━━━━━━━━━━━    │
│  date:    [2026-05-20          ]  (默认: today)                    │
│  symbol:  [000001              ]  (可选)                           │
│                                                                    │
│  ━━ 测试消息 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━    │
│  [请分析今天的大盘走势，重点关注资金流向                    ]  [发送] │
│                                                                    │
│  ━━ 执行结果（SSE 流式）━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━    │
│                                                                    │
│  🤖 市场分析师:                                                    │
│  │ 今日A股三大指数涨跌互现，上证指数收于3,234点...                  │
│  │                                                                 │
│  │ 资金流向方面，北向资金净流入32亿元...                            │
│  │                                                                 │
│  │ 🔧 调用: get_market_overview()                                  │
│  │ 📊 返回: {shanghai: +0.5%, ...}                  ✅ 1.2s       │
│  │                                                                 │
│  │ 🔧 调用: get_capital_flow()                                     │
│  │ 📊 返回: {northbound: +32亿, ...}                ✅ 0.8s       │
│  │                                                                 │
│  │ 综合来看，午后资金回流消费板块...                                │
│  │ █                                                      ← 光标   │
│                                                                    │
│  ─────────────────────────────────────────────────────────────     │
│  耗时: 12.3s  |  工具调用: 2次  |  Token: 1,200/800  [⏹ 停止]     │
└────────────────────────────────────────────────────────────────────┘
```

SSE 事件类型（复用 chat/sse.py 基础设施）：

| 事件 | 数据 | 说明 |
|------|------|------|
| `token` | `{"content": "..."}` | 流式文本输出 |
| `tool_call` | `{"name": "...", "args": {...}}` | Agent 发起工具调用 |
| `tool_result` | `{"name": "...", "result": "...", "duration": 1.2}` | 工具返回结果 |
| `done` | `{"tokens": {...}, "duration": ...}` | 执行完成 |
| `error` | `{"message": "..."}` | 执行出错 |

### 11.6 前端 API 模块

文件: `frontend/src/api/agents.ts`

```typescript
interface Agent {
  id: string
  code: string
  name: string
  description: string
  prompt_id: string
  model_config?: {
    provider?: string
    model?: string
    temperature?: number
    max_tokens?: number
  }
  parameters: {
    max_tool_calls: number
    timeout: number
    retry_on_failure: boolean
  }
  tags: string[]
  is_chat: boolean
  is_system: boolean
  enabled: boolean
  usage_count: number
  last_used_at?: string
  created_at: string
  updated_at: string
}

interface AgentListParams {
  search?: string
  tag?: string
  enabled?: boolean
  is_chat?: boolean
  page?: number
  page_size?: number
}

interface AgentCreateDto {
  code: string
  name: string
  description?: string
  prompt_id: string
  model_config?: { provider?: string; model?: string; temperature?: number; max_tokens?: number }
  parameters?: { max_tool_calls?: number; timeout?: number; retry_on_failure?: boolean }
  tags?: string[]
  is_chat?: boolean
  enabled?: boolean
}

interface AgentUpdateDto {
  name?: string
  description?: string
  prompt_id?: string
  model_config?: { provider?: string; model?: string; temperature?: number; max_tokens?: number } | null
  parameters?: { max_tool_calls?: number; timeout?: number; retry_on_failure?: boolean }
  tags?: string[]
  is_chat?: boolean
  enabled?: boolean
}

const agentsApi = {
  list(params?: AgentListParams),
  get(id: string),
  create(payload: AgentCreateDto),
  update(id: string, payload: AgentUpdateDto),
  remove(id: string),
  toggle(id: string, enabled: boolean),
  getTags(),
  getModels(),           // GET /agents/models → 模型选择器数据
  seed(),
}
```

### 11.7 路由与菜单

**路由注册** (`frontend/src/router/index.ts`)：

```typescript
{
  path: '/agents',
  name: 'AgentManagement',
  component: BasicLayout,
  meta: { title: 'Agent 管理', icon: 'UserFilled', requiresAuth: true },
  children: [{
    path: '',
    name: 'AgentManagementHome',
    component: () => import('@/views/AgentManagement/index.vue'),
    meta: { title: 'Agent 管理', requiresAuth: true }
  }]
}
```

**侧边栏菜单** (`frontend/src/components/Layout/SidebarMenu.vue`)：

在管理中心分组中，`Agent 管理` 排在工具管理、提示词管理之前：

```
├── ── 管理中心 ──
│   ├── Agent 管理        icon: UserFilled
│   ├── 工具管理          icon: SetUp
│   ├── 提示词管理        icon: Document
│   ├── ...
```

### 11.8 交互要点总结

| 场景 | 交互 |
|------|------|
| 列表项点击 | 左侧高亮选中，右侧加载详情，复用 ToolManagement 的选中样式 |
| 启用/禁用 | 列表项内嵌 el-switch，点击即切换，无需进入编辑模式 |
| 提示词选择器 | el-select 远程搜索，显示 name + version，选中后下方刷新规格概览 |
| 工具/变量展示 | 只读折叠面板，工具来自绑定提示词的 bind_tools，变量来自工具元数据和提示词文本动态推导 |
| 工作流输出展示 | 只读展示 Agent code 作为默认输出名，执行结果是完整 LLM 输出文本 |
| 模型选择 | el-switch 控制"使用默认"；关闭后展开 provider→model 二级联动 + temperature 滑块 |
| 测试运行 | el-dialog 内嵌 SSE 流式输出，复用 Chat 页面消息气泡样式 |
| 保存 | 编辑后点击保存，el-message 反馈成功/失败 |
| 删除 | el-popconfirm 二次确认，系统 Agent 禁用删除按钮 |
| 种子初始化 | 页头按钮，调用 POST /agents/seed，el-message 反馈创建/跳过数量 |

---

