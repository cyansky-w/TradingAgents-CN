"""
实盘交易记录数据模型
"""
from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel, Field, model_validator
from bson import ObjectId
from app.models.user import PyObjectId
from app.services.portfolio.asset_normalizer import AssetNormalizer
from app.services.portfolio.types import (
    FeeType,
    InstrumentType,
    MarginMode,
    Market,
    PositionAction,
    PositionSide,
    RecordType,
    TradeSide,
)


DECIMAL_RELATIVE_TOLERANCE = Decimal("1e-18")


def _decimal_close(actual: Decimal, expected: Decimal) -> bool:
    scale = max(abs(actual), abs(expected), Decimal("1"))
    return abs(actual - expected) <= scale * DECIMAL_RELATIVE_TOLERANCE


class LedgerRecordBase(BaseModel):
    record_type: RecordType
    market: Market
    exchange: str = Field(min_length=1)
    symbol: str = Field(min_length=1)
    display_symbol: Optional[str] = None
    instrument_type: InstrumentType
    base_asset: Optional[str] = None
    quote_asset: str = Field(min_length=1)
    name: Optional[str] = None
    side: Optional[TradeSide] = None
    position_side: PositionSide
    position_action: Optional[PositionAction] = None
    price: Optional[Decimal] = Field(default=None, gt=0)
    quantity: Decimal = Field(gt=0)
    gross_amount: Optional[Decimal] = Field(default=None, ge=0)
    fee_amount: Optional[Decimal] = Field(default=None, ge=0)
    fee_currency: Optional[str] = None
    fee_type: Optional[FeeType] = None
    funding_fee: Optional[Decimal] = None
    leverage: Optional[Decimal] = Field(default=None, gt=0)
    initial_margin: Optional[Decimal] = Field(default=None, ge=0)
    order_notional: Optional[Decimal] = Field(default=None, ge=0)
    margin_mode: Optional[MarginMode] = None
    trade_time: datetime
    analysis_id: Optional[str] = None
    reason: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    notes: Optional[str] = None

    @model_validator(mode="after")
    def validate_record_semantics(self):
        if (
            self.market != Market.CRYPTO
            and self.instrument_type != InstrumentType.EQUITY
        ):
            raise ValueError("non-crypto markets require equity instruments")

        asset = AssetNormalizer.normalize(
            self.market,
            self.exchange,
            self.symbol,
            self.instrument_type,
        )
        self.market = asset.market
        self.exchange = asset.exchange
        self.symbol = asset.symbol
        self.instrument_type = asset.instrument_type

        if asset.market == Market.CRYPTO:
            if asset.instrument_type != InstrumentType.CRYPTO_LINEAR_PERPETUAL:
                raise ValueError("v1 supports USDT linear perpetuals only")
            pair_quote = asset.symbol.split("/", 1)[1].split(":", 1)[0]
            settlement = asset.symbol.rsplit(":", 1)[1]
            if pair_quote != "USDT" or settlement != "USDT":
                raise ValueError("v1 supports USDT linear perpetuals only")
            expected_quote_asset = pair_quote
        else:
            expected_quote_asset = {
                Market.CN: "CNY",
                Market.HK: "HKD",
                Market.US: "USD",
            }[asset.market]
        if self.quote_asset.upper() != expected_quote_asset:
            raise ValueError(
                f"quote_asset must be {expected_quote_asset} for {asset.symbol}"
            )
        self.quote_asset = expected_quote_asset
        if self.fee_currency:
            self.fee_currency = self.fee_currency.upper()

        if self.record_type == RecordType.TRADE:
            required = ("side", "position_action", "price")
            missing = [name for name in required if getattr(self, name) is None]
            if missing:
                raise ValueError(f"trade requires: {', '.join(missing)}")

        if self.record_type == RecordType.OPENING_POSITION and self.price is None:
            raise ValueError("opening_position requires: price")

        if self.market == Market.CN and self.position_side == PositionSide.SHORT:
            raise ValueError("A-share short positions are not supported")

        if self.instrument_type == InstrumentType.EQUITY:
            quantity_error = AssetNormalizer.quantity_rules(
                asset.market,
                asset.exchange,
                asset.symbol,
                asset.instrument_type,
            ).validate(self.quantity)
            if quantity_error:
                raise ValueError(quantity_error)

        if self.record_type in {RecordType.TRANSFER_IN, RecordType.TRANSFER_OUT}:
            if self.position_side != PositionSide.LONG:
                raise ValueError("transfers are long-only")
            if self.instrument_type == InstrumentType.CRYPTO_LINEAR_PERPETUAL:
                raise ValueError("perpetual positions cannot use transfer records")

        is_perpetual_open = (
            self.instrument_type == InstrumentType.CRYPTO_LINEAR_PERPETUAL
            and self.record_type == RecordType.TRADE
            and self.position_action == PositionAction.OPEN
        )
        perpetual_values = (self.order_notional, self.leverage, self.initial_margin)
        if is_perpetual_open and any(value is not None for value in perpetual_values):
            if any(value is None for value in perpetual_values):
                raise ValueError(
                    "perpetual open requires order_notional, leverage and initial_margin together"
                )
            expected_notional = self.price * self.quantity
            if not _decimal_close(self.order_notional, expected_notional):
                raise ValueError("order_notional must equal price multiplied by quantity")
            if not _decimal_close(
                self.initial_margin * self.leverage, self.order_notional
            ):
                raise ValueError("initial_margin multiplied by leverage must equal order_notional")

        return self


