"""
Handler Map: handler name string -> Python callable mapping.
"""

import logging
from typing import Any, Callable, Dict, List

logger = logging.getLogger(__name__)

HANDLER_MAP: Dict[str, Callable] = {}


def _build_handler_map() -> Dict[str, Callable]:
    handlers: Dict[str, Callable] = {}
    try:
        from tradingagents.agents.utils.agent_utils import Toolkit
        toolkit = Toolkit()
        # Method 1: detect @tool decorated methods via .name attribute
        for attr_name in dir(toolkit):
            if attr_name.startswith('_'):
                continue
            method = getattr(toolkit, attr_name)
            if not callable(method):
                continue
            if hasattr(method, "name"):
                handlers[method.name] = method
        # Method 2: fallback for @staticmethod + @tool where .name isn't on instance access
        cls_dict = type(toolkit).__dict__
        for attr_name, cls_attr in cls_dict.items():
            if attr_name.startswith('_') or attr_name in handlers:
                continue
            if isinstance(cls_attr, staticmethod):
                fn = cls_attr.__func__
                if hasattr(fn, "name"):
                    handlers[fn.name] = getattr(toolkit, attr_name)
    except Exception as e:
        logger.warning(f"Failed to extract Toolkit handlers: {e}")
    try:
        from app.chat.tool_registry import ToolRegistry
        temp_registry = ToolRegistry()
        from app.chat.builtin_tools import register_builtin_tools
        register_builtin_tools(temp_registry)
        for tool_info in temp_registry.list_tools():
            tool_func = temp_registry.get(tool_info["name"])
            if tool_func:
                handlers[tool_info["name"]] = tool_func
    except Exception as e:
        logger.warning(f"Failed to extract chat builtin handlers: {e}")
    logger.info(f"Built handler map with {len(handlers)} handlers")
    return handlers


HANDLER_MAP = _build_handler_map()

