"""
工作流种子数据。

策略：按 code 查询 — 存在则跳过，不存在则插入并标记 is_system=True。
agent_id 通过运行时按 agent code 解析得到，不硬编码 ObjectId。
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List

from app.services.workflow_service import workflow_service

logger = logging.getLogger(__name__)

WORKFLOW_SEEDS: List[Dict[str, Any]] = [
    # ── 每日复盘工作流 ──────────────────────────────────────────
    {
        "code": "daily_market_review",
        "name": "每日复盘工作流",
        "description": "盘后自动执行全链路复盘：市场分析 → 基本面分析 → 新闻分析 → 投研总结",
        "version": 1,
        "trigger": {"type": "cron", "cron": "0 20 * * 1-5"},
        "message_template": "请对 {{date}} 的市场进行复盘分析，重点关注以下标的：{{symbols}}",
        "output_template": "{{summary.output}}",
        "nodes": [
            {"id": "start", "type": "io", "label": "开始", "config": {"io_direction": "input"}},
            {"id": "market", "type": "agent", "label": "市场分析", "config": {
                "agent_code": "market_analyst",
                "input_mapping": {"date": "{{input.date}}", "ticker": "{{input.symbols}}"},
            }},
            {"id": "fundamentals", "type": "agent", "label": "基本面分析", "config": {
                "agent_code": "fundamentals_analyst",
                "input_mapping": {"date": "{{input.date}}", "ticker": "{{input.symbols}}"},
            }},
            {"id": "news", "type": "agent", "label": "新闻分析", "config": {
                "agent_code": "news_analyst",
                "input_mapping": {"date": "{{input.date}}", "ticker": "{{input.symbols}}"},
            }},
            {"id": "summary", "type": "agent", "label": "投研总结", "config": {
                "agent_code": "research_manager",
                "input_mapping": {
                    "market_report": "{{market.output}}",
                    "fundamentals_report": "{{fundamentals.output}}",
                    "news_report": "{{news.output}}",
                },
            }},
            {"id": "end", "type": "io", "label": "结束", "config": {"io_direction": "output"}},
        ],
        "edges": [
            {"id": "e1", "source": "start", "target": "market"},
            {"id": "e2", "source": "start", "target": "fundamentals"},
            {"id": "e3", "source": "start", "target": "news"},
            {"id": "e4", "source": "market", "target": "summary"},
            {"id": "e5", "source": "fundamentals", "target": "summary"},
            {"id": "e6", "source": "news", "target": "summary"},
            {"id": "e7", "source": "summary", "target": "end"},
        ],
        "settings": {"timeout": 3600, "on_failure": "notify", "retry_count": 1},
        "tags": ["复盘", "系统"],
    },
    # ── 多空辩论工作流 ──────────────────────────────────────────
    {
        "code": "bull_bear_debate",
        "name": "多空辩论工作流",
        "description": "多空辩论：看涨研究员与看跌研究员各自论证，投研经理综合评估",
        "version": 1,
        "trigger": {"type": "manual"},
        "message_template": "请对 {{ticker}} 进行多空辩论分析",
        "output_template": "{{decision.output}}",
        "nodes": [
            {"id": "start", "type": "io", "label": "开始", "config": {"io_direction": "input"}},
            {"id": "bull", "type": "agent", "label": "看涨论证", "config": {
                "agent_code": "bull_researcher",
                "input_mapping": {"ticker": "{{input.ticker}}"},
            }},
            {"id": "bear", "type": "agent", "label": "看跌论证", "config": {
                "agent_code": "bear_researcher",
                "input_mapping": {"ticker": "{{input.ticker}}"},
            }},
            {"id": "decision", "type": "agent", "label": "投研决策", "config": {
                "agent_code": "research_manager",
                "input_mapping": {
                    "bull_argument": "{{bull.output}}",
                    "bear_argument": "{{bear.output}}",
                },
            }},
            {"id": "end", "type": "io", "label": "结束", "config": {"io_direction": "output"}},
        ],
        "edges": [
            {"id": "e1", "source": "start", "target": "bull"},
            {"id": "e2", "source": "start", "target": "bear"},
            {"id": "e3", "source": "bull", "target": "decision"},
            {"id": "e4", "source": "bear", "target": "decision"},
            {"id": "e5", "source": "decision", "target": "end"},
        ],
        "settings": {"timeout": 1800, "on_failure": "notify", "retry_count": 0},
        "tags": ["辩论", "系统"],
    },
    # ── 风险评估工作流 ──────────────────────────────────────────
    {
        "code": "risk_assessment",
        "name": "风险评估工作流",
        "description": "三方风险辩论：激进/保守/中性分析师各自评估，风险经理综合决策",
        "version": 1,
        "trigger": {"type": "manual"},
        "message_template": "请评估 {{ticker}} 的投资风险",
        "output_template": "{{risk_decision.output}}",
        "nodes": [
            {"id": "start", "type": "io", "label": "开始", "config": {"io_direction": "input"}},
            {"id": "aggressive", "type": "agent", "label": "激进评估", "config": {
                "agent_code": "aggressive_debator",
                "input_mapping": {"ticker": "{{input.ticker}}"},
            }},
            {"id": "conservative", "type": "agent", "label": "保守评估", "config": {
                "agent_code": "conservative_debator",
                "input_mapping": {"ticker": "{{input.ticker}}"},
            }},
            {"id": "neutral", "type": "agent", "label": "中性评估", "config": {
                "agent_code": "neutral_debator",
                "input_mapping": {"ticker": "{{input.ticker}}"},
            }},
            {"id": "risk_decision", "type": "agent", "label": "风险决策", "config": {
                "agent_code": "risk_manager",
                "input_mapping": {
                    "aggressive_view": "{{aggressive.output}}",
                    "conservative_view": "{{conservative.output}}",
                    "neutral_view": "{{neutral.output}}",
                },
            }},
            {"id": "end", "type": "io", "label": "结束", "config": {"io_direction": "output"}},
        ],
        "edges": [
            {"id": "e1", "source": "start", "target": "aggressive"},
            {"id": "e2", "source": "start", "target": "conservative"},
            {"id": "e3", "source": "start", "target": "neutral"},
            {"id": "e4", "source": "aggressive", "target": "risk_decision"},
            {"id": "e5", "source": "conservative", "target": "risk_decision"},
            {"id": "e6", "source": "neutral", "target": "risk_decision"},
            {"id": "e7", "source": "risk_decision", "target": "end"},
        ],
        "settings": {"timeout": 1800, "on_failure": "notify", "retry_count": 0},
        "tags": ["风险", "系统"],
    },
    # ── 综合分析工作流 ──────────────────────────────────────────
    {
        "code": "comprehensive_analysis",
        "name": "综合分析工作流",
        "description": "完整投资分析流程：市场分析 + 多空辩论 → 风险评估 → 交易决策",
        "version": 1,
        "trigger": {"type": "manual"},
        "message_template": "请对 {{ticker}} 进行全面综合分析，输出交易建议",
        "output_template": "{{trade_decision.output}}",
        "nodes": [
            {"id": "start", "type": "io", "label": "开始", "config": {"io_direction": "input"}},
            {"id": "market", "type": "agent", "label": "市场分析", "config": {
                "agent_code": "market_analyst",
                "input_mapping": {"ticker": "{{input.ticker}}"},
            }},
            {"id": "bull", "type": "agent", "label": "看涨论证", "config": {
                "agent_code": "bull_researcher",
                "input_mapping": {"ticker": "{{input.ticker}}"},
            }},
            {"id": "bear", "type": "agent", "label": "看跌论证", "config": {
                "agent_code": "bear_researcher",
                "input_mapping": {"ticker": "{{input.ticker}}"},
            }},
            {"id": "research", "type": "agent", "label": "投研总结", "config": {
                "agent_code": "research_manager",
                "input_mapping": {
                    "market_report": "{{market.output}}",
                    "bull_argument": "{{bull.output}}",
                    "bear_argument": "{{bear.output}}",
                },
            }},
            {"id": "risk", "type": "agent", "label": "风险评估", "config": {
                "agent_code": "risk_manager",
                "input_mapping": {"research_summary": "{{research.output}}"},
            }},
            {"id": "trade_decision", "type": "agent", "label": "交易决策", "config": {
                "agent_code": "trader",
                "input_mapping": {
                    "research_summary": "{{research.output}}",
                    "risk_assessment": "{{risk.output}}",
                },
            }},
            {"id": "end", "type": "io", "label": "结束", "config": {"io_direction": "output"}},
        ],
        "edges": [
            {"id": "e1", "source": "start", "target": "market"},
            {"id": "e2", "source": "start", "target": "bull"},
            {"id": "e3", "source": "start", "target": "bear"},
            {"id": "e4", "source": "market", "target": "research"},
            {"id": "e5", "source": "bull", "target": "research"},
            {"id": "e6", "source": "bear", "target": "research"},
            {"id": "e7", "source": "research", "target": "risk"},
            {"id": "e8", "source": "risk", "target": "trade_decision"},
            {"id": "e9", "source": "trade_decision", "target": "end"},
        ],
        "settings": {"timeout": 3600, "on_failure": "notify", "retry_count": 1},
        "tags": ["综合", "系统"],
    },
    # ── A股扫描工作流 ──────────────────────────────────────────
    {
        "code": "a_share_screener",
        "name": "A股筛选工作流",
        "description": "从A股市场筛选股票，再对筛选结果逐一分析",
        "version": 1,
        "trigger": {"type": "manual"},
        "message_template": "请从A股市场筛选具有投资价值的股票并分析",
        "output_template": "{{analysis.output}}",
        "nodes": [
            {"id": "start", "type": "io", "label": "开始", "config": {"io_direction": "input"}},
            {"id": "screen", "type": "agent", "label": "A股筛选", "config": {
                "agent_code": "china_stock_screener",
                "input_mapping": {"metrics": "{{input.metrics}}"},
            }},
            {"id": "analysis", "type": "agent", "label": "中国市场分析", "config": {
                "agent_code": "china_market_analyst",
                "input_mapping": {"screener_result": "{{screen.output}}"},
            }},
            {"id": "end", "type": "io", "label": "结束", "config": {"io_direction": "output"}},
        ],
        "edges": [
            {"id": "e1", "source": "start", "target": "screen"},
            {"id": "e2", "source": "screen", "target": "analysis"},
            {"id": "e3", "source": "analysis", "target": "end"},
        ],
        "settings": {"timeout": 1800, "on_failure": "notify", "retry_count": 0},
        "tags": ["A股", "筛选", "系统"],
    },
    # ── 加密货币分析工作流 ──────────────────────────────────────────
    {
        "code": "crypto_analysis",
        "name": "加密货币分析工作流",
        "description": "完整加密货币分析：行情分析 + 基本面 + 新闻 + 跨交易所比价 → 投研总结",
        "version": 1,
        "trigger": {"type": "manual"},
        "message_template": "请对 {{ticker}} 进行加密货币全面分析（交易所：{{exchange}}）",
        "output_template": "{{summary.output}}",
        "nodes": [
            {"id": "start", "type": "io", "label": "开始", "config": {"io_direction": "input"}},
            {"id": "market", "type": "agent", "label": "行情分析", "config": {
                "agent_code": "crypto_market_analyst",
                "input_mapping": {"ticker": "{{input.ticker}}"},
            }},
            {"id": "fundamentals", "type": "agent", "label": "基本面分析", "config": {
                "agent_code": "fundamentals_analyst",
                "input_mapping": {"ticker": "{{input.ticker}}"},
            }},
            {"id": "news", "type": "agent", "label": "新闻分析", "config": {
                "agent_code": "news_analyst",
                "input_mapping": {"ticker": "{{input.ticker}}"},
            }},
            {"id": "summary", "type": "agent", "label": "投研总结", "config": {
                "agent_code": "research_manager",
                "input_mapping": {
                    "market_report": "{{market.output}}",
                    "fundamentals_report": "{{fundamentals.output}}",
                    "news_report": "{{news.output}}",
                },
            }},
            {"id": "end", "type": "io", "label": "结束", "config": {"io_direction": "output"}},
        ],
        "edges": [
            {"id": "e1", "source": "start", "target": "market"},
            {"id": "e2", "source": "start", "target": "fundamentals"},
            {"id": "e3", "source": "start", "target": "news"},
            {"id": "e4", "source": "market", "target": "summary"},
            {"id": "e5", "source": "fundamentals", "target": "summary"},
            {"id": "e6", "source": "news", "target": "summary"},
            {"id": "e7", "source": "summary", "target": "end"},
        ],
        "settings": {"timeout": 1800, "on_failure": "notify", "retry_count": 0},
        "tags": ["加密货币", "系统"],
    },
]


async def seed_workflows_to_db() -> Dict[str, Any]:
    """Seed system workflows. Resolves agent_code -> agent_id at runtime."""
    from app.services.agent_service import agent_service

    created = 0
    skipped = 0
    failed: List[str] = []

    for seed in WORKFLOW_SEEDS:
        code = seed["code"]
        try:
            existing = await workflow_service.get_workflow_by_code(code)
            if existing:
                skipped += 1
                logger.info(f"[SeedWF] 跳过已存在的工作流: {code}")
                continue

            # Resolve agent_code -> agent_id in node configs
            nodes = seed.get("nodes", [])
            resolved_nodes = []
            for node in nodes:
                node_copy = dict(node)
                config = dict(node_copy.get("config", {}))
                if "agent_code" in config:
                    agent_code = config.pop("agent_code")
                    agent = await agent_service.get_agent_by_code(agent_code)
                    if not agent:
                        raise ValueError(f"Agent '{agent_code}' 不存在，跳过工作流 '{code}'")
                    config["agent_id"] = agent["id"]
                node_copy["config"] = config
                resolved_nodes.append(node_copy)

            now = datetime.utcnow()
            data = {
                "code": code,
                "name": seed["name"],
                "description": seed.get("description", ""),
                "version": seed.get("version", 1),
                "trigger": seed.get("trigger", {"type": "manual"}),
                "message_template": seed.get("message_template", ""),
                "output_template": seed.get("output_template"),
                "nodes": resolved_nodes,
                "edges": seed.get("edges", []),
                "settings": seed.get(
                    "settings",
                    {"timeout": 3600, "on_failure": "notify", "retry_count": 0},
                ),
                "tags": seed.get("tags", []),
                "enabled": seed.get("enabled", True),
                "is_system": True,
                "usage_count": 0,
                "last_used_at": None,
                "created_at": now,
                "updated_at": now,
            }
            await workflow_service.create_workflow(data)
            created += 1
            logger.info(f"[SeedWF] 已创建工作流: {code}")
        except Exception as exc:
            failed.append(f"{code}: {exc}")
            logger.exception(f"[SeedWF] 创建工作流失败 {code}")

    return {
        "created": created,
        "skipped": skipped,
        "failed": failed,
        "total": len(WORKFLOW_SEEDS),
    }
