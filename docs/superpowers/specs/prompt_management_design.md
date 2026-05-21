# 提示词管理模块设计文档

> 版本：v1.0 | 日期：2026-05-20 | 分支：rebuild

## 1. 概述

提示词管理是管理中心的核心模块，为后续 Agent 管理、工作流编排提供提示词配置能力。

核心设计：
- **模块化组装**：提示词由有序 Block 列表组成，自由排列组合
- **工具绑定**：选提示词 = 选工具，绑定工具后自动推导出入参变量
- **变量灵活**：变量来自工具推导 + 手动编写，运行时由 agent 调用方注入
- **版本管理**：同一 code 多版本，仅一个 active，可删除非 active 版本
- **系统保护**：seed 注入的系统提示词不可删除

---

## 2. 数据模型

### 2.1 `prompts` 集合

```json
{
  "_id": ObjectId,
  "code": "market_analyst_system",
  "name": "市场分析提示词",
  "description": "用于市场分析师的系统提示词",

  "prompt_type": "workflow",

  "blocks": [
    {
      "type": "text",
      "label": "系统角色",
      "content": "你是一位专业的股票技术分析师。\n分析标的：{{company_name}}({{ticker}})\n当前日期：{{current_date}}\n可用工具：{{tool_names}}\n市场：{{market_name}} 货币：{{currency_name}}({{currency_symbol}})"
    },
    {
      "type": "text",
      "label": "分析指令",
      "content": "请先使用工具获取数据，然后生成详细的技术分析报告..."
    },
    {
      "type": "messages_placeholder",
      "label": "对话历史"
    }
  ],

  "bind_tools": [
    "get_stock_market_data_unified",
    "get_YFin_data_online",
    "get_stockstats_indicators_report_online"
  ],

  "tags": ["分析", "技术面"],
  "enabled": true,
  "is_system": false,
  "is_active": true,
  "version": 1,
  "agent_count": 0,

  "created_at": datetime,
  "updated_at": datetime
}
```

### 2.2 字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| `code` | string | 唯一编码，同一 code 下有多个版本 |
| `name` | string | 显示名称 |
| `description` | string | 描述 |
| `prompt_type` | string | `chat` / `workflow`，决定运行时注入行为 |
| `blocks` | array | 有序 Block 列表 |
| `bind_tools` | array[string] | 绑定的工具名列表 |
| `tags` | array[string] | 标签 |
| `enabled` | bool | 是否启用 |
| `is_system` | bool | 系统提示词（seed 产生），不可删除 |
| `is_active` | bool | 同一 code 下仅一个 true |
| `version` | int | 版本号，自增 |
| `agent_count` | int | 被 agent 引用计数 |

### 2.3 Block 类型

只有两种：

| type | 用户能做什么 | 运行时行为 |
|------|------------|-----------|
| `text` | 编辑 label + content，自由插入 `{{变量}}` | 文本按序拼接，变量替换后作为消息 |
| `messages_placeholder` | 仅编辑 label | 插入 LangGraph 对话历史占位符 |

运行时注入由 `prompt_type` 驱动，不由 block 类型驱动：
- `workflow` → 按需注入工作流状态（分析报告、辩论结果等）
- `chat` → 按需注入对话上下文

### 2.4 索引

```
prompts: { code: 1, version: 1 } unique
prompts: { code: 1, is_active: 1 }
prompts: { name: 1 } unique
prompts: { tags: 1 }
prompts: { prompt_type: 1 }
```

### 2.5 版本管理规则

- 同一 `code` 下可有多个版本，`version` 自增
- 同一 `code` 下仅一个 `is_active: true`
- `is_active: true` 的版本**不可删除**
- `is_active: false` 的版本**可删除**
- 保存时可选：更新当前版本 / 创建新版本
- `is_system: true` 的版本**不可删除**（无论是否 active）

---

## 3. 变量系统

### 3.1 设计原则

**变量不入库**。变量是编辑时的辅助概念，不是独立的数据记录。

### 3.2 变量来源

| 来源 | 说明 | 前端如何获取 |
|------|------|------------|
| 工具入参 | 绑定工具的 `parameters` 字段 | 选中工具后自动解析展示 |
| 工具出参 | 绑定工具的 `output_schema` 字段 | 选中工具后自动解析展示 |
| 手动编写 | 用户在文本中自由输入 `{{any_var}}` | 正则从 text block 内容提取 |

