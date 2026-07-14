from copy import deepcopy
from datetime import datetime, timezone
from decimal import Decimal

from bson import ObjectId
from pymongo.errors import DuplicateKeyError

from app.services.portfolio.position_calculator import PositionCalculator, PositionError
from app.services.portfolio.types import decimal_string


DECIMAL_FIELDS = {"price", "quantity", "gross_amount", "fee_amount", "funding_fee", "leverage", "initial_margin"}


class VersionConflict(RuntimeError):
    def __init__(self, current_version):
        super().__init__("stale record version")
        self.current_version = current_version


class PositionConflict(RuntimeError):
    def __init__(self, message, available_quantity=None):
        super().__init__(message)
        self.available_quantity = available_quantity


def serialize_document(data):
    doc = deepcopy(data)
    for field in DECIMAL_FIELDS:
        if doc.get(field) is not None:
            doc[field] = decimal_string(doc[field])
    return doc


class LedgerService:
    def __init__(self, records, audit):
        self.records = records
        self.audit = audit

    async def _documents(self, user_id):
        return await self.records.find({"user_id": user_id}).sort([
            ("trade_time", 1), ("created_at", 1), ("_id", 1)
        ]).to_list(length=None)

    async def create_record(self, user_id, payload):
        document, _ = await self.create_record_with_status(user_id, payload)
        return document

    async def create_record_with_status(self, user_id, payload):
        key = payload.get("idempotency_key")
        if key:
            existing = await self.records.find_one({"user_id": user_id, "idempotency_key": key})
            if existing:
                return existing, False
        now = datetime.now(timezone.utc).isoformat()
        doc = serialize_document(payload)
        doc.update({"user_id": user_id, "version": 1, "created_at": now, "updated_at": now})
        try:
            PositionCalculator.replay([*(await self._documents(user_id)), doc])
        except PositionError as exc:
            raise PositionConflict(str(exc), exc.available_quantity) from exc
        try:
            result = await self.records.insert_one(doc)
        except DuplicateKeyError:
            if key:
                existing = await self.records.find_one(
                    {"user_id": user_id, "idempotency_key": key}
                )
                if existing is not None:
                    return existing, False
            raise
        doc["_id"] = result.inserted_id
        return doc, True

    async def update_record(self, user_id, record_id, payload, expected_version):
        object_id = ObjectId(record_id)
        existing = await self.records.find_one({"_id": object_id, "user_id": user_id})
        if existing is None:
            raise LookupError("record not found")
        if existing.get("version", 1) != expected_version:
            raise VersionConflict(existing.get("version", 1))
        replacement = serialize_document(payload)
        replacement.update({
            "_id": object_id, "user_id": user_id, "version": expected_version + 1,
            "created_at": existing["created_at"],
            "updated_at": datetime.now(timezone.utc).isoformat(),
        })
        documents = [d for d in await self._documents(user_id) if d["_id"] != object_id]
        try:
            PositionCalculator.replay([*documents, replacement])
        except PositionError as exc:
            raise PositionConflict(str(exc), exc.available_quantity) from exc
        await self.records.replace_one({"_id": object_id, "user_id": user_id, "version": expected_version}, replacement)
        await self.audit.insert_one({
            "action": "update", "record_id": object_id, "user_id": user_id,
            "previous": existing, "new": replacement,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        return replacement

    async def reconstruct_positions(self, user_id, symbol=None):
        documents = await self._documents(user_id)
        if symbol is not None:
            documents = [d for d in documents if d.get("symbol") == symbol]
        return [state for state in PositionCalculator.replay(documents) if state.quantity > Decimal("0")]

    async def get_record(self, user_id, record_id):
        return await self.records.find_one({"_id": ObjectId(record_id), "user_id": user_id})

    async def get_by_idempotency_key(self, user_id, key):
        return await self.records.find_one(
            {"user_id": user_id, "idempotency_key": key}
        )

    async def delete_record(self, user_id, record_id, expected_version=None):
        object_id = ObjectId(record_id)
        existing = await self.records.find_one({"_id": object_id, "user_id": user_id})
        if existing is None:
            raise LookupError("record not found")
        if expected_version is not None and existing.get("version", 1) != expected_version:
            raise VersionConflict(existing.get("version", 1))
        remaining = [d for d in await self._documents(user_id) if d["_id"] != object_id]
        try:
            PositionCalculator.replay(remaining)
        except PositionError as exc:
            raise PositionConflict(str(exc), exc.available_quantity) from exc
        await self.records.delete_one({"_id": object_id, "user_id": user_id})
        await self.audit.insert_one({
            "action": "delete", "record_id": object_id, "user_id": user_id,
            "previous": existing, "new": None,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    async def list_records(self, user_id):
        return await self._documents(user_id)