class CreateLedgerRecordRequest(LedgerRecordBase):
    idempotency_key: Optional[str] = None


class UpdateLedgerRecordRequest(LedgerRecordBase):
    version: int = Field(ge=1)


class CreateTradeRequest(BaseModel):
    code: str = Field(..., description="股票代码")
    market: Optional[str] = Field(None, description="市场 CN/HK/US，不传则自动识别")
    side: str = Field(..., pattern="^(buy|sell)$", description="buy/sell")
    price: float = Field(..., gt=0, description="成交单价")
    quantity: int = Field(..., gt=0, description="数量(股)")
    commission: float = Field(0.0, ge=0, description="手续费")
    trade_date: datetime = Field(..., description="实际交易时间")
    reason: str = Field(..., min_length=1, description="交易原因")
    tags: List[str] = Field(default_factory=list, description="标签")
    notes: Optional[str] = Field(None, description="备注")


class UpdateTradeRequest(BaseModel):
    code: Optional[str] = None
    market: Optional[str] = None
    side: Optional[str] = Field(None, pattern="^(buy|sell)$")
    price: Optional[float] = Field(None, gt=0)
    quantity: Optional[int] = Field(None, gt=0)
    commission: Optional[float] = Field(None, ge=0)
    trade_date: Optional[datetime] = None
    reason: Optional[str] = Field(None, min_length=1)
    tags: Optional[List[str]] = None
    notes: Optional[str] = None


class PositionItem(BaseModel):
    code: str
    market: str
    currency: str
    name: Optional[str] = None
    quantity: int
    avg_cost: float
    total_cost: float
    last_price: Optional[float] = None
    market_value: float
    unrealized_pnl: Optional[float] = None
    pnl_percent: Optional[float] = None
    weight_percent: Optional[float] = None


class TradeRecord(BaseModel):
    id: str
    code: str
    market: str
    currency: str
    name: Optional[str] = None
    side: str
    price: float
    quantity: int
    amount: float
    commission: float
    trade_date: str
    reason: str
    tags: List[str]
    notes: Optional[str] = None
    created_at: str
    updated_at: str


class DashboardData(BaseModel):
    total_equity: Optional[float] = None
    total_cost: float
    total_pnl: float
    realized_pnl: float
    unrealized_pnl: float
    win_rate: float
    profit_loss_ratio: float
    holding_count: int
    total_trade_count: int
    pnl_curve: List[dict]
    sector_distribution: List[dict]