### 3.3 变量展示

```
┌─ 可用变量 ────────────────────────────────┐
│                                            │
│ 📥 来自工具入参                             │
│  [{{symbol}}]      股票代码                │
│  [{{market}}]      市场                    │
│                                            │
│ 📤 来自工具出参                             │
│  [{{market_data}}] 行情数据                │
│  [{{indicators}}]  技术指标                │
│                                            │
│ ✏️ 文本中已使用（手动编写）                   │
│  [{{company_name}}]   公司名称              │
│  [{{ticker}}]         股票代码              │
│  [{{current_date}}]   当前日期              │
│  [{{market_name}}]    市场名称              │
│                                            │
└────────────────────────────────────────────┘
```

点击变量标签 → 插入到当前聚焦的文本块光标位置。

### 3.4 变量提取逻辑

```python
VARIABLE_PATTERN = re.compile(r"\{\{(\w+)\}\}")

def extract_variables_from_blocks(blocks: list) -> list[str]:
    variables = set()
    for block in blocks:
        if block.get("type") == "text":
            content = block.get("content", "")
            variables.update(VARIABLE_PATTERN.findall(content))
    return sorted(variables)
```

### 3.5 运行时变量注入

变量在 agent 被调用时由调用方注入，提示词管理模块只负责存储和展示：

```python
def render_prompt(prompt_doc, **variables):
    parts = []
    for block in prompt_doc["blocks"]:
        if block["type"] == "text":
            content = block["content"]
            for key, value in variables.items():
                content = content.replace(f"{{{{{key}}}}}", str(value))
            parts.append(content)
        elif block["type"] == "messages_placeholder":
            parts.append("{{MESSAGES_PLACEHOLDER}}")
    return parts
```

---

## 4. 工具绑定

### 4.1 选择方式

从工具管理列表（`tools` 集合）中搜索选择，不是 checkbox 枚举。

```
┌─ 工具绑定 ───────────────────────────────────┐
│                                               │
│ 🔍 搜索工具名称或描述...                       │
│                                               │
│ 已绑定:                                       │
│ ┌───────────────────────────────────────────┐│
│ │ × get_stock_market_data_unified    行情数据││
│ │ × get_YFin_data_online             Yahoo  ││
│ │ × get_stockstats_indicators_report  技术指标││
│ └───────────────────────────────────────────┘│
│                                               │
│ 搜索结果:                                     │
│ ┌───────────────────────────────────────────┐│
│ │ + get_stock_news_unified          新闻数据 ││
│ │ + get_stock_sentiment_unified     情绪分析 ││
│ │ + get_stock_fundamentals_unified  基本面   ││
│ └───────────────────────────────────────────┘│
└──────────────────────────────────────────────┘
```

### 4.2 绑定后的副作用

- 工具的 `parameters` 自动解析为"来自工具入参"的可用变量
- 工具的 `output_schema` 自动解析为"来自工具出参"的可用变量
- 右侧变量区域实时更新

### 4.3 数据存储

只存储工具名列表：`bind_tools: ["tool_name_1", "tool_name_2"]`

运行时通过 `ToolService` 查询工具详情，解析出入参出参。

---

