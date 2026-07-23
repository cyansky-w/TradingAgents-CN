from __future__ import annotations

from decimal import Decimal
from typing import Iterable, Mapping, Optional

from app.services.portfolio.asset_normalizer import AssetNormalizer
from app.services.portfolio.types import (
    PositionAction,
    PositionSide,
    PositionState,
    RecordType,
    TradeSide,
    ZERO,
)


class PositionError(ValueError):
    def __init__(self, message: str, available_quantity: Optional[Decimal] = None):
        super().__init__(message)
        self.available_quantity = available_quantity


def _decimal(value, default: Decimal = ZERO) -> Decimal:
    if value is None or value == "":
        return default
    return Decimal(str(value))


def _quote_fee(item: Mapping) -> Decimal:
    fee = _decimal(item.get("fee_amount"))
    if fee == ZERO:
        return ZERO
    fee_currency = str(item.get("fee_currency") or item.get("quote_asset") or "")
    quote_asset = str(item.get("quote_asset") or "")
    return fee if fee_currency.upper() == quote_asset.upper() else ZERO


def _entry_notional(item: Mapping) -> Decimal:
    order_notional = item.get("order_notional")
    if order_notional not in {None, ""}:
        return _decimal(order_notional)
    return _decimal(item["price"]) * _decimal(item["quantity"])


def _require_available(
    state: PositionState,
    quantity: Decimal,
    label: str,
) -> None:
    if quantity > state.quantity:
        raise PositionError(
            f"close quantity exceeds available {label} quantity {state.quantity}",
            available_quantity=state.quantity,
        )


def _reset_closed_state(state: PositionState) -> None:
    state.quantity = ZERO
    state.average_entry_price = None
    state.cost_value = ZERO
    state.unknown_cost_quantity = ZERO


def _open_long(state: PositionState, item: Mapping) -> None:
    quantity = _decimal(item["quantity"])
    price = _decimal(item["price"])
    fee = _quote_fee(item)
    old_quantity = state.quantity
    new_quantity = old_quantity + quantity

    if state.cost_value is None or state.unknown_cost_quantity > ZERO:
        state.quantity = new_quantity
        state.average_entry_price = None
        state.cost_value = None
    else:
        new_cost = state.cost_value + _entry_notional(item) + fee
        state.quantity = new_quantity
        state.cost_value = new_cost
        state.average_entry_price = new_cost / new_quantity
    state.fee_total += fee


def _close_long(state: PositionState, item: Mapping) -> None:
    quantity = _decimal(item["quantity"])
    _require_available(state, quantity, "long")
    fee = _quote_fee(item)

    if state.cost_value is None or state.average_entry_price is None:
        state.quantity -= quantity
        state.unknown_cost_quantity = max(
            ZERO, state.unknown_cost_quantity - quantity
        )
        state.realized_pnl = None
        state.fee_total += fee
        if state.quantity == ZERO:
            _reset_closed_state(state)
        return

    cost_released = state.average_entry_price * quantity
    net_proceeds = _decimal(item["price"]) * quantity - fee
    state.realized_pnl = (state.realized_pnl or ZERO) + net_proceeds - cost_released
    state.quantity -= quantity
    state.cost_value -= cost_released
    state.fee_total += fee
    if state.quantity == ZERO:
        _reset_closed_state(state)


def _open_short(state: PositionState, item: Mapping) -> None:
    quantity = _decimal(item["quantity"])
    price = _decimal(item["price"])
    fee = _quote_fee(item)
    new_quantity = state.quantity + quantity

    if state.cost_value is None or state.unknown_cost_quantity > ZERO:
        state.quantity = new_quantity
        state.average_entry_price = None
        state.cost_value = None
    else:
        new_entry_value = state.cost_value + _entry_notional(item) - fee
        state.quantity = new_quantity
        state.cost_value = new_entry_value
        state.average_entry_price = new_entry_value / new_quantity
    state.fee_total += fee


