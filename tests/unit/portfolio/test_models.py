from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.models.real_trades import CreateLedgerRecordRequest


def test_crypto_perpetual_trade_keeps_decimal_strings():
    payload = CreateLedgerRecordRequest(
        record_type="trade",
        market="CRYPTO",
        exchange="binance",
        symbol="BTC/USDT:USDT",
        instrument_type="crypto_linear_perpetual",
        quote_asset="USDT",
        side="sell",
        position_side="short",
        position_action="open",
        price="65000.1234",
        quantity="0.00125",
        trade_time="2026-07-14T12:00:00Z",
    )

    assert payload.price == Decimal("65000.1234")
    assert payload.quantity == Decimal("0.00125")
    assert payload.model_dump(mode="json")["quantity"] == "0.00125"


def test_transfer_does_not_require_trade_side():
    payload = CreateLedgerRecordRequest(
        record_type="transfer_in",
        market="CRYPTO",
        exchange="binance",
        symbol="BTC/USDT",
        instrument_type="crypto_spot",
        quote_asset="USDT",
        position_side="long",
        quantity="0.5",
        trade_time="2026-07-14T12:00:00Z",
    )

    assert payload.side is None
    assert payload.position_action is None


def test_trade_rejects_missing_action():
    with pytest.raises(ValidationError, match="position_action"):
        CreateLedgerRecordRequest(
            record_type="trade",
            market="US",
            exchange="NASDAQ",
            symbol="AAPL",
            instrument_type="equity",
            quote_asset="USD",
            side="buy",
            position_side="long",
            price="200",
            quantity="1",
            trade_time="2026-07-14T12:00:00Z",
        )


def test_a_share_rejects_short_position():
    with pytest.raises(ValidationError, match="A-share short"):
        CreateLedgerRecordRequest(
            record_type="trade",
            market="CN",
            exchange="SSE",
            symbol="600519",
            instrument_type="equity",
            quote_asset="CNY",
            side="sell",
            position_side="short",
            position_action="open",
            price="1500",
            quantity="100",
            trade_time="2026-07-14T12:00:00Z",
        )


def test_crypto_spot_rejects_short_position():
    with pytest.raises(ValidationError, match="crypto spot short"):
        CreateLedgerRecordRequest(
            record_type="trade",
            market="CRYPTO",
            exchange="binance",
            symbol="BTC/USDT",
            instrument_type="crypto_spot",
            quote_asset="USDT",
            side="sell",
            position_side="short",
            position_action="open",
            price="65000",
            quantity="0.1",
            trade_time="2026-07-14T12:00:00Z",
        )


def test_perpetual_rejects_transfer_record():
    with pytest.raises(ValidationError, match="perpetual positions cannot use transfer"):
        CreateLedgerRecordRequest(
            record_type="transfer_in",
            market="CRYPTO",
            exchange="binance",
            symbol="BTC/USDT:USDT",
            instrument_type="crypto_linear_perpetual",
            quote_asset="USDT",
            position_side="long",
            quantity="0.1",
            trade_time="2026-07-14T12:00:00Z",
        )
