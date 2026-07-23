from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
import sys

import pandas as pd
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
async def test_same_day_rate_is_cached_for_repeated_valuation_requests():
    calls = 0

    async def fake_direct(source, target, at):
        nonlocal calls
        calls += 1
        return Decimal("0.14")

    service = FxService(direct_rate_provider=fake_direct)
    at = datetime(2026, 7, 21, 12, tzinfo=timezone.utc)

    assert (await service.get_rate("CNY", "USD", at)).rate == Decimal("0.14")
    assert (await service.get_rate("CNY", "USD", at.replace(hour=13))).rate == Decimal("0.14")
    assert calls == 1


@pytest.mark.asyncio
async def test_multi_hop_rate_can_use_inverse_quotes(monkeypatch):
    async def fake_direct(source, target, at):
        rates = {
            ("CNY", "USD"): Decimal("0.14"),
            ("USD", "USDT"): Decimal("1"),
        }
        return rates.get((source, target))

    service = FxService()
    monkeypatch.setattr(service, "_get_direct_rate", fake_direct)

    rate = await service.get_rate("USDT", "CNY", datetime.now(timezone.utc))

    assert rate.rate == Decimal("7.142857142857142857142857143")
    assert rate.path == ["USDT", "USD", "CNY"]


@pytest.mark.asyncio
async def test_missing_conversion_route_is_explicit(monkeypatch):
    service = FxService()

    async def no_rate(source, target, at):
        return None

    monkeypatch.setattr(service, "_get_direct_rate", no_rate)
    with pytest.raises(ValueError, match="no FX route"):
        await service.get_rate("ALT", "CNY", datetime.now(timezone.utc))


def test_yfinance_rate_falls_back_to_crypto_usd_symbol(monkeypatch):
    symbols = []

    def fake_download(symbol, **kwargs):
        symbols.append(symbol)
        if symbol == "BNB-USD":
            return pd.DataFrame({"Close": [Decimal("600")]})
        return pd.DataFrame()

    monkeypatch.setitem(sys.modules, "yfinance", SimpleNamespace(download=fake_download))

    rate = FxService._fetch_yfinance_rate(
        "BNB", "USD", datetime(2026, 7, 14, tzinfo=timezone.utc)
    )

    assert rate == Decimal("600")
    assert symbols == ["BNBUSD=X", "BNB-USD"]
