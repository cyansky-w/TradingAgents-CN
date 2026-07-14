from decimal import Decimal

import pytest

from app.services.portfolio.position_calculator import (
    PositionCalculator,
    PositionError,
)


def record(**overrides):
    data = {
        "record_type": "trade",
        "market": "US",
        "exchange": "NASDAQ",
        "symbol": "AAPL",
        "instrument_type": "equity",
        "position_side": "long",
        "position_action": "open",
        "side": "buy",
        "price": "100",
        "quantity": "10",
        "fee_amount": "0",
        "fee_currency": "USD",
        "quote_asset": "USD",
        "trade_time": "2026-01-01T00:00:00Z",
        "created_at": "2026-01-01T00:00:00Z",
        "_id": "1",
    }
    data.update(overrides)
    return data


def test_long_partial_close_uses_cost_at_close_time():
    result = PositionCalculator.replay(
        [
            record(price="100", quantity="10", fee_amount="10"),
            record(
                _id="2",
                trade_time="2026-01-02T00:00:00Z",
                created_at="2026-01-02T00:00:00Z",
                price="200",
                quantity="10",
            ),
            record(
                _id="3",
                trade_time="2026-01-03T00:00:00Z",
                created_at="2026-01-03T00:00:00Z",
                position_action="close",
                side="sell",
                price="180",
                quantity="5",
                fee_amount="5",
            ),
        ]
    )[0]

    assert result.quantity == Decimal("15")
    assert result.average_entry_price == Decimal("150.5")
    assert result.realized_pnl == Decimal("142.5")


def test_replay_sorts_before_calculating_realized_pnl():
    result = PositionCalculator.replay(
        [
            record(
                _id="2",
                trade_time="2026-01-02T00:00:00Z",
                created_at="2026-01-02T00:00:00Z",
                position_action="close",
                side="sell",
                price="120",
                quantity="5",
            ),
            record(quantity="10", price="100"),
        ]
    )[0]

    assert result.quantity == Decimal("5")
    assert result.realized_pnl == Decimal("100")


def test_long_oversell_is_rejected():
    with pytest.raises(PositionError, match="available long quantity"):
        PositionCalculator.replay(
            [
                record(quantity="1"),
                record(
                    _id="2",
                    position_action="close",
                    side="sell",
                    quantity="2",
                ),
            ]
        )


def test_short_partial_close_realizes_inverse_price_move():
    result = PositionCalculator.replay(
        [
            record(
                market="CRYPTO",
                exchange="binance",
                symbol="BTC/USDT:USDT",
                instrument_type="crypto_linear_perpetual",
                quote_asset="USDT",
                fee_currency="USDT",
                position_side="short",
                side="sell",
                price="65000",
                quantity="0.1",
            ),
            record(
                _id="2",
                market="CRYPTO",
                exchange="binance",
                symbol="BTC/USDT:USDT",
                instrument_type="crypto_linear_perpetual",
                quote_asset="USDT",
                fee_currency="USDT",
                position_side="short",
                position_action="close",
                side="buy",
                price="60000",
                quantity="0.04",
                fee_amount="2",
            ),
        ]
    )[0]

    assert result.quantity == Decimal("0.06")
    assert result.realized_pnl == Decimal("198")


def test_perpetual_loss_can_exceed_initial_margin():
    position = PositionCalculator.replay(
        [
            record(
                market="CRYPTO",
                exchange="binance",
                symbol="BTC/USDT:USDT",
                instrument_type="crypto_linear_perpetual",
                quote_asset="USDT",
                fee_currency="USDT",
                position_side="short",
                side="sell",
                price="50000",
                quantity="1",
                initial_margin="1000",
            )
        ]
    )[0]

    assert PositionCalculator.unrealized_pnl(
        position, Decimal("52000")
    ) == Decimal("-2000")


def test_non_quote_fee_does_not_change_average_entry():
    position = PositionCalculator.replay(
        [record(price="100", quantity="2", fee_amount="0.01", fee_currency="BNB")]
    )[0]
    assert position.average_entry_price == Decimal("100")
    assert position.fee_total == Decimal("0")


def test_opening_position_establishes_cost_without_realized_pnl():
    position = PositionCalculator.replay(
        [
            record(
                record_type="opening_position",
                side=None,
                position_action=None,
                price="80",
                quantity="3",
            )
        ]
    )[0]
    assert position.quantity == Decimal("3")
    assert position.average_entry_price == Decimal("80")
    assert position.realized_pnl == Decimal("0")


def test_transfer_without_cost_marks_position_unknown():
    position = PositionCalculator.replay(
        [
            record(
                record_type="transfer_in",
                side=None,
                position_action=None,
                price=None,
                quantity="2",
            )
        ]
    )[0]
    assert position.quantity == Decimal("2")
    assert position.unknown_cost_quantity == Decimal("2")
    assert position.average_entry_price is None
    assert position.cost_value is None
    assert PositionCalculator.unrealized_pnl(position, Decimal("120")) is None


def test_signed_funding_fee_changes_realized_pnl_only():
    position = PositionCalculator.replay(
        [
            record(
                market="CRYPTO",
                exchange="binance",
                symbol="BTC/USDT:USDT",
                instrument_type="crypto_linear_perpetual",
                quote_asset="USDT",
                fee_currency="USDT",
                funding_fee="-5",
            )
        ]
    )[0]
    assert position.quantity == Decimal("10")
    assert position.average_entry_price == Decimal("100")
    assert position.funding_pnl == Decimal("-5")
    assert position.realized_pnl == Decimal("-5")