TOOL_DEFINITIONS: List[Dict[str, Any]] = [
    {"code": "get_reddit_news", "name": "get_reddit_news", "description": "Retrieve global news from Reddit within a specified time frame.", "type": "builtin", "handler": "get_reddit_news", "tags": ["news", "数据"], "is_system": True, "parameters": [{"name": "curr_date", "type": "string", "required": True, "description": "Date in yyyy-mm-dd format"}]},
    {"code": "get_finnhub_news", "name": "get_finnhub_news", "description": "Retrieve the latest news about a given stock from Finnhub within a date range.", "type": "builtin", "handler": "get_finnhub_news", "tags": ["news", "数据"], "is_system": True, "parameters": [{"name": "ticker", "type": "string", "required": True, "description": "Ticker of a company, e.g. AAPL, TSM"}, {"name": "start_date", "type": "string", "required": True, "description": "Start date in yyyy-mm-dd format"}, {"name": "end_date", "type": "string", "required": True, "description": "End date in yyyy-mm-dd format"}]},
    {"code": "get_reddit_stock_info", "name": "get_reddit_stock_info", "description": "Retrieve latest news about a given stock from Reddit.", "type": "builtin", "handler": "get_reddit_stock_info", "tags": ["news", "数据"], "is_system": True, "parameters": [{"name": "ticker", "type": "string", "required": True, "description": "Ticker of a company, e.g. AAPL, TSM"}, {"name": "curr_date", "type": "string", "required": True, "description": "Current date in yyyy-mm-dd format"}]},
    {"code": "get_chinese_social_sentiment", "name": "get_chinese_social_sentiment", "description": "Analyze Chinese investor sentiment from social media for a given stock.", "type": "builtin", "handler": "get_chinese_social_sentiment", "tags": ["news", "情绪"], "is_system": True, "parameters": [{"name": "ticker", "type": "string", "required": True, "description": "Ticker of a company. e.g. AAPL, TSM"}, {"name": "curr_date", "type": "string", "required": True, "description": "Current date in yyyy-mm-dd format"}]},
    {"code": "get_google_news", "name": "get_google_news", "description": "Retrieve the latest news from Google News based on query and date range.", "type": "builtin", "handler": "get_google_news", "tags": ["news", "数据"], "is_system": True, "parameters": [{"name": "query", "type": "string", "required": True, "description": "Query to search with"}, {"name": "curr_date", "type": "string", "required": True, "description": "Current date in yyyy-mm-dd format"}]},
    {"code": "get_realtime_stock_news", "name": "get_realtime_stock_news", "description": "Retrieve real-time news analysis for a given stock.", "type": "builtin", "handler": "get_realtime_stock_news", "tags": ["news", "数据"], "is_system": True, "parameters": [{"name": "ticker", "type": "string", "required": True, "description": "Ticker of a company. e.g. AAPL, TSM"}, {"name": "curr_date", "type": "string", "required": True, "description": "Current date in yyyy-mm-dd format"}]},
    {"code": "get_stock_news_openai", "name": "get_stock_news_openai", "description": "Retrieve the latest news about a company using OpenAI.", "type": "builtin", "handler": "get_stock_news_openai", "tags": ["news", "AI"], "is_system": True, "parameters": [{"name": "ticker", "type": "string", "required": True, "description": "Ticker of a company"}, {"name": "curr_date", "type": "string", "required": True, "description": "Current date in yyyy-mm-dd format"}]},
    {"code": "get_global_news_openai", "name": "get_global_news_openai", "description": "Retrieve the latest macroeconomic news using OpenAI.", "type": "builtin", "handler": "get_global_news_openai", "tags": ["news", "AI"], "is_system": True, "parameters": [{"name": "curr_date", "type": "string", "required": True, "description": "Current date in yyyy-mm-dd format"}]},
    {"code": "get_stock_news_unified", "name": "get_stock_news_unified", "description": "Unified stock news retrieval supporting A-share, HK, and US markets.", "type": "builtin", "handler": "get_stock_news_unified", "tags": ["news", "统一接口"], "is_system": True, "parameters": [{"name": "ticker", "type": "string", "required": True, "description": "股票代码（支持A股、港股、美股）"}, {"name": "curr_date", "type": "string", "required": True, "description": "当前日期，格式：YYYY-MM-DD"}]},
    {"code": "get_YFin_data", "name": "get_YFin_data", "description": "Retrieve stock price data from Yahoo Finance for a given date range.", "type": "builtin", "handler": "get_YFin_data", "tags": ["market_data", "行情"], "is_system": True, "parameters": [{"name": "symbol", "type": "string", "required": True, "description": "Ticker symbol, e.g. AAPL, TSM"}, {"name": "start_date", "type": "string", "required": True, "description": "Start date in yyyy-mm-dd format"}, {"name": "end_date", "type": "string", "required": True, "description": "End date in yyyy-mm-dd format"}]},
    {"code": "get_YFin_data_online", "name": "get_YFin_data_online", "description": "Retrieve stock price data from Yahoo Finance (online mode).", "type": "builtin", "handler": "get_YFin_data_online", "tags": ["market_data", "行情"], "is_system": True, "parameters": [{"name": "symbol", "type": "string", "required": True, "description": "Ticker symbol, e.g. AAPL, TSM"}, {"name": "start_date", "type": "string", "required": True, "description": "Start date in yyyy-mm-dd format"}, {"name": "end_date", "type": "string", "required": True, "description": "End date in yyyy-mm-dd format"}]},
    {"code": "get_stockstats_indicators_report", "name": "get_stockstats_indicators_report", "description": "Generate a technical indicator analysis report using stockstats.", "type": "builtin", "handler": "get_stockstats_indicators_report", "tags": ["market_data", "技术指标"], "is_system": True, "parameters": [{"name": "symbol", "type": "string", "required": True, "description": "Ticker symbol"}, {"name": "indicator", "type": "string", "required": True, "description": "Technical indicator name"}, {"name": "curr_date", "type": "string", "required": True, "description": "Current trading date, YYYY-mm-dd"}, {"name": "look_back_days", "type": "integer", "required": False, "default": 30, "description": "How many days to look back"}]},
    {"code": "get_stockstats_indicators_report_online", "name": "get_stockstats_indicators_report_online", "description": "Generate a technical indicator analysis report (online mode).", "type": "builtin", "handler": "get_stockstats_indicators_report_online", "tags": ["market_data", "技术指标"], "is_system": True, "parameters": [{"name": "symbol", "type": "string", "required": True, "description": "Ticker symbol"}, {"name": "indicator", "type": "string", "required": True, "description": "Technical indicator name"}, {"name": "curr_date", "type": "string", "required": True, "description": "Current trading date, YYYY-mm-dd"}, {"name": "look_back_days", "type": "integer", "required": False, "default": 30, "description": "How many days to look back"}]},
    {"code": "get_china_market_overview", "name": "get_china_market_overview", "description": "Get China A-share market overview with major indices.", "type": "builtin", "handler": "get_china_market_overview", "tags": ["market_data", "A股"], "is_system": True, "parameters": [{"name": "curr_date", "type": "string", "required": True, "description": "当前日期，格式 yyyy-mm-dd"}]},
    {"code": "get_stock_market_data_unified", "name": "get_stock_market_data_unified", "description": "Unified stock market data retrieval supporting A-share, HK, and US markets.", "type": "builtin", "handler": "get_stock_market_data_unified", "tags": ["market_data", "统一接口"], "is_system": True, "parameters": [{"name": "ticker", "type": "string", "required": True, "description": "股票代码（支持A股、港股、美股）"}, {"name": "start_date", "type": "string", "required": True, "description": "开始日期，格式：YYYY-MM-DD"}, {"name": "end_date", "type": "string", "required": True, "description": "结束日期，格式：YYYY-MM-DD"}]},
    {"code": "get_finnhub_company_insider_sentiment", "name": "get_finnhub_company_insider_sentiment", "description": "Retrieve insider sentiment data for a company from Finnhub.", "type": "builtin", "handler": "get_finnhub_company_insider_sentiment", "tags": ["fundamentals", "数据"], "is_system": True, "parameters": [{"name": "ticker", "type": "string", "required": True, "description": "Ticker symbol for the company"}, {"name": "curr_date", "type": "string", "required": True, "description": "Current date, yyyy-mm-dd"}]},
    {"code": "get_finnhub_company_insider_transactions", "name": "get_finnhub_company_insider_transactions", "description": "Retrieve insider transaction data for a company from Finnhub.", "type": "builtin", "handler": "get_finnhub_company_insider_transactions", "tags": ["fundamentals", "数据"], "is_system": True, "parameters": [{"name": "ticker", "type": "string", "required": True, "description": "Ticker symbol"}, {"name": "curr_date", "type": "string", "required": True, "description": "Current date, yyyy-mm-dd"}]},
    {"code": "get_simfin_balance_sheet", "name": "get_simfin_balance_sheet", "description": "Retrieve the most recent balance sheet for a company.", "type": "builtin", "handler": "get_simfin_balance_sheet", "tags": ["fundamentals", "财务"], "is_system": True, "parameters": [{"name": "ticker", "type": "string", "required": True, "description": "Ticker symbol"}, {"name": "freq", "type": "string", "required": True, "description": "Reporting frequency: annual/quarterly"}, {"name": "curr_date", "type": "string", "required": True, "description": "Current date, yyyy-mm-dd"}]},
    {"code": "get_simfin_cashflow", "name": "get_simfin_cashflow", "description": "Retrieve the most recent cash flow statement for a company.", "type": "builtin", "handler": "get_simfin_cashflow", "tags": ["fundamentals", "财务"], "is_system": True, "parameters": [{"name": "ticker", "type": "string", "required": True, "description": "Ticker symbol"}, {"name": "freq", "type": "string", "required": True, "description": "Reporting frequency: annual/quarterly"}, {"name": "curr_date", "type": "string", "required": True, "description": "Current date, yyyy-mm-dd"}]},
    {"code": "get_simfin_income_stmt", "name": "get_simfin_income_stmt", "description": "Retrieve the most recent income statement for a company.", "type": "builtin", "handler": "get_simfin_income_stmt", "tags": ["fundamentals", "财务"], "is_system": True, "parameters": [{"name": "ticker", "type": "string", "required": True, "description": "Ticker symbol"}, {"name": "freq", "type": "string", "required": True, "description": "Reporting frequency: annual/quarterly"}, {"name": "curr_date", "type": "string", "required": True, "description": "Current date, yyyy-mm-dd"}]},
    {"code": "get_stock_fundamentals_unified", "name": "get_stock_fundamentals_unified", "description": "Unified stock fundamentals retrieval supporting A-share, HK, and US markets.", "type": "builtin", "handler": "get_stock_fundamentals_unified", "tags": ["fundamentals", "统一接口"], "is_system": True, "parameters": [{"name": "ticker", "type": "string", "required": True, "description": "股票代码（支持A股、港股、美股）"}, {"name": "start_date", "type": "string", "required": False, "default": None, "description": "开始日期，格式：YYYY-MM-DD"}, {"name": "end_date", "type": "string", "required": False, "default": None, "description": "结束日期，格式：YYYY-MM-DD"}, {"name": "curr_date", "type": "string", "required": False, "default": None, "description": "当前日期，格式：YYYY-MM-DD"}]},
    {"code": "get_stock_sentiment_unified", "name": "get_stock_sentiment_unified", "description": "Unified stock sentiment analysis supporting A-share, HK, and US markets.", "type": "builtin", "handler": "get_stock_sentiment_unified", "tags": ["sentiment", "统一接口"], "is_system": True, "parameters": [{"name": "ticker", "type": "string", "required": True, "description": "股票代码（支持A股、港股、美股）"}, {"name": "curr_date", "type": "string", "required": True, "description": "当前日期，格式：YYYY-MM-DD"}]},
    {"code": "calculator", "name": "calculator", "description": "Evaluate a mathematical expression. Supports +, -, *, /, **, %, sqrt, sin, cos, tan, log, abs, pi, e.", "type": "builtin", "handler": "calculator", "tags": ["utility"], "is_system": True, "parameters": [{"name": "expression", "type": "string", "required": True, "description": "A math expression to evaluate"}]},
    {"code": "get_current_time", "name": "get_current_time", "description": "Get the current date and time for a given timezone.", "type": "builtin", "handler": "get_current_time", "tags": ["utility"], "is_system": True, "parameters": [{"name": "timezone_offset", "type": "string", "required": False, "default": "UTC", "description": "Timezone name, e.g. UTC, Asia/Shanghai"}]},
]


