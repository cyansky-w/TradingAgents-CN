"""
Agent 种子数据。

策略：按 code 查询 — 存在则跳过，不存在则插入并标记 is_system=True。
prompt_id 通过运行时按 prompt_code 解析得到，不硬编码。
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

from app.services.agent_service import agent_service
from app.services.prompt_service import prompt_service

logger = logging.getLogger(__name__)


AGENT_SEEDS: List[Dict[str, Any]] = [
    # ── 分析师组 ──────────────────────────────────────────────
    {
        "code": "market_analyst",
        "name": "市场分析师",
        "description": "分析市场整体走势、技术指标和价格趋势",
        "prompt_code": "market_analyst_system",
        "tags": ["分析", "技术面", "市场"],
        "is_chat": False,
    },
    {
        "code": "news_analyst",
        "name": "新闻分析师",
        "description": "分析新闻事件和宏观信息对标的的影响",
        "prompt_code": "news_analyst_system",
        "tags": ["分析", "新闻", "舆情"],
        "is_chat": False,
    },
    {
        "code": "social_media_analyst",
        "name": "社交媒体情绪分析师",
        "description": "分析散户与机构观点差异及社交媒体情绪变化",
        "prompt_code": "social_media_analyst_system",
        "tags": ["分析", "情绪", "社交媒体"],
        "is_chat": False,
    },
    {
        "code": "fundamentals_analyst",
        "name": "基本面分析师",
        "description": "分析财务报表、估值指标和公司基本面",
        "prompt_code": "fundamentals_analyst_system",
        "tags": ["分析", "基本面", "估值"],
        "is_chat": False,
    },
    {
        "code": "china_market_analyst",
        "name": "中国市场分析师",
        "description": "专门分析 A 股、港股等中国资本市场",
        "prompt_code": "china_market_analyst_system",
        "tags": ["分析", "中国市场", "A股"],
        "is_chat": False,
    },
    {
        "code": "china_stock_screener",
        "name": "中国股票筛选器",
        "description": "从 A 股市场中筛选具有投资价值的股票",
        "prompt_code": "china_stock_screener_system",
        "tags": ["筛选", "中国市场", "A股"],
        "is_chat": False,
    },
    # ── 研究员组（多空辩论） ────────────────────────────────────
    {
        "code": "bull_researcher",
        "name": "看涨研究员",
        "description": "多头研究员，为投资建立看涨论证",
        "prompt_code": "bull_researcher_system",
        "tags": ["研究员", "多头", "辩论"],
        "is_chat": False,
    },
    {
        "code": "bear_researcher",
        "name": "看跌研究员",
        "description": "空头研究员，论证不投资的风险和理由",
        "prompt_code": "bear_researcher_system",
        "tags": ["研究员", "空头", "辩论"],
        "is_chat": False,
    },
    {
        "code": "research_manager",
        "name": "投研经理",
        "description": "评估多空辩论，制定投资计划与目标价位",
        "prompt_code": "research_manager_system",
        "tags": ["管理", "决策", "投研"],
        "is_chat": False,
    },
    # ── 风险管理组（三方辩论） ──────────────────────────────────
    {
        "code": "aggressive_debator",
        "name": "激进风险分析师",
        "description": "倡导高回报、高风险的投资机会",
        "prompt_code": "aggressive_debator_system",
        "tags": ["风险", "激进", "辩论"],
        "is_chat": False,
    },
    {
        "code": "conservative_debator",
        "name": "保守风险分析师",
        "description": "优先保护资产，最小化波动性",
        "prompt_code": "conservative_debator_system",
        "tags": ["风险", "保守", "辩论"],
        "is_chat": False,
    },
    {
        "code": "neutral_debator",
        "name": "中性风险分析师",
        "description": "提供平衡视角，权衡收益与风险",
        "prompt_code": "neutral_debator_system",
        "tags": ["风险", "中性", "辩论"],
        "is_chat": False,
    },
    {
        "code": "risk_manager",
        "name": "风险经理",
        "description": "评估三方风险辩论，做出最终风险决策",
        "prompt_code": "risk_manager_system",
        "tags": ["管理", "风险", "决策"],
        "is_chat": False,
    },
    # ── 交易执行 ──────────────────────────────────────────────
    {
        "code": "trader",
        "name": "交易员",
        "description": "综合所有分析输出具体买卖决策与目标价位",
        "prompt_code": "trader_system",
        "tags": ["交易", "决策", "执行"],
        "is_chat": False,
    },
]


async def seed_agents_to_db() -> Dict[str, Any]:
    created = 0
    skipped = 0
    failed: List[str] = []

    for seed in AGENT_SEEDS:
        code = seed["code"]
        try:
            existing = await agent_service.get_agent_by_code(code)
            if existing:
                skipped += 1
                logger.info(f"[Seed] 跳过已存在的 Agent: {code}")
                continue

            prompt = await prompt_service.get_active_prompt(seed["prompt_code"])
            if not prompt or not prompt.get("enabled", True):
                msg = f"{code}: 提示词 '{seed['prompt_code']}' 不存在或未启用"
                failed.append(msg)
                logger.warning(f"[Seed] {msg}")
                continue

            await agent_service.create_agent({
                "code": code,
                "name": seed["name"],
                "description": seed.get("description", ""),
                "prompt_id": prompt["id"],
                "tags": seed.get("tags", []),
                "is_chat": seed.get("is_chat", False),
                "is_system": True,
                "enabled": True,
            })
            created += 1
            logger.info(f"[Seed] 已创建 Agent: {code}")
        except Exception as exc:  # noqa: BLE001
            failed.append(f"{code}: {exc}")
            logger.exception(f"[Seed] 创建 Agent 失败 {code}")

    return {
        "created": created,
        "skipped": skipped,
        "failed": failed,
        "total": len(AGENT_SEEDS),
    }
