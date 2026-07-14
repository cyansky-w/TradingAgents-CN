from bson import ObjectId
from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

import app.routers.real_trades as real_trades


class FakeLedger:
    async def create_record(self, user_id, payload):
        return {"_id": ObjectId(), "user_id": user_id, "version": 1, **payload,
                "created_at": "2026-07-14T12:00:00+00:00", "updated_at": "2026-07-14T12:00:00+00:00"}

    async def get_record(self, user_id, record_id):
        return None


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


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(real_trades.router, prefix="/api")
    preference = FakePreference()
    app.dependency_overrides[real_trades.get_current_user] = lambda: {"id": "u1"}
    app.dependency_overrides[real_trades.get_ledger_service] = lambda: FakeLedger()
    app.dependency_overrides[real_trades.get_portfolio_service] = lambda: FakePortfolio()
    app.dependency_overrides[real_trades.get_preference_service] = lambda: preference
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


def test_positions_accept_base_currency(client):
    response = client.get("/api/real-trades/positions", params={"base_currency": "USDT"})
    assert response.status_code == 200
    assert response.json()["data"]["base_currency"] == "USDT"


def test_portfolio_preference_round_trip(client):
    assert client.put("/api/real-trades/portfolio-preference", json={"base_currency": "USD"}).status_code == 200
    loaded = client.get("/api/real-trades/portfolio-preference")
    assert loaded.json()["data"]["base_currency"] == "USD"


def test_invalid_object_id_returns_422(client):
    response = client.get("/api/real-trades/record/not-an-object-id")
    assert response.status_code == 422
