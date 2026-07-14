from copy import deepcopy
from decimal import Decimal

import pytest
from bson import ObjectId

from app.services.portfolio.ledger_service import (
    LedgerService,
    PositionConflict,
    VersionConflict,
)


class InsertResult:
    def __init__(self, inserted_id):
        self.inserted_id = inserted_id


class FakeCollection:
    def __init__(self):
        self.documents = []

    async def find_one(self, query):
        return next((deepcopy(d) for d in self.documents if matches(d, query)), None)

    def find(self, query):
        return FakeCursor([deepcopy(d) for d in self.documents if matches(d, query)])

    async def insert_one(self, document):
        stored = deepcopy(document)
        stored.setdefault("_id", ObjectId())
        self.documents.append(stored)
        return InsertResult(stored["_id"])

    async def count_documents(self, query):
        return sum(1 for d in self.documents if matches(d, query))

    async def replace_one(self, query, replacement):
        for index, document in enumerate(self.documents):
            if matches(document, query):
                self.documents[index] = deepcopy(replacement)
                return True
        return False


class FakeCursor:
    def __init__(self, documents):
        self.documents = documents

    def sort(self, fields):
        for field, direction in reversed(fields):
            self.documents.sort(key=lambda item: item.get(field, ""), reverse=direction < 0)
        return self

    async def to_list(self, length=None):
        return self.documents if length is None else self.documents[:length]


def matches(document, query):
    return all(document.get(key) == value for key, value in query.items())


def trade_payload(**overrides):
    payload = {
        "record_type": "trade", "market": "US", "exchange": "NASDAQ",
        "symbol": "AAPL", "instrument_type": "equity", "quote_asset": "USD",
        "side": "buy", "position_side": "long", "position_action": "open",
        "price": "200", "quantity": "2", "fee_amount": None,
        "trade_time": "2026-01-01T00:00:00+00:00",
    }
    payload.update(overrides)
    return payload


@pytest.fixture
def records():
    return FakeCollection()


@pytest.fixture
def ledger_service(records):
    return LedgerService(records=records, audit=FakeCollection())


@pytest.mark.asyncio
async def test_duplicate_idempotency_key_returns_existing_record(ledger_service, records):
    payload = trade_payload(idempotency_key="import-row-1")
    first = await ledger_service.create_record("u1", payload)
    second = await ledger_service.create_record("u1", payload)
    assert second["_id"] == first["_id"]
    assert await records.count_documents({"user_id": "u1"}) == 1


@pytest.mark.asyncio
async def test_update_rejects_stale_version(ledger_service):
    created = await ledger_service.create_record("u1", trade_payload())
    with pytest.raises(VersionConflict) as error:
        await ledger_service.update_record(
            "u1", str(created["_id"]), trade_payload(price="201"), expected_version=0
        )
    assert error.value.current_version == 1


@pytest.mark.asyncio
async def test_create_rejects_close_larger_than_available_short(ledger_service):
    await ledger_service.create_record("u1", trade_payload(
        side="sell", position_side="short", position_action="open", quantity="2"
    ))
    with pytest.raises(PositionConflict) as error:
        await ledger_service.create_record("u1", trade_payload(
            side="buy", position_side="short", position_action="close", quantity="3",
            trade_time="2026-01-02T00:00:00+00:00",
        ))
    assert error.value.available_quantity == Decimal("2")


@pytest.mark.asyncio
async def test_identity_change_replays_old_and_new_assets(ledger_service):
    created = await ledger_service.create_record("u1", trade_payload())
    updated = await ledger_service.update_record(
        "u1", str(created["_id"]),
        trade_payload(exchange="NYSE", symbol="IBM", price="250"), expected_version=1,
    )
    assert await ledger_service.reconstruct_positions("u1", symbol="AAPL") == []
    new_positions = await ledger_service.reconstruct_positions("u1", symbol="IBM")
    assert new_positions[0].quantity == Decimal("2")
    assert updated["version"] == 2
