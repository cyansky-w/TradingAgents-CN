from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import Optional


ZERO = Decimal("0")


class StringEnum(str, Enum):
    def __str__(self) -> str:
        return self.value


class Market(StringEnum):
    CN = "CN"
    HK = "HK"
    US = "US"
    CRYPTO = "CRYPTO"


class InstrumentType(StringEnum):
    EQUITY = "equity"
    CRYPTO_SPOT = "crypto_spot"
    CRYPTO_LINEAR_PERPETUAL = "crypto_linear_perpetual"


class RecordType(StringEnum):
    TRADE = "trade"
    OPENING_POSITION = "opening_position"
    TRANSFER_IN = "transfer_in"
    TRANSFER_OUT = "transfer_out"


class PositionSide(StringEnum):
    LONG = "long"
    SHORT = "short"


class PositionAction(StringEnum):
    OPEN = "open"
    CLOSE = "close"


class TradeSide(StringEnum):
    BUY = "buy"
    SELL = "sell"


class FeeType(StringEnum):
    COMMISSION = "commission"
    EXCHANGE = "exchange"
    TAX = "tax"
    OTHER = "other"


class MarginMode(StringEnum):
    CROSS = "cross"
    ISOLATED = "isolated"


def decimal_string(value: Decimal | str | int) -> str:
    return format(Decimal(str(value)), "f")


@dataclass(frozen=True)
class AssetKey:
    market: Market
    exchange: str
    symbol: str
    instrument_type: InstrumentType

    @property
    def storage_key(self) -> str:
        return (
            f"{self.market.value}:{self.exchange}:{self.symbol}:"
            f"{self.instrument_type.value}"
        )


@dataclass
class PositionState:
    asset: AssetKey
    position_side: PositionSide
    quantity: Decimal = ZERO
    average_entry_price: Optional[Decimal] = None
    cost_value: Optional[Decimal] = ZERO
    realized_pnl: Optional[Decimal] = ZERO
    funding_pnl: Decimal = ZERO
    fee_total: Decimal = ZERO
    unknown_cost_quantity: Decimal = ZERO
