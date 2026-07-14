from bson import ObjectId
from decimal import Decimal
import pytest

from app.services.portfolio.fx_service import FxService
from app.services.portfolio.portfolio_service import PortfolioService, PreferenceService
from app.services.portfolio.valuation_service import ValuationService


class InsertMutatingCollection:
    async def find_one(self, query):
        return None

    async def insert_one(self, document):
        document["_id"] = ObjectId()


class ExistingPreferenceCollection:
    async def find_one(self, query):
        return {
            "_id": ObjectId(),
            "user_id": query["user_id"],
            "base_currency": "USD",
            "updated_at": "2026-07-14T12:00:00+00:00",
        }


@pytest.mark.asyncio
async def test_preference_creation_does_not_return_mongo_object_id():
    service = PreferenceService(InsertMutatingCollection())

    preference = await service.get_or_create("user-1")

    assert preference == {
        "user_id": "user-1",
        "base_currency": "CNY",
        "updated_at": preference["updated_at"],
    }


@pytest.mark.asyncio
async def test_existing_preference_does_not_return_mongo_object_id():
    service = PreferenceService(ExistingPreferenceCollection())

    preference = await service.get_or_create("user-1")

    assert preference == {
        "user_id": "user-1",
        "base_currency": "USD",
        "updated_at": "2026-07-14T12:00:00+00:00",
    }


def record(**overrides):
    item = {
        "record_type": "trade",
        "market": "HK",
        "exchange": "SEHK",
        "symbol": "00941",
        "instrument_type": "equity",
        "quote_asset": "HKD",
        "side": "buy",
        "position_side": "long",
        "position_action": "open",
        "price": "50",
        "quantity": "10",
        "fee_amount": "0",
        "fee_currency": "HKD",
        "trade_time": "2026-07-14T12:05:00+00:00",
        "created_at": "2026-07-14T12:05:00+00:00",
        "_id": "1",
    }
    item.update(overrides)
    return item


@pytest.mark.asyncio
async def test_later_fx_success_does_not_remove_earlier_exclusion():
    async def rate_provider(source, target, at):
        if (source, target) == ("HKD", "USD") and at.minute >= 7:
            return Decimal("0.1")
        return None

    service = PortfolioService(
        None,
        None,
        ValuationService(FxService(direct_rate_provider=rate_provider)),
    )
    records = [
        record(),
        record(
            _id="2",
            side="sell",
            position_action="close",
            price="60",
            trade_time="2026-07-14T12:06:00+00:00",
            created_at="2026-07-14T12:06:00+00:00",
        ),
        record(
            _id="3",
            trade_time="2026-07-14T12:07:00+00:00",
            created_at="2026-07-14T12:07:00+00:00",
        ),
        record(
            _id="4",
            side="sell",
            position_action="close",
            price="55",
            trade_time="2026-07-14T12:08:00+00:00",
            created_at="2026-07-14T12:08:00+00:00",
        ),
    ]

    _, cumulative, excluded = await service._realized_pnl_curve(
        records, "USD", 90
    )

    assert cumulative == Decimal("5.0")
    assert len(excluded) == 1
    assert excluded[0]["realized_pnl"] == "100"


@pytest.mark.asyncio
async def test_unknown_realized_pnl_preserves_previous_known_total():
    service = PortfolioService(None, None, ValuationService())
    records = [
        record(market="US", exchange="NASDAQ", symbol="AAPL", quote_asset="USD", price="100", quantity="2"),
        record(
            _id="2", market="US", exchange="NASDAQ", symbol="AAPL", quote_asset="USD",
            side="sell", position_action="close", price="120", quantity="1",
            trade_time="2026-07-14T12:06:00+00:00", created_at="2026-07-14T12:06:00+00:00",
        ),
        record(
            _id="3", record_type="transfer_in", market="US", exchange="NASDAQ",
            symbol="AAPL", quote_asset="USD", side=None, position_action=None,
            price=None, quantity="1", trade_time="2026-07-14T12:07:00+00:00",
            created_at="2026-07-14T12:07:00+00:00",
        ),
        record(
            _id="4", market="US", exchange="NASDAQ", symbol="AAPL", quote_asset="USD",
            side="sell", position_action="close", price="130", quantity="1",
            trade_time="2026-07-14T12:08:00+00:00", created_at="2026-07-14T12:08:00+00:00",
        ),
    ]

    _, cumulative, excluded = await service._realized_pnl_curve(
        records, "USD", 90
    )

    assert cumulative == Decimal("20")
    assert excluded[-1]["realized_pnl"] is None
