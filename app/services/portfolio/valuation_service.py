from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Iterable, Mapping

from app.services.portfolio.fx_service import FxService
from app.services.portfolio.types import decimal_string


@dataclass
class PortfolioValuation:
    base_currency: str
    total_market_value: str
    total_cost: str
    total_realized_pnl: str
    total_unrealized_pnl: str
    total_pnl: str
    positions: list[dict]
    excluded: list[dict]
    valuation_time: str


class ValuationService:
    def __init__(self, fx_service: FxService | None = None):
        self.fx_service = fx_service or FxService()

    async def _convert(self, amount, source, target, at) -> Decimal:
        return await self.fx_service.convert(Decimal(str(amount)), source, target, at)

    async def value_positions(
        self,
        positions: Iterable[Mapping],
        base_currency: str,
        valuation_time: datetime | None = None,
    ) -> PortfolioValuation:
        at = valuation_time or datetime.now(timezone.utc)
        included: list[dict] = []
        excluded: list[dict] = []
        total_market = Decimal("0")
        total_cost = Decimal("0")
        total_realized = Decimal("0")
        total_unrealized = Decimal("0")

        for position in positions:
            item = dict(position)
            currency = str(item["quote_asset"])
            try:
                market_value = await self._convert(item["market_value"], currency, base_currency, at)
                cost_value = await self._convert(item.get("cost_value", "0"), currency, base_currency, at)
                realized = await self._convert(item.get("realized_pnl", "0"), currency, base_currency, at)
                unrealized = market_value - cost_value
            except (LookupError, ValueError) as exc:
                item["conversion_error"] = str(exc)
                item["converted"] = False
                excluded.append(item)
                continue

            item.update({
                "converted": True,
                "base_currency": base_currency,
                "base_market_value": decimal_string(market_value),
                "base_cost_value": decimal_string(cost_value),
                "base_realized_pnl": decimal_string(realized),
                "base_unrealized_pnl": decimal_string(unrealized),
            })
            included.append(item)
            total_market += market_value
            total_cost += cost_value
            total_realized += realized
            total_unrealized += unrealized

        for item in included:
            value = Decimal(item["base_market_value"])
            weight = Decimal("0") if total_market == 0 else value / total_market * 100
            item["weight_percent"] = decimal_string(weight)

        return PortfolioValuation(
            base_currency=base_currency,
            total_market_value=decimal_string(total_market),
            total_cost=decimal_string(total_cost),
            total_realized_pnl=decimal_string(total_realized),
            total_unrealized_pnl=decimal_string(total_unrealized),
            total_pnl=decimal_string(total_realized + total_unrealized),
            positions=included,
            excluded=excluded,
            valuation_time=at.isoformat(),
        )
