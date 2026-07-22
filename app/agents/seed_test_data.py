"""
测试用 提示词 → Agent → 工作流 完整种子数据。

创建三个复杂度递增的测试工作流，覆盖以下场景：

  Level 1 — test_linear_chain
      输入 → Agent(builtin×2) → Agent(纯LLM) → 输出
      验证: 工具绑定调用、input_mapping、节点间 output 传递

  Level 2 — test_parallel_fanout
      输入 → [行情(2工具), 新闻(1工具), 风险(1工具)](并行) → 汇总(纯LLM) → 输出
      验证: DAG 并行执行、扇入汇聚、跨节点 {{node.output}} 引用

  Level 3 — test_nested_composite
      输入 → [Subflow(Level2) + Subflow(Level1)](并行)
           → Agent(workflow 工具 + builtin 工具) → 输出
      验证: subflow 递归调用、workflow 类型工具、多层嵌套组合

依赖链: prompts → agents → workflow_1/2 → workflow_tool → workflow_3
内置工具直接引用已有 handler，无需额外 mock。
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List

from app.core.database import get_mongo_db

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
# 1. 测试提示词
# ═══════════════════════════════════════════════════════════════

TEST_PROMPT_SEEDS: List[Dict[str, Any]] = [
    {
        "code": "test_data_collector_prompt",
        "name": "[测试] 数据采集员提示词",
        "description": "绑定 get_current_time + calculator，测试工具调用链路",
        "prompt_type": "workflow",
        "blocks": [
            {
                "type": "text",
                "content": (
                    "你是一个测试数据采集 Agent。\n"
                    "分析标的：{{ticker}}，日期：{{current_date}}。\n"
                    "请依次调用所有工具获取数据，用中文简短回复。\n"
                    "可用工具：{{tool_names}}。"
                ),
            },
            {"type": "messages_placeholder", "label": "对话历史"},
        ],
        "bind_tools": ["get_current_time", "calculator"],
        "tags": ["测试", "数据采集"],
    },
    {
        "code": "test_market_analyst_prompt",
        "name": "[测试] 行情分析师提示词",
        "description": "绑定统一行情 + 时间工具，测试行情数据获取",
        "prompt_type": "workflow",
        "blocks": [
            {
                "type": "text",
                "content": (
                    "你是一个测试行情分析 Agent。\n"
                    "分析标的：{{ticker}}，日期：{{current_date}}。\n"
                    "请使用工具获取行情数据并给出简短分析。\n"
                    "可用工具：{{tool_names}}。"
                ),
            },
            {"type": "messages_placeholder", "label": "对话历史"},
        ],
        "bind_tools": ["get_stock_market_data_unified", "get_current_time"],
        "tags": ["测试", "行情"],
    },
    {
        "code": "test_news_analyst_prompt",
        "name": "[测试] 新闻分析师提示词",
        "description": "绑定统一新闻工具，测试新闻数据获取",
        "prompt_type": "workflow",
        "blocks": [
            {
                "type": "text",
                "content": (
                    "你是一个测试新闻分析 Agent。\n"
                    "分析标的：{{ticker}}，日期：{{current_date}}。\n"
                    "请使用工具获取新闻并给出简短分析。\n"
                    "可用工具：{{tool_names}}。"
                ),
            },
            {"type": "messages_placeholder", "label": "对话历史"},
        ],
        "bind_tools": ["get_stock_news_unified"],
        "tags": ["测试", "新闻"],
    },
    {
        "code": "test_risk_scorer_prompt",
        "name": "[测试] 风险评分员提示词",
        "description": "绑定计算器，测试数值计算场景",
        "prompt_type": "workflow",
        "blocks": [
            {
                "type": "text",
                "content": (
                    "你是一个测试风险评估 Agent。\n"
                    "分析标的：{{ticker}}，日期：{{current_date}}。\n"
                    "请使用计算器工具计算风险指标，给出简短评估。\n"
                    "可用工具：{{tool_names}}。"
                ),
            },
            {"type": "messages_placeholder", "label": "对话历史"},
        ],
        "bind_tools": ["calculator"],
        "tags": ["测试", "风险"],
    },
    {
        "code": "test_summary_prompt",
        "name": "[测试] 综合总结员提示词",
        "description": "无工具，纯 LLM 总结，测试无工具 Agent 链路",
        "prompt_type": "workflow",
        "blocks": [
            {
                "type": "text",
                "content": (
                    "你是一个测试综合分析 Agent。\n"
                    "请根据以下输入数据，用中文给出简短的综合分析总结。\n"
                    "不要使用任何工具，直接分析即可。"
                ),
            },
            {"type": "messages_placeholder", "label": "对话历史"},
        ],
        "bind_tools": [],
        "tags": ["测试", "总结"],
    },
    {
        "code": "test_composite_prompt",
        "name": "[测试] 复合分析员提示词",
        "description": "绑定工作流工具 + 内置工具，验证工具嵌套",
        "prompt_type": "workflow",
        "blocks": [
            {
                "type": "text",
                "content": (
                    "你是一个测试复合分析 Agent。\n"
                    "分析标的：{{ticker}}，日期：{{current_date}}。\n"
                    "请先使用工作流工具获取基础分析结果，再用其他工具补充，最后综合分析。\n"
                    "可用工具：{{tool_names}}。"
                ),
            },
            {"type": "messages_placeholder", "label": "对话历史"},
        ],
        "bind_tools": ["test_workflow_tool", "get_current_time", "calculator"],
        "tags": ["测试", "复合", "工具嵌套"],
    },
]


# ═══════════════════════════════════════════════════════════════
# 2. 测试 Agent
# ═══════════════════════════════════════════════════════════════

TEST_AGENT_SEEDS: List[Dict[str, Any]] = [
    {
        "code": "test_data_collector",
        "name": "[测试] 数据采集员",
        "description": "绑定时间+计算工具，验证工具调用链路",
        "prompt_code": "test_data_collector_prompt",
        "message_template": "请获取 {{ticker}} 在 {{current_date}} 的相关数据。",
        "tags": ["测试", "数据采集"],
    },
    {
        "code": "test_market_analyst",
        "name": "[测试] 行情分析师",
        "description": "绑定行情工具，验证市场数据获取",
        "prompt_code": "test_market_analyst_prompt",
        "message_template": "请分析 {{ticker}} 的行情数据。",
        "tags": ["测试", "行情"],
    },
    {
        "code": "test_news_analyst",
        "name": "[测试] 新闻分析师",
        "description": "绑定新闻工具，验证新闻获取",
        "prompt_code": "test_news_analyst_prompt",
        "message_template": "请分析 {{ticker}} 的相关新闻。",
        "tags": ["测试", "新闻"],
    },
    {
        "code": "test_risk_scorer",
        "name": "[测试] 风险评分员",
        "description": "绑定计算器工具，验证数值计算",
        "prompt_code": "test_risk_scorer_prompt",
        "message_template": "请评估 {{ticker}} 的风险指标。",
        "tags": ["测试", "风险"],
    },
    {
        "code": "test_summary_agent",
        "name": "[测试] 综合总结员",
        "description": "无工具，纯 LLM 总结",
        "prompt_code": "test_summary_prompt",
        "message_template": "请根据以下数据给出综合分析：{{input_data}}",
        "tags": ["测试", "总结"],
    },
    {
        "code": "test_composite_agent",
        "name": "[测试] 复合分析员",
        "description": "绑定工作流工具+内置工具，验证工具嵌套",
        "prompt_code": "test_composite_prompt",
        "message_template": "请对 {{ticker}} 进行复合分析，结合子工作流结果和工具数据。",
        "tags": ["测试", "复合", "工具嵌套"],
    },
]


# ═══════════════════════════════════════════════════════════════
# 3. 测试工作流（三个复杂度递增）
# ═══════════════════════════════════════════════════════════════

TEST_WORKFLOW_SEEDS: List[Dict[str, Any]] = [
    # ── Level 1: 线性链路 ────────────────────────────────────
    {
        "code": "test_linear_chain",
        "name": "[测试] 线性工具链",
        "description": (
            "Level 1 — 线性链路验证\n"
            "输入 → 数据采集(builtin×2) → 分析总结(纯LLM) → 输出\n"
            "测试点: 工具绑定与调用、input_mapping、节点间 output 传递"
        ),
        "message_template": "请对 {{input.ticker}} 进行数据采集和分析。",
        "output_template": "{{summary.output}}",
        "nodes": [
            {"id": "start", "type": "io", "label": "输入", "config": {"io_direction": "input"}},
            {
                "id": "collector",
                "type": "agent",
                "label": "数据采集",
                "config": {
                    "agent_code": "test_data_collector",
                    "input_mapping": {
                        "ticker": "{{input.ticker}}",
                        "current_date": "{{input.current_date}}",
                    },
                },
            },
            {
                "id": "summary",
                "type": "agent",
                "label": "分析总结",
                "config": {
                    "agent_code": "test_summary_agent",
                    "input_mapping": {"input_data": "{{collector.output}}"},
                },
            },
            {"id": "end", "type": "io", "label": "输出", "config": {"io_direction": "output"}},
        ],
        "edges": [
            {"id": "e1", "source": "start", "target": "collector"},
            {"id": "e2", "source": "collector", "target": "summary"},
            {"id": "e3", "source": "summary", "target": "end"},
        ],
        "settings": {"timeout": 300, "on_failure": "notify", "retry_count": 0},
        "tags": ["测试", "Level1", "线性"],
    },
    # ── Level 2: 并行扇出扇入 ────────────────────────────────
    {
        "code": "test_parallel_fanout",
        "name": "[测试] 并行分析扇出",
        "description": (
            "Level 2 — 并行 DAG 验证\n"
            "输入 → [行情(2工具) + 新闻(1工具) + 风险(1工具)](并行)"
            " → 汇总(纯LLM) → 输出\n"
            "测试点: 并行执行、扇入汇聚、{{node.output}} 跨节点引用"
        ),
        "message_template": "请对 {{input.ticker}} 进行全面并行分析。",
        "output_template": "{{aggregate.output}}",
        "nodes": [
            {"id": "start", "type": "io", "label": "输入", "config": {"io_direction": "input"}},
            {
                "id": "market",
                "type": "agent",
                "label": "行情分析",
                "config": {
                    "agent_code": "test_market_analyst",
                    "input_mapping": {
                        "ticker": "{{input.ticker}}",
                        "current_date": "{{input.current_date}}",
                    },
                },
            },
            {
                "id": "news",
                "type": "agent",
                "label": "新闻分析",
                "config": {
                    "agent_code": "test_news_analyst",
                    "input_mapping": {
                        "ticker": "{{input.ticker}}",
                        "current_date": "{{input.current_date}}",
                    },
                },
            },
            {
                "id": "risk",
                "type": "agent",
                "label": "风险评估",
                "config": {
                    "agent_code": "test_risk_scorer",
                    "input_mapping": {
                        "ticker": "{{input.ticker}}",
                        "current_date": "{{input.current_date}}",
                    },
                },
            },
            {
                "id": "aggregate",
                "type": "agent",
                "label": "综合汇总",
                "config": {
                    "agent_code": "test_summary_agent",
                    "input_mapping": {
                        "input_data": (
                            "行情报告：{{market.output}}\n"
                            "新闻报告：{{news.output}}\n"
                            "风险评估：{{risk.output}}"
                        ),
                    },
                },
            },
            {"id": "end", "type": "io", "label": "输出", "config": {"io_direction": "output"}},
        ],
        "edges": [
            {"id": "e1", "source": "start", "target": "market"},
            {"id": "e2", "source": "start", "target": "news"},
            {"id": "e3", "source": "start", "target": "risk"},
            {"id": "e4", "source": "market", "target": "aggregate"},
            {"id": "e5", "source": "news", "target": "aggregate"},
            {"id": "e6", "source": "risk", "target": "aggregate"},
            {"id": "e7", "source": "aggregate", "target": "end"},
        ],
        "settings": {"timeout": 600, "on_failure": "notify", "retry_count": 0},
        "tags": ["测试", "Level2", "并行"],
    },
    # ── Level 3: 子工作流嵌套 + 工作流工具 ───────────────────
    {
        "code": "test_nested_composite",
        "name": "[测试] 嵌套组合分析",
        "description": (
            "Level 3 — 深度嵌套验证\n"
            "输入 → [Subflow(Level2) + Subflow(Level1)](并行)"
            " → 复合Agent(workflow工具 + builtin×2) → 输出\n"
            "测试点: subflow 递归调用、workflow 类型工具、多层嵌套组合"
        ),
        "message_template": "请对 {{input.ticker}} 进行深度嵌套分析。",
        "output_template": "{{composite.output}}",
        "nodes": [
            {"id": "start", "type": "io", "label": "输入", "config": {"io_direction": "input"}},
            {
                "id": "sub_parallel",
                "type": "subflow",
                "label": "并行分析(子工作流)",
                "config": {
                    "workflow_code": "test_parallel_fanout",
                    "input_mapping": {
                        "ticker": "{{input.ticker}}",
                        "current_date": "{{input.current_date}}",
                    },
                },
            },
            {
                "id": "sub_linear",
                "type": "subflow",
                "label": "线性分析(子工作流)",
                "config": {
                    "workflow_code": "test_linear_chain",
                    "input_mapping": {
                        "ticker": "{{input.ticker}}",
                        "current_date": "{{input.current_date}}",
                    },
                },
            },
            {
                "id": "composite",
                "type": "agent",
                "label": "复合分析(工作流工具)",
                "config": {
                    "agent_code": "test_composite_agent",
                    "input_mapping": {
                        "ticker": "{{input.ticker}}",
                        "current_date": "{{input.current_date}}",
                        "parallel_result": "{{sub_parallel.output}}",
                        "linear_result": "{{sub_linear.output}}",
                    },
                },
            },
            {"id": "end", "type": "io", "label": "输出", "config": {"io_direction": "output"}},
        ],
        "edges": [
            {"id": "e1", "source": "start", "target": "sub_parallel"},
            {"id": "e2", "source": "start", "target": "sub_linear"},
            {"id": "e3", "source": "sub_parallel", "target": "composite"},
            {"id": "e4", "source": "sub_linear", "target": "composite"},
            {"id": "e5", "source": "composite", "target": "end"},
        ],
        "settings": {"timeout": 900, "on_failure": "notify", "retry_count": 1},
        "tags": ["测试", "Level3", "嵌套", "子工作流"],
    },
]


# ═══════════════════════════════════════════════════════════════
# 4. 节点引用解析
# ═══════════════════════════════════════════════════════════════

async def _resolve_node_refs(nodes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """将 agent_code / workflow_code 解析为运行时 ID。"""
    from app.services.agent_service import agent_service
    from app.services.workflow_service import workflow_service

    resolved: List[Dict[str, Any]] = []
    for node in nodes:
        copy = dict(node)
        config = dict(copy.get("config", {}))

        if "agent_code" in config:
            agent_code = config.pop("agent_code")
            agent = await agent_service.get_agent_by_code(agent_code)
            if not agent:
                raise ValueError(f"Agent '{agent_code}' 不存在")
            config["agent_id"] = agent["id"]

        if "workflow_code" in config:
            wf_code = config.pop("workflow_code")
            wf = await workflow_service.get_workflow_by_code(wf_code)
            if not wf:
                raise ValueError(f"工作流 '{wf_code}' 不存在")
            config["workflow_id"] = wf["id"]

        copy["config"] = config
        resolved.append(copy)
    return resolved


# ═══════════════════════════════════════════════════════════════
# 5. 种子写入
# ═══════════════════════════════════════════════════════════════

async def seed_test_data() -> Dict[str, Any]:
    """写入全部测试种子数据。

    顺序: prompts → agents → workflow 1/2 → workflow 工具 → workflow 3
    幂等: 按 code 查重，已存在则跳过。
    """
    db = get_mongo_db()
    now = datetime.utcnow()

    stats: Dict[str, Any] = {
        "created_prompts": 0, "skipped_prompts": 0,
        "created_agents": 0, "skipped_agents": 0,
        "created_tools": 0, "skipped_tools": 0,
        "created_workflows": 0, "skipped_workflows": 0,
        "failed": [],
    }

    # ── Phase 1: Prompts ──────────────────────────────────────
    for seed in TEST_PROMPT_SEEDS:
        code = seed["code"]
        try:
            if await db.prompts.find_one({"code": code}):
                stats["skipped_prompts"] += 1
                continue
            await db.prompts.insert_one({
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
            })
            stats["created_prompts"] += 1
            logger.info(f"[TestSeed] 创建提示词: {code}")
        except Exception as exc:
            stats["failed"].append(f"prompt:{code}: {exc}")
            logger.exception(f"[TestSeed] 创建提示词失败 {code}")

    # ── Phase 2: Agents ───────────────────────────────────────
    from app.services.agent_service import agent_service

    for seed in TEST_AGENT_SEEDS:
        code = seed["code"]
        try:
            if await agent_service.get_agent_by_code(code):
                stats["skipped_agents"] += 1
                continue

            prompt = await db.prompts.find_one(
                {"code": seed["prompt_code"], "enabled": True, "is_active": True},
            )
            if not prompt:
                stats["failed"].append(
                    f"agent:{code}: 提示词 '{seed['prompt_code']}' 不存在"
                )
                continue

            await agent_service.create_agent({
                "code": code,
                "name": seed["name"],
                "description": seed.get("description", ""),
                "prompt_id": str(prompt["_id"]),
                "message_template": seed.get("message_template", ""),
                "tags": seed.get("tags", []),
                "is_chat": False,
                "is_system": True,
                "enabled": True,
            })
            stats["created_agents"] += 1
            logger.info(f"[TestSeed] 创建 Agent: {code}")
        except Exception as exc:
            stats["failed"].append(f"agent:{code}: {exc}")
            logger.exception(f"[TestSeed] 创建 Agent 失败 {code}")

    # ── Phase 3: Workflows (按依赖顺序) ───────────────────────
    from app.services.workflow_service import workflow_service

    for seed in TEST_WORKFLOW_SEEDS:
        code = seed["code"]
        try:
            if await workflow_service.get_workflow_by_code(code):
                stats["skipped_workflows"] += 1
                continue

            resolved_nodes = await _resolve_node_refs(seed.get("nodes", []))
            await workflow_service.create_workflow({
                "code": code,
                "name": seed["name"],
                "description": seed.get("description", ""),
                "message_template": seed.get("message_template", ""),
                "output_template": seed.get("output_template"),
                "nodes": resolved_nodes,
                "edges": seed.get("edges", []),
                "trigger": {"type": "manual"},
                "settings": seed.get(
                    "settings",
                    {"timeout": 300, "on_failure": "notify", "retry_count": 0},
                ),
                "tags": seed.get("tags", []),
                "is_system": True,
                "enabled": True,
            })
            stats["created_workflows"] += 1
            logger.info(f"[TestSeed] 创建工作流: {code}")
        except Exception as exc:
            stats["failed"].append(f"workflow:{code}: {exc}")
            logger.exception(f"[TestSeed] 创建工作流失败 {code}")

    # ── Phase 4: Workflow-type Tool ────────────────────────────
    #  依赖 Phase 3 中 test_linear_chain 已创建
    try:
        if await db.tools.find_one({"code": "test_workflow_tool"}):
            stats["skipped_tools"] += 1
        else:
            wf = await workflow_service.get_workflow_by_code("test_linear_chain")
            if not wf:
                stats["failed"].append(
                    "tool:test_workflow_tool: test_linear_chain 工作流未创建"
                )
            else:
                await db.tools.insert_one({
                    "code": "test_workflow_tool",
                    "name": "[测试] 线性分析工作流工具",
                    "description": "将「线性工具链」工作流封装为工具，验证工作流工具嵌套",
                    "type": "workflow",
                    "workflow_id": wf["id"],
                    "output_format": "summary",
                    "parameters": [
                        {
                            "name": "ticker",
                            "type": "string",
                            "required": True,
                            "description": "股票代码",
                        },
                        {
                            "name": "current_date",
                            "type": "string",
                            "required": False,
                            "description": "日期 YYYY-MM-DD",
                        },
                    ],
                    "tags": ["测试", "工作流工具"],
                    "enabled": True,
                    "is_system": True,
                    "timeout": 300,
                    "health_status": "unknown",
                    "last_health_check": None,
                    "health_check_url": None,
                    "endpoint_url": None,
                    "endpoint_method": None,
                    "headers": None,
                    "auth_type": None,
                    "auth_config": None,
                    "output_schema": None,
                    "agent_count": 0,
                    "created_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow(),
                })
                stats["created_tools"] += 1
                logger.info("[TestSeed] 创建工作流工具: test_workflow_tool")
    except Exception as exc:
        stats["failed"].append(f"tool:test_workflow_tool: {exc}")
        logger.exception("[TestSeed] 创建工作流工具失败")

    # ── Summary ───────────────────────────────────────────────
    stats["total_prompts"] = len(TEST_PROMPT_SEEDS)
    stats["total_agents"] = len(TEST_AGENT_SEEDS)
    stats["total_workflows"] = len(TEST_WORKFLOW_SEEDS)
    return stats
