from bson import ObjectId
from fastapi import FastAPI
from fastapi.testclient import TestClient
from decimal import Decimal
import pytest

import app.routers.real_trades as real_trades
from app.services.portfolio.asset_normalizer import QuantityRules
from app.services.portfolio.types import Market


class FakeLedger:
    def __init__(self):
        self.by_idempotency_key = {}

    async def create_record(self, user_id, payload):
        document = {"_id": ObjectId(), "user_id": user_id, "version": 1, **payload,
                    "created_at": "2026-07-14T12:00:00+00:00", "updated_at": "2026-07-14T12:00:00+00:00"}
        if payload.get("idempotency_key"):
            self.by_idempotency_key[payload["idempotency_key"]] = document
        return document

    async def create_record_with_status(self, user_id, payload):
        existing = await self.get_by_idempotency_key(
            user_id, payload.get("idempotency_key")
        )
        if existing is not None:
            return existing, False
        return await self.create_record(user_id, payload), True

    async def get_by_idempotency_key(self, user_id, key):
        return self.by_idempotency_key.get(key)

    async def get_record(self, user_id, record_id):
        return None

    async def list_records(self, user_id):
        return [{
            "_id": ObjectId(),
            "user_id": user_id,
            "record_type": "trade",
            "market": "CRYPTO",
            "exchange": "binance",
            "symbol": "BTC/USDT:USDT",
            "instrument_type": "crypto_linear_perpetual",
            "quote_asset": "USDT",
            "side": "buy",
            "position_side": "long",
            "position_action": "open",
            "price": "60000",
            "quantity": "0.01",
            "gross_amount": "600",
            "fee_amount": "0.01",
            "fee_currency": "BNB",
            "trade_time": "2026-07-14T12:00:00+00:00",
            "version": 1,
        }]


class FakePortfolio:
    async def get_positions(self, user_id, base_currency):
        return {"items": [], "base_currency": base_currency, "total_market_value": "0", "excluded": []}

    async def get_dashboard(self, user_id, base_currency, days):
        return {"base_currency": base_currency, "total_market_value": "0", "pnl_curve": []}


class FakePreference:
    def __init__(self):
        self.currency = "CNY"

    async def get_or_create(self, user_id):
        return {"user_id": user_id, "base_currency": self.currency}

    async def update(self, user_id, base_currency):
        self.currency = base_currency
        return {"user_id": user_id, "base_currency": base_currency}


class FakeQuoteGateway:
    async def get_asset_rules(self, market, exchange, symbol, instrument_type):
        if str(market) == "CRYPTO":
            return QuantityRules(
                "decimal", Decimal("0.001"), Decimal("0.001"), 3, Market.CRYPTO
            )
        return QuantityRules(
            "integer", Decimal("1"), Decimal("1"), 0, Market(str(market))
        )


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(real_trades.router, prefix="/api")
    preference = FakePreference()
    app.dependency_overrides[real_trades.get_current_user] = lambda: {"id": "u1"}
    app.dependency_overrides[real_trades.get_ledger_service] = lambda: FakeLedger()
    app.dependency_overrides[real_trades.get_portfolio_service] = lambda: FakePortfolio()
    app.dependency_overrides[real_trades.get_preference_service] = lambda: preference
    app.dependency_overrides[real_trades.get_quote_gateway] = lambda: FakeQuoteGateway()
    return TestClient(app, raise_server_exceptions=False)


def us_short_open_payload(**overrides):
    payload = {"record_type": "trade", "market": "US", "exchange": "NASDAQ",
               "symbol": "AAPL", "instrument_type": "equity", "quote_asset": "USD",
               "side": "sell", "position_side": "short", "position_action": "open",
               "price": "200", "quantity": "2", "trade_time": "2026-07-14T12:00:00Z"}
    payload.update(overrides)
    return payload


