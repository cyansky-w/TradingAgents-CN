from decimal import Decimal

import pytest

from app.services.portfolio.valuation_service import ValuationService


@pytest.mark.asyncio
async def test_unconverted_position_is_excluded_from_weight(monkeypatch):
    service = ValuationService()
    positions = [
        {
            "storage_key": "US:NASDAQ:AAPL:equity",
            "quote_asset": "USD",
            "market_value": "100",
            "cost_value": "90",
            "realized_pnl": "0",
            "unrealized_pnl": "10",
        },
        {
            "storage_key": "CRYPTO:binance:ALT/BTC:crypto_spot",
            "quote_asset": "BTC",
            "market_value": "2",
            "cost_value": "1.9",
            "realized_pnl": "0",
            "unrealized_pnl": "0.1",
        },
    ]

    async def fake_convert(amount, source, target, at):
        if source == "BTC":
            raise ValueError("no route")
        return Decimal(amount) * Decimal("7")

    monkeypatch.setattr(service, "_convert", fake_convert)
    result = await service.value_positions(positions, "CNY")

    assert result.total_market_value == "700"
    assert result.positions[0]["weight_percent"] == "100"
    assert result.positions[0]["base_unrealized_pnl"] == "70"
    assert result.excluded[0]["storage_key"].endswith("ALT/BTC:crypto_spot")
