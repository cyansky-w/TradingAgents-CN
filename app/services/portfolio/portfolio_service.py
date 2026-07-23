from datetime import datetime, timedelta, timezone
from decimal import Decimal

from app.services.portfolio.position_calculator import PositionCalculator
from app.services.portfolio.types import decimal_string


class PortfolioService:
    def __init__(self, records, quote_gateway, valuation_service):
        self.records = records
        self.quote_gateway = quote_gateway
        self.valuation_service = valuation_service

    async def _records(self, user_id):
        return await self.records.find({"user_id": user_id}).sort([
            ("trade_time", 1), ("created_at", 1), ("_id", 1)
        ]).to_list(length=None)

    async def get_positions(self, user_id, base_currency):
        records = await self._records(user_id)
        states = PositionCalculator.replay(records)
        quote_assets = {
            f"{item['market']}:{item['exchange']}:{item['symbol']}:{item['instrument_type']}": item.get("quote_asset")
            for item in records
        }
        raw_positions = []
        unavailable_positions = []
        excluded = []
        for state in states:
            if state.quantity <= 0:
                continue
            try:
                quote = await self.quote_gateway.get_quote(
                    state.asset.market, state.asset.exchange, state.asset.symbol,
                    state.asset.instrument_type,
                )
            except Exception as exc:
                error = str(exc)
                unavailable_positions.append({
                    "storage_key": state.asset.storage_key,
                    "market": state.asset.market.value,
                    "exchange": state.asset.exchange,
                    "symbol": state.asset.symbol,
                    "instrument_type": state.asset.instrument_type.value,
                    "position_side": state.position_side.value,
                    "quote_asset": quote_assets.get(state.asset.storage_key),
                    "quantity": decimal_string(state.quantity),
                    "average_entry_price": decimal_string(state.average_entry_price) if state.average_entry_price is not None else None,
                    "cost_value": decimal_string(state.cost_value) if state.cost_value is not None else None,
                    "realized_pnl": decimal_string(state.realized_pnl) if state.realized_pnl is not None else None,
                    "mark_price": None,
                    "market_value": None,
                    "unrealized_pnl": None,
                    "quote_unavailable": True,
                    "quote_error": error,
                })
                excluded.append({
                    "scope": "quote",
                    "storage_key": state.asset.storage_key,
                    "market": state.asset.market.value,
                    "exchange": state.asset.exchange,
                    "symbol": state.asset.symbol,
                    "position_side": state.position_side.value,
                    "error": error,
                })
                continue
            mark = Decimal(quote.price)
            market_value = mark * state.quantity
            unrealized_pnl = PositionCalculator.unrealized_pnl(state, mark)
            raw_positions.append({
                "storage_key": state.asset.storage_key,
                "market": state.asset.market.value,
                "exchange": state.asset.exchange,
                "symbol": state.asset.symbol,
                "instrument_type": state.asset.instrument_type.value,
                "position_side": state.position_side.value,
                "quote_asset": quote.quote_currency,
                "quantity": decimal_string(state.quantity),
                "average_entry_price": decimal_string(state.average_entry_price) if state.average_entry_price is not None else None,
                "cost_value": decimal_string(state.cost_value) if state.cost_value is not None else None,
                "mark_price": quote.price,
                "market_value": decimal_string(market_value),
                "realized_pnl": decimal_string(state.realized_pnl) if state.realized_pnl is not None else None,
                "unrealized_pnl": decimal_string(unrealized_pnl) if unrealized_pnl is not None else None,
                "quote_stale": quote.stale,
            })
        valued = await self.valuation_service.value_positions(raw_positions, base_currency)
        for item in unavailable_positions:
            item.update({
                "converted": False,
                "base_currency": base_currency,
                "base_market_value": None,
                "base_cost_value": None,
                "base_realized_pnl": None,
                "base_unrealized_pnl": None,
                "weight_percent": None,
            })
        valued.positions.extend(unavailable_positions)
        valued.excluded.extend(excluded)
        return {**valued.__dict__, "items": valued.positions}

    async def get_dashboard(self, user_id, base_currency, days):
        positions = await self.get_positions(user_id, base_currency)
        records = await self._records(user_id)
        pnl_curve, cumulative_realized, realized_excluded = await self._realized_pnl_curve(
            records, base_currency, days
        )
        realized_pnl = decimal_string(cumulative_realized)
        total_pnl = decimal_string(
            Decimal(realized_pnl) + Decimal(positions["total_unrealized_pnl"])
        )
        return {
            "base_currency": base_currency,
            "total_market_value": positions["total_market_value"],
            "total_cost": positions["total_cost"],
            "realized_pnl": realized_pnl,
            "unrealized_pnl": positions["total_unrealized_pnl"],
            "total_pnl": total_pnl,
            "holding_count": len(positions["items"]),
            "total_trade_count": len(records),
            "excluded": [*positions["excluded"], *realized_excluded],
            "pnl_curve": pnl_curve,
            "valuation_time": datetime.now(timezone.utc).isoformat(),
        }

    async def _realized_pnl_curve(self, records, base_currency, days):
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        prefix = []
        previous_realized = {}
        cumulative = Decimal("0")
        curve = []
        excluded = []

        for record in records:
            prefix.append(record)
            trade_time = datetime.fromisoformat(
                str(record["trade_time"]).replace("Z", "+00:00")
            )
            if trade_time.tzinfo is None:
                trade_time = trade_time.replace(tzinfo=timezone.utc)

            quote_assets = {
                (
                    item["market"], item["exchange"], item["symbol"],
                    item["instrument_type"], item["position_side"],
                ): item["quote_asset"]
                for item in prefix
            }
            changed = False
            for state in PositionCalculator.replay(prefix):
                key = (
                    state.asset.market.value,
                    state.asset.exchange,
                    state.asset.symbol,
                    state.asset.instrument_type.value,
                    state.position_side.value,
                )
                realized = state.realized_pnl
                previous = previous_realized.get(key, Decimal("0"))
                if realized is None:
                    if previous is not None:
                        excluded.append({
                            "scope": "realized_pnl",
                            "storage_key": state.asset.storage_key,
                            "symbol": state.asset.symbol,
                            "position_side": state.position_side.value,
                            "quote_asset": quote_assets.get(key),
                            "realized_pnl": None,
                            "trade_time": trade_time.isoformat(),
                            "record_id": str(record.get("_id", "")),
                            "error": "realized PnL is unknown due to unknown cost basis",
                        })
                    previous_realized[key] = None
                    continue
                if previous is None:
                    excluded.append({
                        "scope": "realized_pnl",
                        "storage_key": state.asset.storage_key,
                        "symbol": state.asset.symbol,
                        "position_side": state.position_side.value,
                        "quote_asset": quote_assets.get(key),
                        "realized_pnl": decimal_string(realized),
                        "trade_time": trade_time.isoformat(),
                        "record_id": str(record.get("_id", "")),
                        "error": "realized PnL delta cannot be derived after unknown cost basis",
                    })
                    previous_realized[key] = realized
                    continue
                delta = realized - previous
                if delta == 0:
                    previous_realized[key] = realized
                    continue
                try:
                    cumulative += await self.valuation_service.fx_service.convert(
                        delta, quote_assets[key], base_currency, trade_time
                    )
                except (LookupError, ValueError, KeyError) as exc:
                    excluded.append({
                        "scope": "realized_pnl",
                        "storage_key": state.asset.storage_key,
                        "symbol": state.asset.symbol,
                        "position_side": state.position_side.value,
                        "quote_asset": quote_assets.get(key),
                        "realized_pnl": decimal_string(delta),
                        "trade_time": trade_time.isoformat(),
                        "record_id": str(record.get("_id", "")),
                        "error": str(exc),
                    })
                    previous_realized[key] = realized
                    continue
                previous_realized[key] = realized
                changed = True

            if changed and trade_time >= cutoff:
                point = {
                    "date": trade_time.date().isoformat(),
                    "cumulative_pnl": decimal_string(cumulative),
                }
                if curve and curve[-1]["date"] == point["date"]:
                    curve[-1] = point
                else:
                    curve.append(point)

        return curve, cumulative, excluded


class PreferenceService:
    def __init__(self, collection):
        self.collection = collection

    async def get_or_create(self, user_id):
        existing = await self.collection.find_one({"user_id": user_id})
        if existing:
            return {key: value for key, value in existing.items() if key != "_id"}
        document = {"user_id": user_id, "base_currency": "CNY", "updated_at": datetime.now(timezone.utc).isoformat()}
        await self.collection.insert_one(document)
        return {key: value for key, value in document.items() if key != "_id"}

    async def update(self, user_id, base_currency):
        document = {"user_id": user_id, "base_currency": base_currency, "updated_at": datetime.now(timezone.utc).isoformat()}
        await self.collection.update_one({"user_id": user_id}, {"$set": document}, upsert=True)
        return document