def test_create_accepts_v1_aliases_and_returns_v2_fields(client):
    response = client.post("/api/real-trades/record", json={
        "code": "AAPL", "market": "US", "side": "buy", "price": "200",
        "quantity": "2", "commission": "1.5", "trade_date": "2026-01-01T00:00:00Z",
        "reason": "entry",
    })
    assert response.status_code == 201
    body = response.json()["data"]["record"]
    assert body["symbol"] == body["code"] == "AAPL"
    assert body["fee_amount"] == body["commission"] == "1.5"


def test_open_short_us_equity_returns_201(client):
    response = client.post("/api/real-trades/record", json=us_short_open_payload())
    assert response.status_code == 201
    assert response.json()["data"]["record"]["position_side"] == "short"


def test_a_share_short_returns_422(client):
    response = client.post("/api/real-trades/record", json=us_short_open_payload(
        market="CN", exchange="SSE", symbol="600519", quote_asset="CNY"))
    assert response.status_code == 422
    assert "A-share short" in str(response.json())


def test_crypto_quantity_must_match_exchange_step(client):
    response = client.post(
        "/api/real-trades/record",
        json=us_short_open_payload(
            market="CRYPTO",
            exchange="binance",
            symbol="BTC/USDT:USDT",
            instrument_type="crypto_linear_perpetual",
            quote_asset="USDT",
            quantity="0.0005",
        ),
    )
    assert response.status_code == 422
    assert "quantity must be at least 0.001" in str(response.json())


def test_positions_accept_base_currency(client):
    response = client.get("/api/real-trades/positions", params={"base_currency": "USDT"})
    assert response.status_code == 200
    assert response.json()["data"]["base_currency"] == "USDT"


def test_records_convert_fee_to_selected_base_currency_at_trade_time(client, monkeypatch):
    class FakeFx:
        async def convert(self, amount, source, target, at):
            assert amount == Decimal("0.01")
            assert source == "BNB"
            assert target == "CNY"
            assert at.isoformat() == "2026-07-14T12:00:00+00:00"
            return Decimal("2.5")

    monkeypatch.setattr(real_trades, "FxService", lambda db=None: FakeFx())
    monkeypatch.setattr(real_trades, "get_mongo_db", lambda: {})

    response = client.get(
        "/api/real-trades/records",
        params={"base_currency": "CNY"},
    )

    assert response.status_code == 200
    record = response.json()["data"]["items"][0]
    assert record["fee_amount"] == "0.01"
    assert record["fee_currency"] == "BNB"
    assert record["base_fee_amount"] == "2.5"
    assert record["base_fee_currency"] == "CNY"
    assert record["fee_conversion_error"] is None


def test_portfolio_preference_round_trip(client):
    assert client.put("/api/real-trades/portfolio-preference", json={"base_currency": "USD"}).status_code == 200
    loaded = client.get("/api/real-trades/portfolio-preference")
    assert loaded.json()["data"]["base_currency"] == "USD"


def test_imports_report_success_duplicate_and_error(client):
    valid = us_short_open_payload(idempotency_key="row-1")
    spaced_duplicate = {**valid, "idempotency_key": " row-1 "}
    invalid = us_short_open_payload(
        idempotency_key="row-2",
        market="CN",
        exchange="SSE",
        symbol="600519",
        quote_asset="CNY",
        position_side="long",
        side="buy",
        quantity="150",
    )

    response = client.post(
        "/api/real-trades/imports",
        json={"items": [valid, spaced_duplicate, invalid]},
    )

    assert response.status_code == 200
    results = response.json()["data"]["results"]
    assert [item["status"] for item in results] == [
        "success",
        "duplicate",
        "error",
    ]
    assert response.json()["data"]["counts"] == {
        "success": 1,
        "duplicate": 1,
        "error": 1,
    }
    assert results[1]["idempotency_key"] == "row-1"


def test_invalid_object_id_returns_422(client):
    response = client.get("/api/real-trades/record/not-an-object-id")
    assert response.status_code == 422
