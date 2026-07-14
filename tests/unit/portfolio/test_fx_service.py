from datetime import datetime, timezone
from decimal import Decimal

import pytest

from app.services.portfolio.fx_service import FxService


@pytest.mark.asyncio
async def test_same_currency_rate_is_one():
    rate = await FxService().get_rate("USD", "USD", datetime.now(timezone.utc))
    assert rate.rate == Decimal("1")
    assert rate.path == ["USD"]


@pytest.mark.asyncio
async def test_multi_hop_rate_uses_usd(monkeypatch):
    async def fake_direct(source, target, at):
        rates = {
            ("CNY", "USD"): Decimal("0.14"),
            ("USD", "USDT"): Decimal("0.998"),
        }
        return rates.get((source, target))

    service = FxService()
    monkeypatch.setattr(service, "_get_direct_rate", fake_direct)
    rate = await service.get_rate("CNY", "USDT", datetime.now(timezone.utc))
    assert rate.rate == Decimal("0.13972")
    assert rate.path == ["CNY", "USD", "USDT"]


@pytest.mark.asyncio
async def test_missing_conversion_route_is_explicit(monkeypatch):
    service = FxService()

    async def no_rate(source, target, at):
        return None

    monkeypatch.setattr(service, "_get_direct_rate", no_rate)
    with pytest.raises(ValueError, match="no FX route"):
        await service.get_rate("ALT", "CNY", datetime.now(timezone.utc))
