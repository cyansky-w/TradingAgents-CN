import logging
import re
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, Optional

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import ValidationError

from app.core.database import get_mongo_db
from app.core.response import ok
from app.models.real_trades import CreateLedgerRecordRequest
from app.routers.auth_db import get_current_user
from app.services.portfolio.fx_service import FxService
from app.services.portfolio.ledger_service import LedgerService, PositionConflict, VersionConflict
from app.services.portfolio.portfolio_service import PortfolioService, PreferenceService
from app.services.portfolio.quote_gateway import QuoteGateway
from app.services.portfolio.valuation_service import ValuationService


router = APIRouter(prefix="/real-trades", tags=["real-trades"])
logger = logging.getLogger(__name__)
CURRENCY_MAP = {"CN": "CNY", "HK": "HKD", "US": "USD"}
VALIDATION_LOG_FIELDS = (
    "record_type", "market", "exchange", "symbol", "instrument_type",
    "quote_asset", "side", "position_side", "position_action", "price",
    "quantity", "order_notional", "leverage", "initial_margin",
    "fee_amount", "fee_currency", "funding_fee", "trade_time",
)


def _detect_market_and_code(code: str) -> tuple:
    code = code.strip().upper()
    if code.endswith(".HK"):
        return "HK", code[:-3].zfill(5)
    if re.match(r"^[A-Z]+$", code):
        return "US", code
    if re.match(r"^\d{4,5}$", code):
        return "HK", code.zfill(5)
    if re.match(r"^\d{6}$", code):
        return "CN", code
    return "CN", code.zfill(6)


def get_ledger_service():
    db = get_mongo_db()
    return LedgerService(db["real_trades"], db["real_trade_audit"])


def get_portfolio_service():
    db = get_mongo_db()
    fx = FxService(db=db)
    return PortfolioService(db["real_trades"], QuoteGateway(db=db), ValuationService(fx))


def get_preference_service():
    return PreferenceService(get_mongo_db()["portfolio_preferences"])


def get_quote_gateway():
    return QuoteGateway(db=get_mongo_db())


def get_fx_service():
    return FxService(db=get_mongo_db())


async def _validate_exchange_quantity(model, gateway):
    if model.market.value != "CRYPTO":
        return
    rules = await gateway.get_asset_rules(
        model.market.value,
        model.exchange,
        model.symbol,
        model.instrument_type.value,
    )
    error = rules.validate(model.quantity)
    if error:
        raise ValueError(error)


def _legacy_to_v2(payload: Dict[str, Any]) -> Dict[str, Any]:
    if "symbol" in payload:
        return payload
    market, symbol = _detect_market_and_code(payload["code"])
    market = str(payload.get("market") or market).upper()
    if market == "CN":
        exchange = "SSE" if symbol.startswith(("5", "6", "9")) else "SZSE"
    elif market == "HK":
        exchange = "SEHK"
    else:
        exchange = str(payload.get("exchange") or "NASDAQ").upper()
    side = payload["side"]
    return {
        "record_type": "trade", "market": market, "exchange": exchange,
        "symbol": symbol, "instrument_type": "equity",
        "quote_asset": payload.get("currency") or CURRENCY_MAP[market],
        "side": side, "position_side": "long",
        "position_action": "open" if side == "buy" else "close",
        "price": str(payload["price"]), "quantity": str(payload["quantity"]),
        "fee_amount": str(payload.get("commission", 0)),
        "fee_currency": payload.get("currency") or CURRENCY_MAP[market],
        "trade_time": payload["trade_date"], "reason": payload.get("reason"),
        "tags": payload.get("tags", []), "notes": payload.get("notes"),
    }


def _record_response(document):
    item = {k: v for k, v in document.items() if k not in {"_id", "user_id"}}
    item["id"] = str(document.get("_id", ""))
    item["code"] = item["symbol"]
    item["trade_date"] = item["trade_time"]
    item["commission"] = item.get("fee_amount") or "0"
    item["currency"] = item["quote_asset"]
    item["amount"] = item.get("gross_amount") or (
        str(Decimal(item["price"]) * Decimal(item["quantity"])) if item.get("price") else None
    )
    return item


