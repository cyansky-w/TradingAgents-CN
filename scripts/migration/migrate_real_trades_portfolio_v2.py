from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path

from pymongo import MongoClient

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.core.config import settings
from app.services.portfolio.position_calculator import PositionCalculator, PositionError


@dataclass
class MigrationError:
    record_id: str
    code: str
    message: str


@dataclass
class MigrationReport:
    converted: list[dict] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    errors: list[MigrationError] = field(default_factory=list)

    def as_dict(self):
        return {
            "converted": self.converted,
            "skipped": self.skipped,
            "errors": [error.__dict__ for error in self.errors],
        }


def _decimal(value, default=0):
    return format(Decimal(str(default if value is None else value)), "f")


def convert_legacy_record(document):
    market = str(document.get("market") or "CN").upper()
    symbol = str(document.get("symbol") or document.get("code") or "").upper()
    exchange = document.get("exchange")
    if market == "CRYPTO":
        raise ValueError("unsupported_crypto_spot_migration")
    if market == "CN":
        exchange = "SSE" if symbol.startswith(("5", "6", "9")) else "SZSE"
    elif market == "HK":
        exchange, symbol = "SEHK", symbol.removesuffix(".HK").zfill(5)
    elif market == "US" and not exchange:
        raise ValueError("ambiguous_exchange")
    side = document.get("side")
    converted = dict(document)
    converted.update({
        "schema_version": 2,
        "record_type": "trade",
        "market": market,
        "exchange": str(exchange).upper(),
        "symbol": symbol,
        "instrument_type": "equity",
        "quote_asset": document.get("quote_asset") or document.get("currency"),
        "position_side": "long",
        "position_action": "open" if side == "buy" else "close",
        "price": _decimal(document.get("price")),
        "quantity": _decimal(document.get("quantity")),
        "fee_amount": _decimal(document.get("commission")),
        "fee_currency": document.get("currency"),
        "fee_type": "commission",
        "trade_time": document.get("trade_time") or document.get("trade_date"),
    })
    return converted


def migrate_documents(documents):
    report = MigrationReport()
    for document in documents:
        record_id = str(document.get("_id", ""))
        if document.get("schema_version", 0) >= 2:
            report.skipped.append(record_id)
            continue
        try:
            converted = convert_legacy_record(document)
            related = [item for item in report.converted if (
                item.get("user_id"), item.get("market"), item.get("exchange"),
                item.get("symbol"), item.get("position_side"),
            ) == (
                converted.get("user_id"), converted.get("market"), converted.get("exchange"),
                converted.get("symbol"), converted.get("position_side"),
            )]
            PositionCalculator.replay([*related, converted])
            report.converted.append(converted)
        except PositionError as exc:
            report.errors.append(MigrationError(record_id, "oversell_requires_opening_position", str(exc)))
        except ValueError as exc:
            code = str(exc)
            report.errors.append(MigrationError(record_id, code, code.replace("_", " ")))
    return report


def main():
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    parser.add_argument("--input", help="Optional JSON export; otherwise read MongoDB real_trades")
    parser.add_argument("--report", required=True)
    parser.add_argument("--backup-collection")
    args = parser.parse_args()
    client = None
    collection = None
    if args.input:
        documents = json.loads(Path(args.input).read_text(encoding="utf-8"))
    else:
        client = MongoClient(settings.MONGO_URI)
        database = client[settings.MONGO_DB]
        collection = database["real_trades"]
        documents = list(collection.find({}))
    report = migrate_documents(documents)
    if args.apply:
        if report.errors:
            Path(args.report).write_text(json.dumps(report.as_dict(), ensure_ascii=False, indent=2, default=str), encoding="utf-8")
            return 1
        if collection is None:
            raise SystemExit("--apply requires MongoDB input")
        if not args.backup_collection:
            raise SystemExit("--backup-collection is required with --apply")
        backup = collection.database[args.backup_collection]
        for converted in report.converted:
            original = collection.find_one({"_id": converted["_id"]})
            backup.replace_one({"_id": original["_id"]}, original, upsert=True)
            collection.replace_one({"_id": converted["_id"]}, converted)
    Path(args.report).write_text(json.dumps(report.as_dict(), ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    if client:
        client.close()
    return 1 if report.errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
