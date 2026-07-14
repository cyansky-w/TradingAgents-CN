from decimal import Decimal

import pytest

from app.services.portfolio.quote_gateway import QuoteGateway
from tradingagents.dataflows.providers.crypto.ccxt_provider import CCXTProvider


class FakeProvider:
    def get_crypto_ticker(self, symbol, exchange):
        assert symbol == "BTC/USDT:USDT"
        assert exchange == "binance"
        return {"last": 65000.12, "timestamp": "2026-07-14T12:00:00Z"}

    def get_market_rules(self, symbol, exchange):
        assert symbol == "BTC/USDT:USDT"
        assert exchange == "binance"
        return {"amount_precision": 5, "min_amount": "0.0001"}


@pytest.mark.asyncio
async def test_crypto_perpetual_quote_is_normalized():
    quote = await QuoteGateway(ccxt_provider=FakeProvider()).get_quote(
        "CRYPTO", "binance", "BTC/USDT:USDT", "crypto_linear_perpetual"
    )

    assert quote.price == "65000.12"
    assert quote.quote_currency == "USDT"
    assert quote.source == "ccxt"
    assert quote.exchange == "binance"


@pytest.mark.asyncio
async def test_crypto_asset_rules_use_exchange_minimum():
    rules = await QuoteGateway(ccxt_provider=FakeProvider()).get_asset_rules(
        "CRYPTO", "binance", "BTC/USDT:USDT", "crypto_linear_perpetual"
    )
    assert rules.precision == 5
    assert rules.step == Decimal("0.00001")
    assert rules.minimum == Decimal("0.0001")


def test_ccxt_market_rules_normalize_precision_and_limits():
    class FakeExchange:
        def load_markets(self):
            return None

        def market(self, symbol):
            assert symbol == "BTC/USDT:USDT"
            return {
                "precision": {"amount": 0.00001, "price": 0.1},
                "limits": {"amount": {"min": 0.0001}, "cost": {"min": 5}},
            }

    provider = CCXTProvider.__new__(CCXTProvider)
    provider.get_exchange = lambda exchange: FakeExchange()
    rules = provider.get_market_rules("BTC/USDT:USDT", "binance")

    assert rules == {
        "amount_precision": 5,
        "price_precision": 0.1,
        "min_amount": "0.0001",
        "min_cost": "5",
    }
