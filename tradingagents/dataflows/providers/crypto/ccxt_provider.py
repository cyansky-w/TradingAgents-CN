"""
CCXT 加密货币数据提供器
支持多交易所实例管理、行情数据获取、跨交易所比价
"""

import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import ccxt

from tradingagents.utils.logging_manager import get_logger

logger = get_logger('agents')

SUPPORTED_EXCHANGES = ["binance", "okx", "bybit", "bitget", "gate"]
DEFAULT_EXCHANGE = "binance"
DEFAULT_TIMEFRAME = "1d"
MAX_CANDLES = 1000


class CCXTProvider:
    """CCXT 加密货币数据提供器 — 多交易所支持"""

    def __init__(self):
        self._exchanges: Dict[str, ccxt.Exchange] = {}
        logger.info("加密货币数据提供器初始化完成")

    def get_exchange(self, exchange_id: str) -> ccxt.Exchange:
        """获取或创建交易所实例（懒初始化 + 实例池）"""
        exchange_id = exchange_id.lower()
        if exchange_id not in SUPPORTED_EXCHANGES:
            raise ValueError(
                f"不支持的交易所: {exchange_id}，"
                f"支持的交易所: {', '.join(SUPPORTED_EXCHANGES)}"
            )
        if exchange_id not in self._exchanges:
            exchange_class = getattr(ccxt, exchange_id)
            self._exchanges[exchange_id] = exchange_class({
                'enableRateLimit': True,
                'options': {'defaultType': 'spot'},
            })
            logger.info(f"已创建交易所实例: {exchange_id}")
        return self._exchanges[exchange_id]

    # ── 行情数据 ──────────────────────────────────────────

    def get_crypto_market_data(
        self,
        symbol: str,
        exchange: str = DEFAULT_EXCHANGE,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        timeframe: str = DEFAULT_TIMEFRAME,
    ) -> str:
        """
        获取加密货币 OHLCV 数据并格式化为分析文本

        Args:
            symbol: 交易对，如 BTC/USDT
            exchange: 交易所 ID
            start_date: 开始日期 YYYY-MM-DD
            end_date: 结束日期 YYYY-MM-DD
            timeframe: K线周期

        Returns:
            str: 格式化的行情分析文本
        """
        try:
            ex = self.get_exchange(exchange)

            if not end_date:
                end_date = datetime.utcnow().strftime('%Y-%m-%d')
            if not start_date:
                start_date = (datetime.utcnow() - timedelta(days=90)).strftime('%Y-%m-%d')

            since = int(datetime.strptime(start_date, '%Y-%m-%d').timestamp() * 1000)
            limit = MAX_CANDLES

            logger.info(f"获取加密货币行情: {symbol}@{exchange} ({start_date} ~ {end_date})")

            ohlcv = ex.fetch_ohlcv(symbol, timeframe=timeframe, since=since, limit=limit)

            if not ohlcv:
                return f"无法获取 {symbol}@{exchange} 的行情数据"

            # 过滤超出 end_date 的数据
            end_ts = int(datetime.strptime(end_date, '%Y-%m-%d').timestamp() * 1000)
            ohlcv = [c for c in ohlcv if c[0] <= end_ts]

            if not ohlcv:
                return f"在指定日期范围内无数据: {symbol}@{exchange}"

            # 计算统计指标
            closes = [c[4] for c in ohlcv]
            volumes = [c[5] for c in ohlcv]
            latest = ohlcv[-1]
            first = ohlcv[0]

            high_price = max(c[2] for c in ohlcv)
            low_price = min(c[3] for c in ohlcv)
            avg_volume = sum(volumes) / len(volumes) if volumes else 0
            price_change = ((latest[4] - first[4]) / first[4]) * 100 if first[4] else 0

            # 简单移动平均
            def sma(data, period):
                if len(data) < period:
                    return None
                return sum(data[-period:]) / period

            ma5 = sma(closes, 5)
            ma10 = sma(closes, 10)
            ma20 = sma(closes, 20)

            # RSI
            def calc_rsi(data, period=14):
                if len(data) < period + 1:
                    return None
                gains, losses = [], []
                for i in range(1, len(data)):
                    diff = data[i] - data[i - 1]
                    gains.append(max(0, diff))
                    losses.append(max(0, -diff))
                avg_gain = sum(gains[-period:]) / period
                avg_loss = sum(losses[-period:]) / period
                if avg_loss == 0:
                    return 100
                rs = avg_gain / avg_loss
                return 100 - (100 / (1 + rs))

            rsi = calc_rsi(closes)

            result = f"加密货币行情分析: {symbol} ({exchange.upper()})\n"
            result += "=" * 60 + "\n\n"

            result += "基本信息\n"
            result += f"   交易对: {symbol}\n"
            result += f"   交易所: {exchange.upper()}\n"
            result += f"   数据期间: {start_date} 至 {end_date}\n"
            result += f"   K线周期: {timeframe}\n"
            result += f"   数据条数: {len(ohlcv)}\n\n"

            result += "最新价格\n"
            result += f"   开盘: ${latest[1]:,.2f}\n"
            result += f"   最高: ${latest[2]:,.2f}\n"
            result += f"   最低: ${latest[3]:,.2f}\n"
            result += f"   收盘: ${latest[4]:,.2f}\n"
            result += f"   成交量: {latest[5]:,.2f}\n"
            result += f"   区间涨跌: {price_change:+.2f}%\n"
            result += f"   区间最高: ${high_price:,.2f}\n"
            result += f"   区间最低: ${low_price:,.2f}\n"
            result += f"   日均成交量: {avg_volume:,.2f}\n\n"

            result += "技术指标\n"
            if ma5:
                result += f"   MA5: ${ma5:,.2f}\n"
            if ma10:
                result += f"   MA10: ${ma10:,.2f}\n"
            if ma20:
                result += f"   MA20: ${ma20:,.2f}\n"
            if rsi is not None:
                zone = "超买" if rsi >= 70 else "超卖" if rsi <= 30 else "中性"
                result += f"   RSI(14): {rsi:.2f} ({zone})\n"

            result += f"\n数据来源: CCXT / {exchange.upper()}\n"

            return result

        except ccxt.BaseError as e:
            logger.error(f"CCXT 行情获取失败: {e}")
            return f"获取行情数据失败: {symbol}@{exchange} — {e}"
        except Exception as e:
            logger.error(f"加密货币行情获取异常: {e}", exc_info=True)
            return f"获取行情数据异常: {symbol}@{exchange}"

    def get_crypto_ticker(self, symbol: str, exchange: str = DEFAULT_EXCHANGE) -> Optional[Dict]:
        """获取实时行情"""
        try:
            ex = self.get_exchange(exchange)
            ticker = ex.fetch_ticker(symbol)
            return {
                "symbol": symbol,
                "exchange": exchange,
                "last": ticker.get("last"),
                "bid": ticker.get("bid"),
                "ask": ticker.get("ask"),
                "high": ticker.get("high"),
                "low": ticker.get("low"),
                "volume": ticker.get("baseVolume"),
                "change": ticker.get("percentage"),
                "timestamp": ticker.get("datetime"),
            }
        except Exception as e:
            logger.error(f"获取实时行情失败: {symbol}@{exchange} — {e}")
            return None

    def get_crypto_market_overview(self, exchange: str = DEFAULT_EXCHANGE) -> str:
        """获取指定交易所的头部币种总览"""
        try:
            ex = self.get_exchange(exchange)
            tickers = ex.fetch_tickers()

            # 按成交量排序取前10
            sorted_tickers = sorted(
                [
                    (sym, t) for sym, t in tickers.items()
                    if t.get("baseVolume") and "/USDT" in sym
                ],
                key=lambda x: x[1].get("baseVolume", 0),
                reverse=True,
            )[:10]

            if not sorted_tickers:
                return f"{exchange.upper()} 暂无 USDT 交易对数据"

            result = f"加密货币市场总览 ({exchange.upper()})\n"
            result += "=" * 80 + "\n\n"
            result += f"{'交易对':<14} {'最新价':>12} {'24h涨跌':>10} {'24h成交量':>16}\n"
            result += "-" * 56 + "\n"

            for sym, t in sorted_tickers:
                last = t.get("last", 0) or 0
                pct = t.get("percentage", 0) or 0
                vol = t.get("baseVolume", 0) or 0
                pct_str = f"{pct:+.2f}%"
                result += f"{sym:<14} ${last:>11,.2f} {pct_str:>10} {vol:>14,.0f}\n"

            result += f"\n数据来源: CCXT / {exchange.upper()}\n"
            return result

        except Exception as e:
            logger.error(f"市场总览获取失败: {exchange} — {e}")
            return f"获取市场总览失败: {exchange}"

    def get_crypto_fundamentals(
        self, symbol: str, exchange: str = DEFAULT_EXCHANGE
    ) -> str:
        """
        获取交易对基本面信息（精度、限制、手续费）
        """
        try:
            ex = self.get_exchange(exchange)
            ex.load_markets()

            market = ex.market(symbol)
            if not market:
                return f"交易对 {symbol} 在 {exchange.upper()} 不存在"

            result = f"交易对信息: {symbol} ({exchange.upper()})\n"
            result += "=" * 50 + "\n\n"

            result += f"   交易对: {market.get('symbol', symbol)}\n"
            result += f"   基础货币: {market.get('base', '')}\n"
            result += f"   报价货币: {market.get('quote', '')}\n"
            result += f"   类型: {market.get('type', 'spot')}\n"
            result += f"   现货: {'是' if market.get('spot') else '否'}\n\n"

            # 精度信息
            result += "交易精度\n"
            result += f"   价格精度: {market.get('precision', {}).get('price', 'N/A')}\n"
            result += f"   数量精度: {market.get('precision', {}).get('amount', 'N/A')}\n\n"

            # 限制
            limits = market.get('limits', {})
            amount_lim = limits.get('amount', {})
            cost_lim = limits.get('cost', {})
            result += "交易限制\n"
            result += f"   最小下单量: {amount_lim.get('min', 'N/A')}\n"
            result += f"   最大下单量: {amount_lim.get('max', 'N/A')}\n"
            result += f"   最小金额: {cost_lim.get('min', 'N/A')}\n\n"

            # 手续费
            fees = market.get('fees', {})
            taker = fees.get('trading', {}).get('taker', 'N/A')
            maker = fees.get('trading', {}).get('maker', 'N/A')
            result += "手续费\n"
            result += f"   Taker: {taker}\n"
            result += f"   Maker: {maker}\n"

            result += f"\n数据来源: CCXT / {exchange.upper()}\n"
            return result

        except Exception as e:
            logger.error(f"交易对信息获取失败: {symbol}@{exchange} — {e}")
            return f"获取交易对信息失败: {symbol}@{exchange}"

    def compare_cross_exchange(
        self, symbol: str, exchanges: Optional[List[str]] = None
    ) -> str:
        """
        跨交易所比价

        Args:
            symbol: 交易对，如 BTC/USDT
            exchanges: 要比较的交易所列表，默认所有支持的交易所
        """
        if exchanges is None:
            exchanges = SUPPORTED_EXCHANGES

        results: List[Dict] = []
        for ex_id in exchanges:
            try:
                ex = self.get_exchange(ex_id)
                ticker = ex.fetch_ticker(symbol)
                if ticker and ticker.get("last"):
                    results.append({
                        "exchange": ex_id,
                        "last": ticker["last"],
                        "bid": ticker.get("bid"),
                        "ask": ticker.get("ask"),
                        "volume": ticker.get("baseVolume", 0) or 0,
                        "change": ticker.get("percentage", 0) or 0,
                        "spread": (ticker.get("ask", 0) or 0) - (ticker.get("bid", 0) or 0),
                    })
            except Exception as e:
                logger.warning(f"跨交易所比价跳过 {ex_id}: {e}")

        if not results:
            return f"无法获取 {symbol} 在任何交易所的价格数据"

        # 按价格排序
        results.sort(key=lambda x: x["last"])

        result = f"跨交易所价格对比: {symbol}\n"
        result += "=" * 80 + "\n\n"
        result += f"{'交易所':<12} {'最新价':>14} {'24h成交量':>16} {'24h涨跌':>10} {'买卖价差':>12}\n"
        result += "-" * 68 + "\n"

        for r in results:
            pct_str = f"{r['change']:+.2f}%"
            result += (
                f"{r['exchange']:<12} "
                f"${r['last']:>13,.2f} "
                f"{r['volume']:>14,.0f} "
                f"{pct_str:>10} "
                f"${r['spread']:>10,.4f}\n"
            )

        # 价格差分析
        if len(results) >= 2:
            cheapest = results[0]
            most_expensive = results[-1]
            diff = most_expensive["last"] - cheapest["last"]
            diff_pct = (diff / cheapest["last"]) * 100 if cheapest["last"] else 0
            result += f"\n价差: {cheapest['exchange']} vs {most_expensive['exchange']} "
            result += f"= ${diff:,.2f} ({diff_pct:.4f}%)\n"

        result += f"\n数据来源: CCXT\n"
        return result


# 全局提供器实例
_ccxt_provider: Optional[CCXTProvider] = None


def get_ccxt_provider() -> CCXTProvider:
    """获取全局 CCXT 提供器实例"""
    global _ccxt_provider
    if _ccxt_provider is None:
        _ccxt_provider = CCXTProvider()
    return _ccxt_provider
