from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
import logging
import re

from app.routers.auth_db import get_current_user
from app.core.database import get_mongo_db
from app.core.response import ok
from app.models.real_trades import CreateTradeRequest, UpdateTradeRequest

router = APIRouter(prefix="/real-trades", tags=["real-trades"])
logger = logging.getLogger("webapi")

CURRENCY_MAP = {"CN": "CNY", "HK": "HKD", "US": "USD"}


def _detect_market_and_code(code: str) -> tuple:
    """检测股票代码的市场类型并标准化代码"""
    code = code.strip().upper()
    if code.endswith('.HK'):
        return 'HK', code[:-3].zfill(5)
    if re.match(r'^[A-Z]+$', code):
        return 'US', code
    if re.match(r'^\d{4,5}$', code):
        return 'HK', code.zfill(5)
    if re.match(r'^\d{6}$', code):
        return 'CN', code
    return 'CN', code.zfill(6)


async def _get_last_price(code: str, market: str) -> Optional[float]:
    db = get_mongo_db()
    # A股
    if market == "CN":
        q = await db["market_quotes"].find_one(
            {"$or": [{"code": code}, {"symbol": code}]}, {"_id": 0, "close": 1}
        )
        if q and q.get("close") is not None:
            try:
                price = float(q["close"])
                if price > 0:
                    return price
            except Exception:
                pass
        basic_info = await db["stock_basic_info"].find_one(
            {"$or": [{"code": code}, {"symbol": code}]}, {"_id": 0, "current_price": 1}
        )
        if basic_info and basic_info.get("current_price") is not None:
            try:
                price = float(basic_info["current_price"])
                if price > 0:
                    return price
            except Exception:
                pass
        return None
    # 港股/美股
    elif market in ('HK', 'US'):
        try:
            from app.services.foreign_stock_service import ForeignStockService
            db = get_mongo_db()
            service = ForeignStockService(db=db)
            quote = await service.get_quote(market, code, force_refresh=False)
            if quote:
                price = quote.get("price") or quote.get("current_price") or quote.get("close")
                if price and float(price) > 0:
                    return float(price)
        except Exception as e:
            logger.error(f"获取{market}股价格失败 {code}: {e}")
            return None
    return None


async def _get_stock_name(code: str) -> Optional[str]:
    db = get_mongo_db()
    doc = await db["stock_basic_info"].find_one(
        {"$or": [{"code": code}, {"symbol": code}]}, {"_id": 0, "name": 1}
    )
    if doc:
        return doc.get("name")
    return None


# ---- Endpoints ----

@router.post("/record")
async def create_record(payload: CreateTradeRequest, current_user: dict = Depends(get_current_user)):
    db = get_mongo_db()

    if payload.market:
        market = payload.market.upper()
        normalized_code = payload.code.strip().upper()
    else:
        market, normalized_code = _detect_market_and_code(payload.code)

    currency = CURRENCY_MAP.get(market, "CNY")
    amount = round(payload.price * payload.quantity, 2)
    name = await _get_stock_name(normalized_code)
    now_iso = datetime.utcnow().isoformat()

    doc = {
        "user_id": current_user["id"],
        "code": normalized_code,
        "market": market,
        "currency": currency,
        "name": name,
        "side": payload.side,
        "price": payload.price,
        "quantity": payload.quantity,
        "amount": amount,
        "commission": payload.commission,
        "trade_date": payload.trade_date.isoformat(),
        "reason": payload.reason,
        "tags": payload.tags,
        "notes": payload.notes,
        "created_at": now_iso,
        "updated_at": now_iso,
    }
    result = await db["real_trades"].insert_one(doc)
    doc["id"] = str(result.inserted_id)
    return ok({"record": {k: v for k, v in doc.items() if k != "_id"}})


