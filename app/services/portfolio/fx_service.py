from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Awaitable, Callable, Optional


@dataclass(frozen=True)
class FxRate:
    source_currency: str
    target_currency: str
    rate: Decimal
    path: list[str]
    source: str
    timestamp: str


class FxService:
    BRIDGES = ("USD", "USDT", "CNY")

    def __init__(
        self,
        db=None,
        direct_rate_provider: Optional[
            Callable[[str, str, datetime], Awaitable[Optional[Decimal]]]
        ] = None,
    ):
        self.db = db
        self.direct_rate_provider = direct_rate_provider

    async def get_rate(self, source: str, target: str, at: datetime) -> FxRate:
        source = source.upper()
        target = target.upper()
        at = at if at.tzinfo else at.replace(tzinfo=timezone.utc)
        if source == target:
            return FxRate(source, target, Decimal("1"), [source], "identity", at.isoformat())

        pair = await self._get_pair_rate(source, target, at)
        if pair is not None:
            rate, rate_source = pair
            return FxRate(
                source, target, rate, [source, target], rate_source, at.isoformat()
            )

        for bridge in self.BRIDGES:
            if bridge in {source, target}:
                continue
            first = await self._get_pair_rate(source, bridge, at)
            second = await self._get_pair_rate(bridge, target, at)
            if first is not None and second is not None:
                return FxRate(
                    source, target, first[0] * second[0],
                    [source, bridge, target], "multi-hop", at.isoformat()
                )

        raise ValueError(f"no FX route from {source} to {target}")

    async def convert(
        self, amount: Decimal, source: str, target: str, at: datetime
    ) -> Decimal:
        return amount * (await self.get_rate(source, target, at)).rate

    async def _get_pair_rate(
        self, source: str, target: str, at: datetime
    ) -> Optional[tuple[Decimal, str]]:
        direct = await self._get_direct_rate(source, target, at)
        if direct is not None:
            return direct, "direct"
        inverse = await self._get_direct_rate(target, source, at)
        if inverse not in {None, Decimal("0")}:
            return Decimal("1") / inverse, "inverse"
        return None

    async def _get_direct_rate(
        self, source: str, target: str, at: datetime
    ) -> Optional[Decimal]:
        if self.direct_rate_provider is not None:
            return await self.direct_rate_provider(source, target, at)
        return await asyncio.to_thread(self._fetch_yfinance_rate, source, target, at)

    @staticmethod
    def _fetch_yfinance_rate(
        source: str, target: str, at: datetime
    ) -> Optional[Decimal]:
        import yfinance as yf

        symbols = [f"{source}{target}=X"]
        if {source, target} == {"USD", "USDT"}:
            symbols = ["USDT-USD" if source == "USDT" else "USDUSDT=X"]
        elif target == "USD":
            symbols.append(f"{source}-USD")
        start = at.date().isoformat()
        end = (at.date() + timedelta(days=1)).isoformat()
        for symbol in symbols:
            try:
                history = yf.download(symbol, start=start, end=end, progress=False)
            except Exception:
                continue
            if history.empty:
                continue
            value = history["Close"].dropna().iloc[-1]
            if hasattr(value, "iloc"):
                value = value.iloc[0]
            return Decimal(str(value))
        return None