async def _record_response_with_fee_conversion(document, base_currency, fx):
    item = _record_response(document)
    item.update({
        "base_fee_amount": None,
        "base_fee_currency": None,
        "fee_conversion_error": None,
    })
    fee_amount = document.get("fee_amount")
    fee_currency = str(document.get("fee_currency") or "").upper()
    quote_asset = str(document.get("quote_asset") or "").upper()
    if not fee_amount or not fee_currency or fee_currency == quote_asset:
        return item

    item["base_fee_currency"] = base_currency
    try:
        trade_time = document.get("trade_time")
        if not isinstance(trade_time, datetime):
            trade_time = datetime.fromisoformat(str(trade_time).replace("Z", "+00:00"))
        converted = await fx.convert(
            Decimal(str(fee_amount)), fee_currency, base_currency, trade_time
        )
        item["base_fee_amount"] = str(converted)
    except Exception as exc:
        item["fee_conversion_error"] = str(exc)
    return item


@router.post("/record", status_code=status.HTTP_201_CREATED)
async def create_record(payload: Dict[str, Any], current_user=Depends(get_current_user), ledger=Depends(get_ledger_service), gateway=Depends(get_quote_gateway)):
    try:
        model = CreateLedgerRecordRequest.model_validate(_legacy_to_v2(payload))
        await _validate_exchange_quantity(model, gateway)
        document = await ledger.create_record(current_user["id"], model.model_dump(mode="json", exclude_none=True))
        return ok({"record": _record_response(document)})
    except ValidationError as exc:
        logger.warning(
            "创建实盘记录模型校验失败: %s payload=%s",
            exc,
            {key: payload.get(key) for key in VALIDATION_LOG_FIELDS if key in payload},
        )
        raise HTTPException(422, detail=str(exc)) from exc
    except (LookupError, ValueError) as exc:
        logger.warning(
            "创建实盘记录业务校验失败: %s payload=%s",
            exc,
            {key: payload.get(key) for key in VALIDATION_LOG_FIELDS if key in payload},
        )
        raise HTTPException(422, detail=str(exc)) from exc
    except PositionConflict as exc:
        raise HTTPException(409, detail={"message": str(exc), "available_quantity": str(exc.available_quantity)}) from exc


@router.post("/imports")
async def import_records(payload: Dict[str, Any], current_user=Depends(get_current_user), ledger=Depends(get_ledger_service), gateway=Depends(get_quote_gateway)):
    items = payload.get("items")
    if not isinstance(items, list):
        raise HTTPException(422, detail="items must be a list")

    results = []
    counts = {"success": 0, "duplicate": 0, "error": 0}
    for index, item in enumerate(items):
        try:
            if not isinstance(item, dict):
                raise ValueError("import row must be an object")
            idempotency_key = str(item.get("idempotency_key") or "").strip()
            if not idempotency_key:
                raise ValueError("idempotency_key is required")
            normalized_item = {**item, "idempotency_key": idempotency_key}
            model = CreateLedgerRecordRequest.model_validate(
                _legacy_to_v2(normalized_item)
            )
            await _validate_exchange_quantity(model, gateway)
            document, created = await ledger.create_record_with_status(
                current_user["id"],
                model.model_dump(mode="json", exclude_none=True),
            )
            status_name = "success" if created else "duplicate"
            counts[status_name] += 1
            results.append({
                "index": index,
                "status": status_name,
                "idempotency_key": idempotency_key,
                "record": _record_response(document),
            })
        except (ValidationError, PositionConflict, ValueError, KeyError) as exc:
            counts["error"] += 1
            results.append({
                "index": index,
                "status": "error",
                "idempotency_key": (
                    str(item.get("idempotency_key") or "").strip()
                    if isinstance(item, dict)
                    else None
                ),
                "error": str(exc),
            })

    return ok({"results": results, "counts": counts})


@router.get("/positions")
async def list_positions(base_currency: str = Query("CNY", pattern="^(CNY|USD|USDT)$"), current_user=Depends(get_current_user), service=Depends(get_portfolio_service)):
    return ok(await service.get_positions(current_user["id"], base_currency))


@router.get("/dashboard")
async def get_dashboard(base_currency: str = Query("CNY", pattern="^(CNY|USD|USDT)$"), days: int = Query(90, ge=7, le=3650), current_user=Depends(get_current_user), service=Depends(get_portfolio_service)):
    return ok(await service.get_dashboard(current_user["id"], base_currency, days))