@router.put("/record/{record_id}")
async def update_record(record_id: str, payload: UpdateTradeRequest, current_user: dict = Depends(get_current_user)):
    db = get_mongo_db()
    from bson import ObjectId as BsonObjectId

    existing = await db["real_trades"].find_one({"_id": BsonObjectId(record_id), "user_id": current_user["id"]})
    if not existing:
        raise HTTPException(status_code=404, detail="记录不存在")

    updates = {}
    update_data = payload.model_dump(exclude_none=True)
    for field in ("code", "market", "side", "price", "quantity", "commission", "reason", "tags", "notes", "trade_date"):
        if field in update_data:
            val = update_data[field]
            if field == "trade_date" and isinstance(val, datetime):
                val = val.isoformat()
            updates[field] = val
    if "price" in updates or "quantity" in updates:
        p = updates.get("price", existing.get("price", 0))
        q = updates.get("quantity", existing.get("quantity", 0))
        updates["amount"] = round(p * q, 2)
    if "code" in updates or "market" in updates:
        code = updates.get("code", existing.get("code"))
        market = updates.get("market", existing.get("market", "CN"))
        updates["currency"] = CURRENCY_MAP.get(market.upper(), "CNY")
        name = await _get_stock_name(code.strip().upper())
        if name:
            updates["name"] = name

    updates["updated_at"] = datetime.utcnow().isoformat()
    await db["real_trades"].update_one(
        {"_id": BsonObjectId(record_id)}, {"$set": updates}
    )
    return ok({"message": "更新成功"})


@router.delete("/record/{record_id}")
async def delete_record(record_id: str, current_user: dict = Depends(get_current_user)):
    db = get_mongo_db()
    from bson import ObjectId as BsonObjectId

    result = await db["real_trades"].delete_one({"_id": BsonObjectId(record_id), "user_id": current_user["id"]})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="记录不存在")
    return ok({"message": "删除成功"})


@router.get("/records")
async def list_records(
    code: Optional[str] = Query(None),
    side: Optional[str] = Query(None),
    tags: Optional[str] = Query(None, description="逗号分隔"),
    pnl: Optional[str] = Query(None, description="profit/loss"),
    start: Optional[str] = Query(None),
    end: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    sort: str = Query("desc", pattern="^(asc|desc)$"),
    current_user: dict = Depends(get_current_user),
):
    db = get_mongo_db()
    filters: Dict[str, Any] = {"user_id": current_user["id"]}

    if code:
        filters["code"] = {"$regex": code.strip(), "$options": "i"}
    if side and side in ("buy", "sell"):
        filters["side"] = side
    if tags:
        tag_list = [t.strip() for t in tags.split(",") if t.strip()]
        if tag_list:
            filters["tags"] = {"$all": tag_list}

    # 日期范围
    if start or end:
        date_filter = {}
        if start:
            date_filter["$gte"] = start
        if end:
            date_filter["$lte"] = end
        if date_filter:
            filters["trade_date"] = date_filter

    sort_dir = -1 if sort == "desc" else 1
    total = await db["real_trades"].count_documents(filters)
    cursor = db["real_trades"].find(filters).sort("trade_date", sort_dir).skip((page - 1) * page_size).limit(page_size)
    items = await cursor.to_list(page_size)

    tag_list_for_filter = [t.strip() for t in tags.split(",") if t.strip()] if tags else []

    cleaned = []
    for it in items:
        item = {k: v for k, v in it.items() if k != "_id"}
        item["id"] = str(it["_id"])
        # 计算卖出盈亏
        item_pnl = None
        if it["side"] == "sell":
            # 获取这只股票的持仓均价（卖出前）
            buy_avg_cost = await _get_buy_avg_cost(current_user["id"], it["code"])
            if buy_avg_cost is not None:
                item_pnl = round((it["price"] - buy_avg_cost) * it["quantity"], 2)
        item["pnl"] = item_pnl

        # pnl 筛选在客户端做（这里做服务端过滤）
        cleaned.append(item)

    # pnl 筛选 (profit: pnl>0, loss: pnl<0)
    if pnl == "profit":
        cleaned = [i for i in cleaned if i.get("pnl") is not None and i["pnl"] > 0]
    elif pnl == "loss":
        cleaned = [i for i in cleaned if i.get("pnl") is not None and i["pnl"] < 0]

    return ok({"items": cleaned, "total": total, "page": page, "page_size": page_size})


