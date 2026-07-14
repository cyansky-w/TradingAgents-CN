from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from app.services.portfolio.asset_normalizer import AssetNormalizer, QuantityRules
from app.services.portfolio.types import InstrumentType, Market, decimal_string


@dataclass(frozen=True)
class NormalizedQuote:
    market: Market
    exchange: str
    symbol: str
    price: str
    quote_currency: str
    source: str
    timestamp: Optional[str]
    stale: bool = False


class QuoteGateway:
    def __init__(self, db=None, foreign_service=None, ccxt_provider=None):
        self.db = db
        self.foreign_service = foreign_service
        self.ccxt_provider = ccxt_provider

    def _crypto_provider(self):
        if self.ccxt_provider is None:
            from tradingagents.dataflows.providers.crypto.ccxt_provider import (
                get_ccxt_provider,
            )

            self.ccxt_provider = get_ccxt_provider()
        return self.ccxt_provider

    async def get_quote(
        self,
        market,
        exchange,
        symbol,
        instrument_type,
    ) -> NormalizedQuote:
        asset = AssetNormalizer.normalize(market, exchange, symbol, instrument_type)
        if asset.market == Market.CRYPTO:
            return await self._get_crypto_quote(asset)
        if asset.market in {Market.HK, Market.US}:
            return await self._get_foreign_quote(asset)
        return await self._get_cn_quote(asset)

    async def _get_crypto_quote(self, asset) -> NormalizedQuote:
        ticker = await asyncio.to_thread(
            self._crypto_provider().get_crypto_ticker,
            asset.symbol,
            asset.exchange,
        )
        if not ticker or ticker.get("last") is None:
            raise LookupError(f"quote unavailable for {asset.symbol}@{asset.exchange}")
        quote_currency = asset.symbol.split("/", 1)[1].split(":", 1)[0]
        return NormalizedQuote(
            market=asset.market,
            exchange=asset.exchange,
            symbol=asset.symbol,
            price=decimal_string(ticker["last"]),
            quote_currency=quote_currency,
            source="ccxt",
            timestamp=ticker.get("timestamp"),
            stale=False,
        )

    async def _get_foreign_quote(self, asset) -> NormalizedQuote:
        if self.foreign_service is None:
            from app.services.foreign_stock_service import ForeignStockService

            self.foreign_service = ForeignStockService(db=self.db)
        quote = await self.foreign_service.get_quote(
            asset.market.value, asset.symbol, force_refresh=False
        )
        price = quote.get("price") or quote.get("current_price") or quote.get("close")
        if price is None:
            raise LookupError(f"quote unavailable for {asset.symbol}")
        timestamp = quote.get("timestamp") or quote.get("updated_at")
        return NormalizedQuote(
            market=asset.market,
            exchange=asset.exchange,
            symbol=asset.symbol,
            price=decimal_string(price),
            quote_currency="HKD" if asset.market == Market.HK else "USD",
            source=str(quote.get("source") or "foreign_stock_service"),
            timestamp=timestamp,
            stale=self._is_stale(timestamp),
        )

    async def _get_cn_quote(self, asset) -> NormalizedQuote:
        if self.db is None:
            raise LookupError("database is required for A-share quotes")
        quote = await self.db["market_quotes"].find_one(
            {"$or": [{"code": asset.symbol}, {"symbol": asset.symbol}]},
            {"_id": 0},
        )
        if not quote or quote.get("close") is None:
            raise LookupError(f"quote unavailable for {asset.symbol}")
        timestamp = quote.get("timestamp") or quote.get("updated_at")
        return NormalizedQuote(
            market=asset.market,
            exchange=asset.exchange,
            symbol=asset.symbol,
            price=decimal_string(quote["close"]),
            quote_currency="CNY",
            source=str(quote.get("source") or "market_quotes"),
            timestamp=timestamp,
            stale=self._is_stale(timestamp),
        )

    async def get_asset_rules(
        self,
        market,
        exchange,
        symbol,
        instrument_type,
    ) -> QuantityRules:
        asset = AssetNormalizer.normalize(market, exchange, symbol, instrument_type)
        if asset.instrument_type not in {
            InstrumentType.CRYPTO_SPOT,
            InstrumentType.CRYPTO_LINEAR_PERPETUAL,
        }:
            return AssetNormalizer.quantity_rules(
                asset.market, asset.exchange, asset.symbol, asset.instrument_type
            )

        raw_rules = await asyncio.to_thread(
            self._crypto_provider().get_market_rules,
            asset.symbol,
            asset.exchange,
        )
        precision = int(raw_rules["amount_precision"])
        rules = AssetNormalizer.quantity_rules(
            asset.market,
            asset.exchange,
            asset.symbol,
            asset.instrument_type,
            precision=precision,
        )
        return QuantityRules(
            quantity_type=rules.quantity_type,
            step=rules.step,
            minimum=Decimal(str(raw_rules.get("min_amount") or rules.minimum)),
            precision=rules.precision,
            market=rules.market,
        )

    @staticmethod
    def _is_stale(timestamp: Optional[str], max_age_seconds: int = 900) -> bool:
        if not timestamp:
            return True
        try:
            observed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            if observed.tzinfo is None:
                observed = observed.replace(tzinfo=timezone.utc)
            return (datetime.now(timezone.utc) - observed).total_seconds() > max_age_seconds
        except (TypeError, ValueError):
            return True
