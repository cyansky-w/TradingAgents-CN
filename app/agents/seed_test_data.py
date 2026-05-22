"""
测试用工具 → 提示词 → Agent 的种子数据。

用于验证 Agent 管理的完整链路：提示词绑定工具、Agent 绑定提示词、运行时构建。
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List

from app.core.database import get_mongo_db

logger = logging.getLogger(__name__)

TEST_PROMPT_SEEDS: List[Dict[str, Any]] = [
    {
        "code": "test_market_agent_prompt",
        "name": "测试市场分析师提示词",
        "description": "测试提示词：模拟市场分析师角色，绑定行情快照和新闻工具",
        "prompt_type": "agent",
        "blocks": [
            {
                "type": "text",
                "content": (
                    "您是一位测试用的市场分析师 AI Agent。\n"
                    "当前分析日期：{{current_date}}，分析标的：{{ticker}}。\n"
                    "请使用提供的工具获取行情快照和新闻数据，然后给出简短的市场分析意见。\n"
                    "您可以访问以下工具：{{tool_names}}。\n"
                    "请用中文回复，保持简洁。"
                ),
            },
            {
                "type": "messages_placeholder",
                "label": "对话历史",
            },
        ],
        "bind_tools": ["test_market_snapshot_tool", "test_news_digest_tool"],
        "tags": ["测试", "市场"],
    },
    {
        "code": "test_risk_agent_prompt",
        "name": "测试风险分析师提示词",
        "description": "测试提示词：模拟风险分析师角色，绑定风险评分工具",
        "prompt_type": "agent",
        "blocks": [
            {
                "type": "text",
                "content": (
                    "您是一位测试用的风险分析师 AI Agent。\n"
                    "当前分析日期：{{current_date}}，分析标的：{{ticker}}。\n"
                    "请使用提供的工具获取风险评分数据，然后给出简短的风险评估意见。\n"
                    "您可以访问以下工具：{{tool_names}}。\n"
                    "请用中文回复，保持简洁。"
                ),
            },
            {
                "type": "messages_placeholder",
                "label": "对话历史",
            },
        ],
        "bind_tools": ["test_risk_score_tool"],
        "tags": ["测试", "风险"],
    },
    {
        "code": "test_fundamental_agent_prompt",
        "name": "测试基本面分析师提示词",
        "description": "测试提示词：模拟基本面分析师角色，绑定基本面指标工具",
        "prompt_type": "agent",
        "blocks": [
            {
                "type": "text",
                "content": (
                    "您是一位测试用的基本面分析师 AI Agent。\n"
                    "当前分析日期：{{current_date}}，分析标的：{{ticker}}。\n"
                    "请使用提供的工具获取基本面指标，然后给出简短的基本面分析意见。\n"
                    "您可以访问以下工具：{{tool_names}}。\n"
                    "请用中文回复，保持简洁。"
                ),
            },
            {
                "type": "messages_placeholder",
                "label": "对话历史",
            },
        ],
        "bind_tools": ["test_fundamental_metrics_tool"],
        "tags": ["测试", "基本面"],
    },
    {
        "code": "test_multi_tool_agent_prompt",
        "name": "测试多工具分析师提示词",
        "description": "测试提示词：综合角色，绑定所有测试工具",
        "prompt_type": "agent",
        "blocks": [
            {
                "type": "text",
                "content": (
                    "您是一位测试用的综合分析师 AI Agent。\n"
                    "当前分析日期：{{current_date}}，分析标的：{{ticker}}。\n"
                    "请使用提供的工具获取行情、新闻、风险和基本面数据，然后给出综合分析意见。\n"
                    "您可以访问以下工具：{{tool_names}}。\n"
                    "请用中文回复，先调用所有工具获取数据，再综合分析。"
                ),
            },
            {
                "type": "messages_placeholder",
                "label": "对话历史",
            },
        ],
        "bind_tools": [
            "test_market_snapshot_tool",
            "test_news_digest_tool",
            "test_risk_score_tool",
            "test_fundamental_metrics_tool",
        ],
        "tags": ["测试", "综合"],
    },
]

TEST_AGENT_SEEDS: List[Dict[str, Any]] = [
    {
        "code": "test_market_agent",
        "name": "测试市场分析师",
        "description": "测试 Agent：行情快照 + 新闻，验证工具绑定和多工具调用",
        "prompt_code": "test_market_agent_prompt",
        "message_template": "请分析 {{ticker}} 的最新市场行情和新闻动态。",
        "tags": ["测试", "市场"],
        "is_chat": True,
    },
    {
        "code": "test_risk_agent",
        "name": "测试风险分析师",
        "description": "测试 Agent：风险评分，验证单工具调用",
        "prompt_code": "test_risk_agent_prompt",
        "message_template": "请评估 {{ticker}} 的当前风险水平。",
        "tags": ["测试", "风险"],
        "is_chat": True,
    },
    {
        "code": "test_fundamental_agent",
        "name": "测试基本面分析师",
        "description": "测试 Agent：基本面指标，验证单工具调用",
        "prompt_code": "test_fundamental_agent_prompt",
        "message_template": "请分析 {{ticker}} 的基本面数据。",
        "tags": ["测试", "基本面"],
        "is_chat": True,
    },
    {
        "code": "test_multi_tool_agent",
        "name": "测试综合分析师",
        "description": "测试 Agent：所有测试工具，验证多工具并行调用",
        "prompt_code": "test_multi_tool_agent_prompt",
        "message_template": "请对 {{ticker}} 进行全面的行情、新闻、风险和基本面综合分析。",
        "tags": ["测试", "综合"],
        "is_chat": True,
    },
]


async def seed_test_data() -> Dict[str, Any]:
    db = get_mongo_db()
    now = datetime.utcnow()

    created_prompts = 0
    skipped_prompts = 0
    created_agents = 0
    skipped_agents = 0
    failed: List[str] = []

    # 1. Seed prompts
    for seed in TEST_PROMPT_SEEDS:
        code = seed["code"]
        try:
            existing = await db.prompts.find_one({"code": code})
            if existing:
                skipped_prompts += 1
                logger.info(f"[TestSeed] 跳过已存在的提示词: {code}")
                continue
            doc = {
                "code": code,
                "name": seed["name"],
                "description": seed.get("description", ""),
                "prompt_type": seed.get("prompt_type", "agent"),
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
            }
            await db.prompts.insert_one(doc)
            created_prompts += 1
            logger.info(f"[TestSeed] 已创建提示词: {code}")
        except Exception as exc:
            failed.append(f"prompt:{code}: {exc}")
            logger.exception(f"[TestSeed] 创建提示词失败 {code}")

    # 2. Seed agents
    from app.services.agent_service import agent_service

    for seed in TEST_AGENT_SEEDS:
        code = seed["code"]
        try:
            existing = await agent_service.get_agent_by_code(code)
            if existing:
                skipped_agents += 1
                logger.info(f"[TestSeed] 跳过已存在的 Agent: {code}")
                continue

            prompt = await db.prompts.find_one({"code": seed["prompt_code"], "enabled": True})
            if not prompt:
                failed.append(f"agent:{code}: 提示词 '{seed['prompt_code']}' 不存在或未启用")
                continue

            await agent_service.create_agent({
                "code": code,
                "name": seed["name"],
                "description": seed.get("description", ""),
                "prompt_id": str(prompt["_id"]),
                "message_template": seed.get("message_template", ""),
                "tags": seed.get("tags", []),
                "is_chat": seed.get("is_chat", True),
                "is_system": True,
                "enabled": True,
            })
            created_agents += 1
            logger.info(f"[TestSeed] 已创建 Agent: {code}")
        except Exception as exc:
            failed.append(f"agent:{code}: {exc}")
            logger.exception(f"[TestSeed] 创建 Agent 失败 {code}")

    return {
        "created_prompts": created_prompts,
        "skipped_prompts": skipped_prompts,
        "created_agents": created_agents,
        "skipped_agents": skipped_agents,
        "failed": failed,
        "total_prompts": len(TEST_PROMPT_SEEDS),
        "total_agents": len(TEST_AGENT_SEEDS),
    }
