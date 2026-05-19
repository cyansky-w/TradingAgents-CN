"""
实盘交易记录数据模型
"""
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field
from bson import ObjectId
from app.models.user import PyObjectId


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
