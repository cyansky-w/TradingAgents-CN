from datetime import datetime, timezone
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
        states = PositionCalculator.replay(await self._records(user_id))
        raw_positions = []
        excluded = []
        for state in states:
            if state.quantity <= 0:
                continue
            try:
                quote = await self.quote_gateway.get_quote(
                    state.asset.market, state.asset.exchange, state.asset.symbol,
                    state.asset.instrument_type,
                )
            except (LookupError, ValueError) as exc:
                excluded.append({"storage_key": state.asset.storage_key, "error": str(exc)})
                continue
            mark = Decimal(quote.price)
            market_value = mark * state.quantity
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
                "quote_stale": quote.stale,
            })
        valued = await self.valuation_service.value_positions(raw_positions, base_currency)
        valued.excluded.extend(excluded)
        return {**valued.__dict__, "items": valued.positions}

    async def get_dashboard(self, user_id, base_currency, days):
        positions = await self.get_positions(user_id, base_currency)
        records = await self._records(user_id)
        return {
            "base_currency": base_currency,
            "total_market_value": positions["total_market_value"],
            "total_cost": positions["total_cost"],
            "realized_pnl": positions["total_realized_pnl"],
            "unrealized_pnl": positions["total_unrealized_pnl"],
            "total_pnl": positions["total_pnl"],
            "holding_count": len(positions["items"]),
            "total_trade_count": len(records),
            "excluded": positions["excluded"],
            "pnl_curve": [],
            "valuation_time": datetime.now(timezone.utc).isoformat(),
        }


class PreferenceService:
    def __init__(self, collection):
        self.collection = collection

    async def get_or_create(self, user_id):
        existing = await self.collection.find_one({"user_id": user_id})
        if existing:
            return existing
        document = {"user_id": user_id, "base_currency": "CNY", "updated_at": datetime.now(timezone.utc).isoformat()}
        await self.collection.insert_one(document)
        return document

    async def update(self, user_id, base_currency):
        document = {"user_id": user_id, "base_currency": base_currency, "updated_at": datetime.now(timezone.utc).isoformat()}
        await self.collection.update_one({"user_id": user_id}, {"$set": document}, upsert=True)
        return document