@router.get("/portfolio-preference")
async def get_portfolio_preference(current_user=Depends(get_current_user), service=Depends(get_preference_service)):
    return ok(await service.get_or_create(current_user["id"]))


@router.put("/portfolio-preference")
async def update_portfolio_preference(payload: Dict[str, str], current_user=Depends(get_current_user), service=Depends(get_preference_service)):
    currency = str(payload.get("base_currency", "")).upper()
    if currency not in {"CNY", "USD", "USDT"}:
        raise HTTPException(422, detail="unsupported base currency")
    return ok(await service.update(current_user["id"], currency))


@router.get("/record/{record_id}")
async def get_record(record_id: str, current_user=Depends(get_current_user), ledger=Depends(get_ledger_service)):
    if not ObjectId.is_valid(record_id):
        raise HTTPException(422, detail="invalid record id")
    document = await ledger.get_record(current_user["id"], record_id)
    if document is None:
        raise HTTPException(404, detail="record not found")
    return ok({"record": _record_response(document)})


@router.put("/record/{record_id}")
async def update_record(record_id: str, payload: Dict[str, Any], current_user=Depends(get_current_user), ledger=Depends(get_ledger_service), gateway=Depends(get_quote_gateway)):
    if not ObjectId.is_valid(record_id):
        raise HTTPException(422, detail="invalid record id")
    existing = await ledger.get_record(current_user["id"], record_id)
    if existing is None:
        raise HTTPException(404, detail="record not found")
    version = int(payload.pop("version", existing.get("version", 1)))
    merged = {k: v for k, v in existing.items() if k not in {"_id", "user_id", "version", "created_at", "updated_at"}}
    aliases = {"code": "symbol", "trade_date": "trade_time", "commission": "fee_amount", "currency": "quote_asset"}
    for key, value in payload.items():
        merged[aliases.get(key, key)] = str(value) if key in {"price", "quantity", "commission"} else value
    try:
        model = CreateLedgerRecordRequest.model_validate(merged)
        await _validate_exchange_quantity(model, gateway)
        document = await ledger.update_record(current_user["id"], record_id, model.model_dump(mode="json", exclude_none=True), version)
        return ok({"record": _record_response(document)})
    except ValidationError as exc:
        raise HTTPException(422, detail=str(exc)) from exc
    except (LookupError, ValueError) as exc:
        raise HTTPException(422, detail=str(exc)) from exc
    except VersionConflict as exc:
        raise HTTPException(409, detail={"message": str(exc), "current_version": exc.current_version}) from exc
    except PositionConflict as exc:
        raise HTTPException(409, detail={"message": str(exc), "available_quantity": str(exc.available_quantity)}) from exc


@router.delete("/record/{record_id}")
async def delete_record(record_id: str, version: Optional[int] = None, current_user=Depends(get_current_user), ledger=Depends(get_ledger_service)):
    if not ObjectId.is_valid(record_id):
        raise HTTPException(422, detail="invalid record id")
    try:
        await ledger.delete_record(current_user["id"], record_id, version)
        return ok({"message": "deleted"})
    except LookupError as exc:
        raise HTTPException(404, detail=str(exc)) from exc
    except VersionConflict as exc:
        raise HTTPException(409, detail={"message": str(exc), "current_version": exc.current_version}) from exc


@router.get("/records")
async def list_records(base_currency: str = Query("CNY", pattern="^(CNY|USD|USDT)$"), page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=200), current_user=Depends(get_current_user), ledger=Depends(get_ledger_service), fx=Depends(get_fx_service)):
    documents = await ledger.list_records(current_user["id"])
    start = (page - 1) * page_size
    items = [
        await _record_response_with_fee_conversion(document, base_currency, fx)
        for document in documents[start:start + page_size]
    ]
    return ok({"items": items, "total": len(documents), "page": page, "page_size": page_size})


@router.get("/asset-rules")
async def get_asset_rules(market: str, exchange: str, symbol: str, instrument_type: str, gateway=Depends(get_quote_gateway)):
    try:
        rules = await gateway.get_asset_rules(market, exchange, symbol, instrument_type)
        return ok({
            "quantity_type": rules.quantity_type, "step": str(rules.step),
            "minimum": str(rules.minimum), "precision": rules.precision,
        })
    except ValueError as exc:
        raise HTTPException(422, detail=str(exc)) from exc