async def seed_tools_to_db() -> dict:
    from app.core.database import get_mongo_db
    db = get_mongo_db()
    collection = db["tools"]

    # Drop old indexes first so we can clean up dirty data
    try:
        await collection.drop_index("uniq_tool_code")
    except Exception:
        pass
    try:
        await collection.drop_index("uniq_tool_name")
    except Exception:
        pass

    # Remove docs with missing code (legacy dirty data)
    dirty = await collection.delete_many({"code": None})
    if dirty.deleted_count:
        logger.warning(f"Removed {dirty.deleted_count} tool docs with missing code")

    # Now safe to create unique indexes
    await collection.create_index("code", unique=True, name="uniq_tool_code")
    await collection.create_index("name", unique=True, name="uniq_tool_name")

    # Delete all system tools, then re-insert from definitions
    delete_result = await collection.delete_many({"is_system": True})
    logger.info(f"Removed {delete_result.deleted_count} existing system tools")

    docs = []
    for tool_def in TOOL_DEFINITIONS:
        docs.append({
            **tool_def,
            "timeout": 300, "enabled": True, "health_status": "unknown",
            "last_health_check": None, "health_check_url": None,
            "endpoint_url": None, "endpoint_method": None,
            "headers": None, "auth_type": None, "auth_config": None,
            "output_schema": None, "agent_count": 0,
            "created_at": _now_iso(), "updated_at": _now_iso(),
        })
    if docs:
        await collection.insert_many(docs)
    result = {"inserted": len(docs), "total": len(TOOL_DEFINITIONS)}
    logger.info(f"Seed result: {result}")
    return result


def _now_iso() -> str:
    from app.utils.timezone import now_tz
    return now_tz().isoformat()
