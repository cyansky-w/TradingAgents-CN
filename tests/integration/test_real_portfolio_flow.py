from copy import deepcopy
from datetime import datetime, timezone
from decimal import Decimal

from bson import ObjectId
from pydantic import ValidationError
import pytest

from app.models.real_trades import CreateLedgerRecordRequest
from app.services.portfolio.fx_service import FxService
from app.services.portfolio.ledger_service import LedgerService, VersionConflict
from app.services.portfolio.portfolio_service import PortfolioService
from app.services.portfolio.quote_gateway import NormalizedQuote
from app.services.portfolio.types import Market
from app.services.portfolio.valuation_service import ValuationService


class InsertResult:
    def __init__(self, inserted_id):
        self.inserted_id = inserted_id


class FakeCursor:
    def __init__(self, documents):
        self.documents = documents

    def sort(self, fields):
        for field, direction in reversed(fields):
            self.documents.sort(
                key=lambda item: item.get(field, ""), reverse=direction < 0
            )
        return self

    async def to_list(self, length=None):
        return self.documents if length is None else self.documents[:length]


class FakeCollection:
    def __init__(self):
        self.documents = []

    async def find_one(self, query):
        return next(
            (deepcopy(item) for item in self.documents if matches(item, query)),
            None,
        )

    def find(self, query):
        return FakeCursor(
            [deepcopy(item) for item in self.documents if matches(item, query)]
        )

    async def insert_one(self, document):
        stored = deepcopy(document)
        stored.setdefault("_id", ObjectId())
        self.documents.append(stored)
        return InsertResult(stored["_id"])

    async def replace_one(self, query, replacement):
        for index, item in enumerate(self.documents):
            if matches(item, query):
                self.documents[index] = deepcopy(replacement)
                return True
        return False

    async def delete_one(self, query):
        self.documents = [
            item for item in self.documents if not matches(item, query)
        ]

    async def count_documents(self, query):
        return sum(1 for item in self.documents if matches(item, query))


def matches(document, query):
    return all(document.get(key) == value for key, value in query.items())


class FakeQuoteGateway:
    prices = {
        ("CN", "SSE", "600519"): ("1600", "CNY"),
        ("US", "NASDAQ", "AAPL"): ("210", "USD"),
        ("CRYPTO", "binance", "BTC/USDT:USDT"): ("52000", "USDT"),
        ("HK", "SEHK", "00700"): ("400", "HKD"),
    }

    async def get_quote(self, market, exchange, symbol, instrument_type):
        price, currency = self.prices[(str(market), exchange, symbol)]
        return NormalizedQuote(
            market=Market(str(market)),
            exchange=exchange,
            symbol=symbol,
            price=price,
            quote_currency=currency,
            source="test",
            timestamp="2026-07-14T12:00:00+00:00",
        )


async def direct_fx_rate(source, target, at):
    if (
        (source, target) == ("HKD", "USD")
        and at.hour == 12
        and at.minute >= 7
    ):
        return Decimal("0.13")
    return {
        ("CNY", "USD"): Decimal("0.14"),
        ("USD", "USDT"): Decimal("1"),
    }.get((source, target))


def trade_payload(**overrides):
    payload = {
        "record_type": "trade",
        "market": "US",
        "exchange": "NASDAQ",
        "symbol": "AAPL",
        "instrument_type": "equity",
        "quote_asset": "USD",
        "side": "buy",
        "position_side": "long",
        "position_action": "open",
        "price": "200",
        "quantity": "2",
        "fee_amount": "0",
        "fee_currency": "USD",
        "trade_time": "2026-07-14T12:00:00+00:00",
    }
    payload.update(overrides)
    return payload