async def _get_buy_avg_cost(user_id: str, code: str) -> Optional[float]:
    """计算某股票的买入加权平均成本"""
    db = get_mongo_db()
    buys = await db["real_trades"].find({"user_id": user_id, "code": code, "side": "buy"}).to_list(None)
    if not buys:
        return None
    total_qty = sum(int(b["quantity"]) for b in buys)
    total_cost = sum(float(b["price"]) * int(b["quantity"]) for b in buys)
    return round(total_cost / total_qty, 4) if total_qty > 0 else None


@router.get("/positions")
async def list_positions(current_user: dict = Depends(get_current_user)):
    db = get_mongo_db()
    records = await db["real_trades"].find({"user_id": current_user["id"]}).sort("trade_date", 1).to_list(None)

    # 按标的聚合
    holdings: Dict[str, dict] = {}
    for r in records:
        code = r["code"]
        if code not in holdings:
            holdings[code] = {
                "code": code,
                "market": r.get("market", "CN"),
                "currency": r.get("currency", "CNY"),
                "name": r.get("name"),
                "buy_qty": 0,
                "buy_cost": 0.0,
                "sell_qty": 0,
            }
        h = holdings[code]
        qty = int(r["quantity"])
        price = float(r["price"])
        if r["side"] == "buy":
            h["buy_qty"] += qty
            h["buy_cost"] += price * qty
        else:
            h["sell_qty"] += qty

    positions = []
    total_market_value = 0.0

    # 先计算所有持仓市值
    temp_positions = []
    for h in holdings.values():
        remaining = h["buy_qty"] - h["sell_qty"]
        if remaining <= 0:
            continue
        avg_cost = round(h["buy_cost"] / h["buy_qty"], 4) if h["buy_qty"] > 0 else 0.0
        last_price = await _get_last_price(h["code"], h["market"])
        market_value = round((last_price or avg_cost) * remaining, 2)
        total_market_value += market_value
        temp_positions.append({**h, "remaining": remaining, "avg_cost": avg_cost, "last_price": last_price, "market_value": market_value})

    for p in temp_positions:
        weight = round(p["market_value"] / total_market_value * 100, 2) if total_market_value > 0 else 0.0
        unrealized = None
        pnl_pct = None
        if p["last_price"] is not None:
            unrealized = round((p["last_price"] - p["avg_cost"]) * p["remaining"], 2)
            pnl_pct = round((p["last_price"] / p["avg_cost"] - 1) * 100, 2) if p["avg_cost"] > 0 else None

        positions.append({
            "code": p["code"],
            "market": p["market"],
            "currency": p["currency"],
            "name": p["name"],
            "quantity": p["remaining"],
            "avg_cost": p["avg_cost"],
            "total_cost": round(p["avg_cost"] * p["remaining"], 2),
            "last_price": p["last_price"],
            "market_value": p["market_value"],
            "unrealized_pnl": unrealized,
            "pnl_percent": pnl_pct,
            "weight_percent": weight,
        })

    return ok({"items": positions, "total_market_value": round(total_market_value, 2)})