def _close_short(state: PositionState, item: Mapping) -> None:
    quantity = _decimal(item["quantity"])
    _require_available(state, quantity, "short")
    fee = _quote_fee(item)

    if state.cost_value is None or state.average_entry_price is None:
        state.quantity -= quantity
        state.unknown_cost_quantity = max(
            ZERO, state.unknown_cost_quantity - quantity
        )
        state.realized_pnl = None
        state.fee_total += fee
        if state.quantity == ZERO:
            _reset_closed_state(state)
        return

    entry_released = state.average_entry_price * quantity
    close_cost = _decimal(item["price"]) * quantity
    state.realized_pnl = (
        (state.realized_pnl or ZERO) + entry_released - close_cost - fee
    )
    state.quantity -= quantity
    state.cost_value -= entry_released
    state.fee_total += fee
    if state.quantity == ZERO:
        _reset_closed_state(state)


def _apply_opening_position(state: PositionState, item: Mapping) -> None:
    opening = dict(item)
    opening["fee_amount"] = "0"
    if state.position_side == PositionSide.LONG:
        _open_long(state, opening)
    else:
        _open_short(state, opening)


def _apply_transfer_in(state: PositionState, item: Mapping) -> None:
    if state.position_side != PositionSide.LONG:
        raise PositionError("transfers are long-only")

    quantity = _decimal(item["quantity"])
    if item.get("price") is None:
        state.quantity += quantity
        state.unknown_cost_quantity += quantity
        state.average_entry_price = None
        state.cost_value = None
        return

    transfer = dict(item)
    transfer["fee_amount"] = "0"
    _open_long(state, transfer)


def _apply_transfer_out(state: PositionState, item: Mapping) -> None:
    if state.position_side != PositionSide.LONG:
        raise PositionError("transfers are long-only")

    quantity = _decimal(item["quantity"])
    _require_available(state, quantity, "long")
    if state.cost_value is None or state.average_entry_price is None:
        state.quantity -= quantity
        state.unknown_cost_quantity = max(
            ZERO, state.unknown_cost_quantity - quantity
        )
        if state.quantity == ZERO:
            _reset_closed_state(state)
        return

    state.quantity -= quantity
    state.cost_value -= state.average_entry_price * quantity
    if state.quantity == ZERO:
        _reset_closed_state(state)


def _apply_trade(state: PositionState, item: Mapping) -> None:
    action = PositionAction(item["position_action"])
    side = TradeSide(item["side"])

    if state.position_side == PositionSide.LONG:
        expected = TradeSide.BUY if action == PositionAction.OPEN else TradeSide.SELL
        if side != expected:
            raise PositionError(f"{action.value} long requires side {expected.value}")
        (_open_long if action == PositionAction.OPEN else _close_long)(state, item)
    else:
        expected = TradeSide.SELL if action == PositionAction.OPEN else TradeSide.BUY
        if side != expected:
            raise PositionError(f"{action.value} short requires side {expected.value}")
        (_open_short if action == PositionAction.OPEN else _close_short)(state, item)


def _apply_record(state: PositionState, item: Mapping) -> None:
    record_type = RecordType(item["record_type"])
    if record_type == RecordType.TRADE:
        _apply_trade(state, item)
    elif record_type == RecordType.OPENING_POSITION:
        _apply_opening_position(state, item)
    elif record_type == RecordType.TRANSFER_IN:
        _apply_transfer_in(state, item)
    else:
        _apply_transfer_out(state, item)

    funding = _decimal(item.get("funding_fee"))
    if funding != ZERO:
        state.funding_pnl += funding
        if state.realized_pnl is not None:
            state.realized_pnl += funding


class PositionCalculator:
    @staticmethod
    def replay(records: Iterable[Mapping]) -> list[PositionState]:
        ordered_records = sorted(
            records,
            key=lambda item: (
                item["trade_time"],
                item.get("created_at", ""),
                str(item.get("_id", "")),
            ),
        )
        states: dict[tuple[str, str], PositionState] = {}

        for item in ordered_records:
            asset = AssetNormalizer.normalize(
                item["market"],
                item.get("exchange"),
                item["symbol"],
                item["instrument_type"],
            )
            position_side = PositionSide(item["position_side"])
            key = (asset.storage_key, position_side.value)
            state = states.setdefault(
                key,
                PositionState(asset=asset, position_side=position_side),
            )
            _apply_record(state, item)

        return list(states.values())

    @staticmethod
    def unrealized_pnl(
        position: PositionState,
        mark_price: Decimal,
    ) -> Optional[Decimal]:
        if position.average_entry_price is None or position.cost_value is None:
            return None
        if position.position_side == PositionSide.LONG:
            return (mark_price - position.average_entry_price) * position.quantity
        return (position.average_entry_price - mark_price) * position.quantity