def validated(payload):
    return CreateLedgerRecordRequest.model_validate(payload).model_dump(
        mode="json", exclude_none=True
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_real_multi_asset_portfolio_flow():
    records = FakeCollection()
    ledger = LedgerService(records, FakeCollection())
    portfolio = PortfolioService(
        records,
        FakeQuoteGateway(),
        ValuationService(FxService(direct_rate_provider=direct_fx_rate)),
    )

    with pytest.raises(ValidationError, match="multiple of 100"):
        validated(
            trade_payload(
                market="CN",
                exchange="SSE",
                symbol="600519",
                quote_asset="CNY",
                price="1500",
                quantity="150",
                fee_currency="CNY",
            )
        )

    with pytest.raises(ValidationError, match="quote_asset"):
        validated(
            trade_payload(
                market="CRYPTO",
                exchange="binance",
                symbol="BTC/USDT:USDT",
                instrument_type="crypto_linear_perpetual",
                quote_asset="CNY",
                position_side="short",
                side="sell",
                fee_currency="CNY",
            )
        )

    with pytest.raises(ValidationError, match="non-crypto markets require equity"):
        validated(
            trade_payload(
                market="CN",
                exchange="SSE",
                symbol="600519",
                instrument_type="crypto_linear_perpetual",
                quote_asset="CNY",
                quantity="100",
            )
        )

    await ledger.create_record(
        "u1",
        validated(
            trade_payload(
                market="CN",
                exchange="SSE",
                symbol="600519",
                quote_asset="CNY",
                price="1500",
                quantity="200",
                fee_currency="CNY",
            )
        ),
    )
    await ledger.create_record(
        "u1",
        validated(
            trade_payload(
                market="HK",
                exchange="SEHK",
                symbol="00941",
                quote_asset="HKD",
                price="50",
                quantity="10",
                fee_currency="HKD",
                trade_time="2026-07-14T12:05:00+00:00",
            )
        ),
    )
    await ledger.create_record(
        "u1",
        validated(
            trade_payload(
                market="HK",
                exchange="SEHK",
                symbol="00941",
                quote_asset="HKD",
                side="sell",
                position_action="close",
                price="60",
                quantity="10",
                fee_currency="HKD",
                trade_time="2026-07-14T12:06:00+00:00",
            )
        ),
    )
    long_record = await ledger.create_record(
        "u1", validated(trade_payload(idempotency_key="aapl-long"))
    )
    duplicate = await ledger.create_record(
        "u1", validated(trade_payload(idempotency_key="aapl-long"))
    )
    assert duplicate["_id"] == long_record["_id"]

    await ledger.create_record(
        "u1",
        validated(
            trade_payload(
                side="sell",
                position_side="short",
                price="220",
                quantity="1",
                trade_time="2026-07-14T12:01:00+00:00",
            )
        ),
    )
    btc_open = trade_payload(
        market="CRYPTO",
        exchange="BINANCE",
        symbol="btc/usdt:usdt",
        instrument_type="crypto_linear_perpetual",
        quote_asset="USDT",
        side="sell",
        position_side="short",
        price="50000",
        quantity="1",
        fee_currency="USDT",
        leverage="10",
        initial_margin="1000",
        margin_mode="cross",
        trade_time="2026-07-14T12:02:00+00:00",
    )
    normalized_btc_open = validated(btc_open)
    assert normalized_btc_open["exchange"] == "binance"
    assert normalized_btc_open["symbol"] == "BTC/USDT:USDT"
    await ledger.create_record("u1", normalized_btc_open)
    await ledger.create_record(
        "u1",
        validated(
            {
                **btc_open,
                "side": "buy",
                "position_action": "close",
                "price": "45000",
                "quantity": "0.4",
                "fee_amount": "10",
                "trade_time": "2026-07-14T12:03:00+00:00",
            }
        ),
    )
    await ledger.create_record(
        "u1",
        validated(
            trade_payload(
                market="HK",
                exchange="SEHK",
                symbol="00700",
                quote_asset="HKD",
                price="390",
                quantity="1",
                fee_currency="HKD",
                trade_time="2026-07-14T12:04:00+00:00",
            )
        ),
    )
    await ledger.create_record(
        "u1",
        validated(
            trade_payload(
                side="sell",
                position_action="close",
                price="230",
                quantity="1",
                trade_time="2026-07-14T12:07:00+00:00",
            )
        ),
    )

    usd = await portfolio.get_positions("u1", "USD")
    us_sides = {
        item["position_side"]
        for item in usd["items"]
        if item["symbol"] == "AAPL"
    }
    assert us_sides == {"long", "short"}
    btc = next(item for item in usd["items"] if item["symbol"] == "BTC/USDT:USDT")
    assert btc["quantity"] == "0.6"
    assert Decimal(btc["base_realized_pnl"]) == Decimal("1990")
    assert Decimal(btc["base_unrealized_pnl"]) == Decimal("-1200")
    assert abs(Decimal(btc["base_unrealized_pnl"])) > Decimal("1000")
    assert any(item["symbol"] == "00700" for item in usd["excluded"])

    cny = await portfolio.get_dashboard("u1", "CNY", 90)
    usdt = await portfolio.get_dashboard("u1", "USDT", 90)
    assert Decimal(cny["total_market_value"]) > Decimal(usd["total_market_value"])
    assert Decimal(usdt["total_market_value"]) == Decimal(usd["total_market_value"])
    assert abs(
        Decimal(cny["pnl_curve"][-1]["cumulative_pnl"])
        - (Decimal("2020") / Decimal("0.14"))
    ) < Decimal("0.00000000000000000001")
    assert any(
        item.get("scope") == "realized_pnl" and item.get("symbol") == "00941"
        for item in cny["excluded"]
    )

    await ledger.update_record(
        "u1",
        str(long_record["_id"]),
        validated(trade_payload(price="190", idempotency_key="aapl-long")),
        expected_version=1,
    )
    updated = await portfolio.get_positions("u1", "USD")
    aapl_long = next(
        item
        for item in updated["items"]
        if item["symbol"] == "AAPL" and item["position_side"] == "long"
    )
    assert aapl_long["average_entry_price"] == "190"
    assert aapl_long["quantity"] == "1"
    updated_dashboard = await portfolio.get_dashboard("u1", "USD", 90)
    assert Decimal(updated_dashboard["realized_pnl"]) == Decimal("2030")

    with pytest.raises(VersionConflict):
        await ledger.update_record(
            "u1",
            str(long_record["_id"]),
            validated(trade_payload(price="180", idempotency_key="aapl-long")),
            expected_version=1,
        )

    for index, item in enumerate(records.documents, start=1):
        item["trade_time"] = f"2025-01-{index:02d}T12:00:00+00:00"
    historic = await portfolio.get_dashboard("u1", "USD", 90)
    assert historic["pnl_curve"] == []
    assert Decimal(historic["realized_pnl"]) == Decimal("2030")