@router.get("/dashboard")
async def get_dashboard(
    days: int = Query(90, ge=7, le=3650),
    current_user: dict = Depends(get_current_user),
):
    db = get_mongo_db()
    user_id = current_user["id"]
    records = await db["real_trades"].find({"user_id": user_id}).sort("trade_date", 1).to_list(None)

    # 已实现盈亏
    realized_pnl = 0.0
    win_count = 0
    loss_count = 0
    total_win_amount = 0.0
    total_loss_amount = 0.0

    # 按标的聚合买入均价（用于计算卖出盈亏）
    buy_avg_map: Dict[str, dict] = {}
    for r in records:
        code = r["code"]
        if code not in buy_avg_map:
            buy_avg_map[code] = {"qty": 0, "cost": 0.0}
        if r["side"] == "buy":
            qty = int(r["quantity"])
            buy_avg_map[code]["qty"] += qty
            buy_avg_map[code]["cost"] += float(r["price"]) * qty

    for r in records:
        if r["side"] == "sell":
            code = r["code"]
            avg_cost = buy_avg_map[code]["cost"] / buy_avg_map[code]["qty"] if buy_avg_map[code]["qty"] > 0 else 0
            pnl = round((float(r["price"]) - avg_cost) * int(r["quantity"]), 2)
            realized_pnl += pnl
            if pnl > 0:
                win_count += 1
                total_win_amount += pnl
            elif pnl < 0:
                loss_count += 1
                total_loss_amount += abs(pnl)

    # 未实现盈亏: 复用持仓计算
    pos_result = await list_positions(current_user)
    positions = pos_result["data"]["items"]
    total_market_value = pos_result["data"]["total_market_value"]
    unrealized_pnl = sum(p.get("unrealized_pnl", 0) or 0 for p in positions)
    total_cost = sum(p.get("total_cost", 0) for p in positions)

    total_pnl = realized_pnl + unrealized_pnl
    total_trades = win_count + loss_count
    win_rate = round(win_count / total_trades, 4) if total_trades > 0 else 0.0
    avg_win = round(total_win_amount / win_count, 2) if win_count > 0 else 0.0
    avg_loss = round(total_loss_amount / loss_count, 2) if loss_count > 0 else 0.0
    profit_loss_ratio = round(avg_win / avg_loss, 2) if avg_loss > 0 else 0.0

    # 收益率曲线：按日累计盈亏
    cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()
    recent = [r for r in records if r.get("trade_date", "") >= cutoff]
    daily_pnl: Dict[str, float] = {}
    for r in recent:
        date_key = r.get("trade_date", "")[:10]
        if date_key not in daily_pnl:
            daily_pnl[date_key] = 0.0
        code = r["code"]
        avg_cost = buy_avg_map[code]["cost"] / buy_avg_map[code]["qty"] if buy_avg_map.get(code, {}).get("qty", 0) > 0 else 0
        if r["side"] == "sell":
            pnl = round((float(r["price"]) - avg_cost) * int(r["quantity"]), 2)
        else:
            # 买入日不算盈亏，用后续持仓浮动
            pnl = 0.0
        daily_pnl[date_key] += pnl

    sorted_dates = sorted(daily_pnl.keys())
    cumulative = 0.0
    pnl_curve = []
    for d in sorted_dates:
        cumulative += daily_pnl[d]
        pnl_curve.append({"date": d, "cumulative_pnl": round(cumulative, 2)})

    # 注入当日未实现盈亏到最后一天
    if pnl_curve and unrealized_pnl != 0:
        pnl_curve[-1]["cumulative_pnl"] = round(pnl_curve[-1]["cumulative_pnl"] + unrealized_pnl, 2)

    # 持仓分布
    sector_distribution = [
        {
            "code": p["code"],
            "name": p.get("name", p["code"]),
            "market_value": p["market_value"],
            "percentage": p["weight_percent"],
        }
        for p in positions
    ]

    return ok({
        "total_equity": None,  # 留待后续版本完善（需整合账户初始资金）
        "total_cost": round(total_cost, 2),
        "total_pnl": round(total_pnl, 2),
        "realized_pnl": round(realized_pnl, 2),
        "unrealized_pnl": round(unrealized_pnl, 2),
        "win_rate": win_rate,
        "profit_loss_ratio": profit_loss_ratio,
        "holding_count": len(positions),
        "total_trade_count": len(records),
        "pnl_curve": pnl_curve,
        "sector_distribution": sector_distribution,
    })


@router.get("/record/{record_id}")
async def get_record(record_id: str, current_user: dict = Depends(get_current_user)):
    from bson import ObjectId as BsonObjectId
    db = get_mongo_db()
    doc = await db["real_trades"].find_one({"_id": BsonObjectId(record_id), "user_id": current_user["id"]})
    if not doc:
        raise HTTPException(status_code=404, detail="记录不存在")
    item = {k: v for k, v in doc.items() if k != "_id"}
    item["id"] = str(doc["_id"])
    return ok({"record": item})