## 5. 后端 API

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/prompts/` | 提示词列表（按 type/tag/enabled 筛选，默认仅 active） |
| GET | `/api/prompts/{id}` | 提示词详情 |
| POST | `/api/prompts/` | 创建提示词（version=1, is_active=true） |
| PUT | `/api/prompts/{id}` | 更新当前版本内容 |
| POST | `/api/prompts/{id}/new-version` | 基于当前版本创建新版本 |
| DELETE | `/api/prompts/{id}` | 删除指定版本（active 或 system 拒绝） |
| PUT | `/api/prompts/{id}/activate` | 激活指定版本 |
| GET | `/api/prompts/code/{code}/versions` | 获取某 code 下所有版本 |
| POST | `/api/prompts/{id}/render` | 预览渲染 |
| GET | `/api/prompts/variables?tools=...` | 从工具推导变量列表 |
| POST | `/api/prompts/seed` | 触发 seed |
| GET | `/api/prompts/tags` | 获取所有标签 |
| PUT | `/api/prompts/{id}/toggle` | 启用/禁用 |

### 关键接口 Schema

**创建/更新**：
```json
{
  "code": "market_analyst_system",
  "name": "市场分析提示词",
  "description": "...",
  "prompt_type": "workflow",
  "blocks": [
    {"type": "text", "label": "系统角色", "content": "..."},
    {"type": "messages_placeholder", "label": "对话历史"}
  ],
  "bind_tools": ["get_stock_market_data_unified"],
  "tags": ["分析"]
}
```

**变量推导** `GET /api/prompts/variables?tools=tool_a,tool_b`：
```json
{
  "tool_params": [
    {"name": "symbol", "description": "股票代码", "source_tool": "get_stock_market_data_unified"}
  ],
  "tool_outputs": [
    {"name": "market_data", "description": "行情数据", "source_tool": "get_stock_market_data_unified"}
  ]
}
```

**预览渲染** `POST /api/prompts/{id}/render`：
```json
// Request
{"variables": {"company_name": "苹果公司", "ticker": "AAPL"}}
// Response
{
  "rendered_blocks": [
    {"type": "text", "label": "系统角色", "content": "你是一位专业的...苹果公司(AAPL)..."},
    {"type": "messages_placeholder", "label": "对话历史"}
  ],
  "unresolved_variables": ["current_date", "market_name"]
}
```

---

## 6. 前端页面

### 6.1 路由与入口

- 路由：`/prompts`
- 侧边栏：管理中心 → 提示词管理
- 布局：左右分栏（列表 | 编辑区）

### 6.2 页面布局

```
┌── 提示词管理 [+ 新建] [初始化 Seed] ──────────────────────────────┐
│ 筛选: [类型▾] [标签▾] [状态▾] [搜索...]                           │
│                                                                     │
│ ┌─ 列表(span=8) ─────────┐   ┌─ 编辑区(span=16) ──────────────┐ │
│ │                          │   │                                 │ │
│ │ 🔍 搜索...               │   │ 名称: [___________]            │ │
│ │                          │   │ 类型: [workflow▾]              │ │
│ │ ● 市场分析提示词  v3 ●   │   │ 描述: [___________]            │ │
│ │   workflow · 系统        │   │                                 │ │
│ │   [管理版本]             │   │ ── 版本 ──                     │ │
│ │                          │   │ v3(当前) v2 v1                  │ │
│ │ ● 新闻分析提示词  v1 ●   │   │ [保存] [另存为新版本]           │ │
│ │   workflow · 系统        │   │                                 │ │
│ │                          │   │ ── 提示词构造序列 ──           │ │
│ │ ○ 保守分析      v2       │   │                                 │ │
│ │   workflow · 自定义      │   │ [≡1] 系统角色      [✏][✕]     │ │
│ │                          │   │ ┌────────────────────────┐    │ │
│ │ ● 智能助手      v1 ●   │   │ │你是一位专业的股票...    │    │ │
│ │   chat · 系统            │   │ │{{company_name}}{{ticker}}│   │ │
│ │                          │   │ └────────────────────────┘    │ │
│ │                          │   │                                 │ │
│ │                          │   │ [≡2] 分析指令      [✏][✕]     │ │
│ │                          │   │ ┌────────────────────────┐    │ │
│ │                          │   │ │请先使用工具获取数据... │    │ │
│ │                          │   │ └────────────────────────┘    │ │
│ │                          │   │                                 │ │
│ │                          │   │ [≡3] 📌对话历史    [✕]        │ │
│ │                          │   │                                 │ │
│ │                          │   │ [+ 文本块] [+ 对话历史占位符] │ │
│ │                          │   │                                 │ │
│ │                          │   │ ── 工具绑定 ──                 │ │
│ │                          │   │ 🔍 搜索工具...                 │ │
│ │                          │   │ [×行情] [×技术] [+添加]        │ │
│ │                          │   │                                 │ │
│ │                          │   │ ── 可用变量 ──                 │ │
│ │                          │   │ 📥工具入参: [{{symbol}}]...    │ │
│ │                          │   │ 📤工具出参: [{{market_data}}]  │ │
│ │                          │   │ ✏️已使用: [{{company_name}}]   │ │
│ │                          │   │                                 │ │
│ │                          │   │ 标签: [分析] [+添加]           │ │
│ │                          │   │ [●启用] [保存] [删除]          │ │
│ └──────────────────────────┘   └─────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
```

### 6.3 版本管理面板

点击列表中的"管理版本"展开：

```
┌─ 市场分析提示词 - 版本管理 ──────────────────┐
│                                               │
│ ● v3 (当前)  2026-05-20  [编辑]               │
│ ○ v2         2026-05-18  [激活]  [编辑] [删除]│
│ ○ v1         2026-05-15  [激活]  [编辑] [删除]│
│                                               │
└───────────────────────────────────────────────┘
```

- 当前 active 版本标 ●，只有 [编辑]
- 非 active 版本有 [激活] [编辑] [删除]
- `is_system: true` 的版本无 [删除] 按钮

---

## 7. Seed 策略

### 7.1 defaults.py

从 14 个 agent 源码中提取现有提示词文本，硬编码为 seed 数据：

```python
PROMPT_SEEDS = [
    {
        "code": "market_analyst_system",
        "name": "市场分析提示词",
        "prompt_type": "workflow",
        "blocks": [
            {
                "type": "text",
                "label": "系统角色",
                "content": "你是一位专业的股票技术分析师。\n..."
            },
            {
                "type": "messages_placeholder",
                "label": "对话历史"
            }
        ],
        "bind_tools": [
            "get_stock_market_data_unified",
            "get_YFin_data_online",
            "get_stockstats_indicators_report_online",
            "get_YFin_data",
            "get_stockstats_indicators_report"
        ],
        "tags": ["分析", "技术面"]
    },
    # ... 其余 13 个
]
```

### 7.2 Seed 逻辑

`POST /api/prompts/seed`：
1. 遍历 `PROMPT_SEEDS`
2. 按 `code` 查询是否已存在
3. 不存在 → 插入，`is_system=true, is_active=true, version=1`
4. 已存在 → **跳过**（不覆盖用户修改）
5. 返回 `{created: N, skipped: M}`

---

## 8. 文件清单

### 重构

| 文件 | 改动 |
|------|------|
| `app/services/prompt_service.py` | sections → blocks，移除 variables 存储字段，新增 prompt_type |
| `app/routers/prompts.py` | 更新 API 匹配新数据模型 |
| `frontend/src/router/index.ts` | 新增 `/prompts` 路由 |
| `frontend/src/components/Layout/SidebarMenu.vue` | 管理中心增加"提示词管理" |

### 新建

| 文件 | 用途 |
|------|------|
| `app/schemas/prompts.py` | Pydantic 校验模型 |
| `frontend/src/api/prompts.ts` | TS 接口 + API 方法 |
| `frontend/src/views/PromptManagement/index.vue` | 提示词管理页面 |
| `tradingagents/prompts/defaults.py` | 14 个 agent 默认提示词 seed |

### 不动

- `app/services/tool_service.py` / `app/routers/tools.py` — prompt 通过 tool_service 查询工具详情
- 14 个 agent 源码 — 本阶段不动，后续 Agent 管理模块改造

---

## 9. 实施阶段

### Phase 1：后端重构

1. 重构 `prompt_service.py`（blocks 数据模型、版本管理、变量推导）
2. 新建 `app/schemas/prompts.py`
3. 更新 `app/routers/prompts.py`
4. 新建 `tradingagents/prompts/defaults.py`

验证：`POST /api/prompts/seed` → `GET /api/prompts/` 返回 14 个提示词

### Phase 2：前端页面

1. 新建 `frontend/src/api/prompts.ts`
2. 新建 `frontend/src/views/PromptManagement/index.vue`
3. 注册路由 + 侧边栏菜单

验证：完整 CRUD、block 拖拽排序、工具搜索绑定、变量展示插入

---

## 10. 与后续模块的关系

| 后续模块 | 依赖提示词管理的部分 |
|----------|-------------------|
| Agent 管理 | agent 选择提示词 → 继承工具绑定 + 注入变量 |
| 工作流管理 | 工作流节点关联 agent → 间接使用提示词 |
| AI Chat | chat 类型提示词 + 上下文注入 |
| 运行时 | render_prompt() 组装 blocks + 替换变量 → 交给 agent |
