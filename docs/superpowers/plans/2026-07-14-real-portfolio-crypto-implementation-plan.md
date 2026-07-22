# Real Portfolio and Crypto Asset Support Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the current stock-only real-trade journal calculations with a tested multi-asset ledger that reconstructs long and short positions, supports crypto spot and USDT linear perpetuals, and values holdings in a user-selected CNY, USD, or USDT base currency.

**Architecture:** Keep `real_trades` as the source ledger, but move asset normalization, chronological position replay, quotes, FX conversion, and valuation out of the router into focused services under `app/services/portfolio/`. Preserve the existing `/api/real-trades` endpoints through compatibility aliases while the Vue page migrates to Decimal strings and explicit instrument/position semantics. Paper trading remains untouched.

**Tech Stack:** Python 3.10+, FastAPI, Pydantic v2, MongoDB/Motor, Python `Decimal`, CCXT, yfinance, Vue 3 Composition API, TypeScript, Element Plus, decimal.js, ECharts, pytest, Vitest, Vue Test Utils.

---

## File Structure

### Backend files to create

- `app/services/portfolio/__init__.py` — public exports for portfolio services.
- `app/services/portfolio/types.py` — enums, Decimal serializers, asset/ledger/position/quote/value dataclasses.
- `app/services/portfolio/asset_normalizer.py` — canonical `(market, exchange, symbol)` construction and quantity rules.
- `app/services/portfolio/position_calculator.py` — pure chronological long/short/open/close/opening/transfer replay.
- `app/services/portfolio/quote_gateway.py` — normalized CN/HK/US/crypto spot/perpetual quote access.
- `app/services/portfolio/fx_service.py` — trade-time and valuation-time currency conversion.
- `app/services/portfolio/valuation_service.py` — position valuation, base-currency totals, weights, exclusions.
- `app/services/portfolio/ledger_service.py` — persistence, idempotency, optimistic locking, CRUD, filtering.
- `scripts/migration/migrate_real_trades_portfolio_v2.py` — dry-run/apply migration with backup and report.

### Backend files to modify

- `app/models/real_trades.py` — v2 request/response schemas plus v1 aliases.
- `app/routers/real_trades.py` — thin HTTP adapter over portfolio services.
- `app/core/database.py` — v2 indexes and portfolio preference collection.
- `tradingagents/dataflows/providers/crypto/ccxt_provider.py` — normalized ticker and amount precision for spot/swap markets.

### Frontend files to create

- `frontend/src/utils/portfolioDecimal.ts` — Decimal-safe formatting and arithmetic.
- `frontend/src/views/RealTrading/components/TradeRecordForm.vue` — asset-aware record form.
- `frontend/src/views/RealTrading/components/PortfolioSummary.vue` — base-currency selector and summary.
- `frontend/src/views/RealTrading/components/PositionTable.vue` — long/short multi-asset positions.
- `frontend/src/views/RealTrading/components/TradeRecordsDialog.vue` — v2 records and filters.
- `frontend/src/utils/__tests__/portfolioDecimal.test.ts` — Decimal utility tests.
- `frontend/src/views/RealTrading/__tests__/TradeRecordForm.test.ts` — market/instrument/quantity/position controls.
- `frontend/src/views/RealTrading/__tests__/RealTradingPage.test.ts` — preference persistence and selected-base refresh behavior.
- `frontend/src/views/RealTrading/__tests__/PositionTable.test.ts` — long/short separation and unavailable/stale valuation states.

### Frontend files to modify

- `frontend/package.json` and `frontend/package-lock.json` — decimal.js and Vitest test dependencies/scripts.
- `frontend/vite.config.ts` — Vitest jsdom configuration.
- `frontend/src/api/realTrades.ts` — v2 Decimal-string API contract and preference/rules endpoints.
- `frontend/src/views/RealTrading/index.vue` — compose the extracted components and refresh workflow.
- `frontend/src/router/index.ts` and `frontend/src/components/Layout/SidebarMenu.vue` — rename user-facing feature to “实盘持仓”.

### Tests to create

- `tests/unit/portfolio/test_asset_normalizer.py`
- `tests/unit/portfolio/test_position_calculator.py`
- `tests/unit/portfolio/test_fx_service.py`
- `tests/unit/portfolio/test_valuation_service.py`
- `tests/services/test_portfolio_ledger_service.py`
- `tests/routers/test_real_trades_router.py`
- `tests/integration/test_real_portfolio_flow.py`
- `tests/migration/test_migrate_real_trades_portfolio_v2.py`

---

### Task 1: Establish Decimal-safe portfolio domain types

**Files:**
- Create: `app/services/portfolio/__init__.py`
- Create: `app/services/portfolio/types.py`
- Modify: `app/models/real_trades.py`
- Test: `tests/unit/portfolio/test_models.py`

- [ ] **Step 1: Write failing schema tests**

```python
# tests/unit/portfolio/test_models.py
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
```

- [ ] **Step 2: Run the targeted tests and confirm RED**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest -c tests/pytest.ini tests/unit/portfolio/test_models.py -q
```

Expected: FAIL because `CreateLedgerRecordRequest` does not exist.

- [ ] **Step 3: Add domain enums and Decimal helpers**

```python
# app/services/portfolio/types.py
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum
from typing import Optional


ZERO = Decimal("0")


class Market(StrEnum):
    CN = "CN"
    HK = "HK"
    US = "US"
    CRYPTO = "CRYPTO"


class InstrumentType(StrEnum):
    EQUITY = "equity"
    CRYPTO_SPOT = "crypto_spot"
    CRYPTO_LINEAR_PERPETUAL = "crypto_linear_perpetual"


class RecordType(StrEnum):
    TRADE = "trade"
    OPENING_POSITION = "opening_position"
    TRANSFER_IN = "transfer_in"
    TRANSFER_OUT = "transfer_out"


class PositionSide(StrEnum):
    LONG = "long"
    SHORT = "short"


class PositionAction(StrEnum):
    OPEN = "open"
    CLOSE = "close"


class TradeSide(StrEnum):
    BUY = "buy"
    SELL = "sell"


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
        return f"{self.market.value}:{self.exchange}:{self.symbol}:{self.instrument_type.value}"


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
```

- [ ] **Step 4: Replace Pydantic request models with v2 schemas and v1 aliases**

In `app/models/real_trades.py`, define `CreateLedgerRecordRequest` and `UpdateLedgerRecordRequest` with `Decimal` fields, `ConfigDict(json_encoders={Decimal: decimal_string})`, and an `@model_validator(mode="after")` that enforces:

```python
if self.record_type == RecordType.TRADE:
    required = ("side", "position_action", "price")
    missing = [name for name in required if getattr(self, name) is None]
    if missing:
        raise ValueError(f"trade requires: {', '.join(missing)}")

if self.market == Market.CN and self.position_side == PositionSide.SHORT:
    raise ValueError("A-share short positions are not supported")

if self.instrument_type == InstrumentType.CRYPTO_SPOT and self.position_side == PositionSide.SHORT:
    raise ValueError("crypto spot short positions are not supported")

if self.record_type in {RecordType.TRANSFER_IN, RecordType.TRANSFER_OUT}:
    if self.position_side != PositionSide.LONG:
        raise ValueError("transfers are long-only")
    if self.instrument_type == InstrumentType.CRYPTO_LINEAR_PERPETUAL:
        raise ValueError("perpetual positions cannot use transfer records")
```

Keep compatibility properties or aliases for `code`, `trade_date`, and `commission`; do not keep float arithmetic.

- [ ] **Step 5: Run schema tests and existing quick model tests**

```powershell
.\.venv\Scripts\python.exe -m pytest -c tests/pytest.ini tests/unit/portfolio/test_models.py test_real_trades.py -q
```

Expected: PASS. If `test_real_trades.py` is not collected because it is outside `tests/`, run it explicitly as shown.

- [ ] **Step 6: Commit the domain types**

```powershell
git add app/services/portfolio/__init__.py app/services/portfolio/types.py app/models/real_trades.py tests/unit/portfolio/test_models.py
git commit -m "feat: add real portfolio domain types"
```

---

### Task 2: Normalize assets and market-specific quantity rules

**Files:**
- Create: `app/services/portfolio/asset_normalizer.py`
- Test: `tests/unit/portfolio/test_asset_normalizer.py`

- [ ] **Step 1: Write failing normalization tests**

```python
# tests/unit/portfolio/test_asset_normalizer.py
from decimal import Decimal

import pytest

from app.services.portfolio.asset_normalizer import AssetNormalizer


@pytest.mark.parametrize(
    "market,exchange,symbol,instrument,expected",
    [
        ("CN", None, "600519", "equity", ("SSE", "600519")),
        ("CN", None, "000001", "equity", ("SZSE", "000001")),
        ("HK", None, "700", "equity", ("SEHK", "00700")),
        ("US", "NASDAQ", "aapl", "equity", ("NASDAQ", "AAPL")),
        ("CRYPTO", "BINANCE", "btc/usdt", "crypto_spot", ("binance", "BTC/USDT")),
        ("CRYPTO", "binance", "btc/usdt:usdt", "crypto_linear_perpetual", ("binance", "BTC/USDT:USDT")),
    ],
)
def test_normalize_asset(market, exchange, symbol, instrument, expected):
    asset = AssetNormalizer.normalize(market, exchange, symbol, instrument)
    assert (asset.exchange, asset.symbol) == expected


def test_a_share_requires_hundred_unit_quantity():
    rules = AssetNormalizer.quantity_rules("CN", "SSE", "600519", "equity")
    assert rules.step == Decimal("100")
    assert rules.validate(Decimal("200")) is None
    assert rules.validate(Decimal("150")) == "A-share quantity must be a multiple of 100"


def test_crypto_perpetual_allows_decimal_quantity():
    rules = AssetNormalizer.quantity_rules(
        "CRYPTO", "binance", "BTC/USDT:USDT", "crypto_linear_perpetual", precision=5
    )
    assert rules.step == Decimal("0.00001")
    assert rules.validate(Decimal("0.00125")) is None
```

- [ ] **Step 2: Run tests and confirm RED**

```powershell
.\.venv\Scripts\python.exe -m pytest -c tests/pytest.ini tests/unit/portfolio/test_asset_normalizer.py -q
```

Expected: FAIL because `AssetNormalizer` does not exist.

- [ ] **Step 3: Implement canonical asset normalization**

```python
# app/services/portfolio/asset_normalizer.py
from dataclasses import dataclass
from decimal import Decimal
import re

from .types import AssetKey, InstrumentType, Market


SUPPORTED_CRYPTO_EXCHANGES = {"binance", "okx", "bybit", "bitget", "gate"}
SUPPORTED_US_EXCHANGES = {"NASDAQ", "NYSE", "AMEX"}


@dataclass(frozen=True)
class QuantityRules:
    quantity_type: str
    step: Decimal
    minimum: Decimal
    precision: int
    market: Market

    def validate(self, quantity: Decimal) -> str | None:
        if quantity < self.minimum:
            return f"quantity must be at least {self.minimum}"
        if quantity % self.step != 0:
            if self.market == Market.CN:
                return "A-share quantity must be a multiple of 100"
            return f"quantity must align to step {self.step}"
        return None


class AssetNormalizer:
    @staticmethod
    def normalize(market, exchange, symbol, instrument_type) -> AssetKey:
        market = Market(str(market).upper())
        instrument = InstrumentType(str(instrument_type))
        symbol = str(symbol).strip().upper()

        if market == Market.CN:
            if not re.fullmatch(r"\d{6}", symbol):
                raise ValueError("A-share symbol must be 6 digits")
            exchange = "SSE" if symbol.startswith(("5", "6", "9")) else "SZSE"
        elif market == Market.HK:
            symbol = symbol.removesuffix(".HK")
            if not re.fullmatch(r"\d{1,5}", symbol):
                raise ValueError("Hong Kong symbol must be 1-5 digits")
            symbol, exchange = symbol.zfill(5), "SEHK"
        elif market == Market.US:
            exchange = str(exchange or "").upper()
            if exchange not in SUPPORTED_US_EXCHANGES:
                raise ValueError("US exchange must be NASDAQ, NYSE, or AMEX")
            if not re.fullmatch(r"[A-Z][A-Z0-9.-]{0,14}", symbol):
                raise ValueError("invalid US symbol")
        else:
            exchange = str(exchange or "").lower()
            if exchange not in SUPPORTED_CRYPTO_EXCHANGES:
                raise ValueError("unsupported crypto exchange")
            pattern = r"[A-Z0-9]+/[A-Z0-9]+" if instrument == InstrumentType.CRYPTO_SPOT else r"[A-Z0-9]+/[A-Z0-9]+:[A-Z0-9]+"
            if not re.fullmatch(pattern, symbol):
                raise ValueError("invalid crypto symbol for instrument type")

        return AssetKey(market, exchange, symbol, instrument)

    @staticmethod
    def quantity_rules(market, exchange, symbol, instrument_type, precision: int = 0) -> QuantityRules:
        asset = AssetNormalizer.normalize(market, exchange, symbol, instrument_type)
        if asset.market == Market.CN:
            return QuantityRules("integer", Decimal("100"), Decimal("100"), 0, asset.market)
        if asset.instrument_type in {InstrumentType.CRYPTO_SPOT, InstrumentType.CRYPTO_LINEAR_PERPETUAL}:
            step = Decimal(1).scaleb(-precision)
            return QuantityRules("decimal", step, step, precision, asset.market)
        return QuantityRules("integer", Decimal("1"), Decimal("1"), 0, asset.market)
```

- [ ] **Step 4: Run normalization tests**

```powershell
.\.venv\Scripts\python.exe -m pytest -c tests/pytest.ini tests/unit/portfolio/test_asset_normalizer.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit normalization**

```powershell
git add app/services/portfolio/asset_normalizer.py tests/unit/portfolio/test_asset_normalizer.py
git commit -m "feat: normalize portfolio assets and quantities"
```

---

### Task 3: Implement chronological long/short position replay

**Files:**
- Create: `app/services/portfolio/position_calculator.py`
- Test: `tests/unit/portfolio/test_position_calculator.py`

- [ ] **Step 1: Write failing long-position accounting tests**

```python
# tests/unit/portfolio/test_position_calculator.py
from decimal import Decimal

import pytest

from app.services.portfolio.position_calculator import PositionCalculator, PositionError


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
        "quote_asset": "USD",
        "trade_time": "2026-01-01T00:00:00Z",
        "created_at": "2026-01-01T00:00:00Z",
        "_id": "1",
    }
    data.update(overrides)
    return data


def test_long_partial_close_uses_cost_at_close_time():
    result = PositionCalculator.replay([
        record(price="100", quantity="10", fee_amount="10"),
        record(_id="2", trade_time="2026-01-02T00:00:00Z", created_at="2026-01-02T00:00:00Z", price="200", quantity="10"),
        record(_id="3", trade_time="2026-01-03T00:00:00Z", created_at="2026-01-03T00:00:00Z", position_action="close", side="sell", price="180", quantity="5", fee_amount="5"),
    ])[0]

    assert result.quantity == Decimal("15")
    assert result.average_entry_price == Decimal("150.5")
    assert result.realized_pnl == Decimal("142.5")


def test_long_oversell_is_rejected():
    with pytest.raises(PositionError, match="available long quantity"):
        PositionCalculator.replay([
            record(quantity="1"),
            record(_id="2", position_action="close", side="sell", quantity="2"),
        ])
```

- [ ] **Step 2: Add failing short and perpetual tests**

```python
def test_short_partial_close_realizes_inverse_price_move():
    result = PositionCalculator.replay([
        record(market="CRYPTO", exchange="binance", symbol="BTC/USDT:USDT", instrument_type="crypto_linear_perpetual", quote_asset="USDT", position_side="short", side="sell", price="65000", quantity="0.1"),
        record(_id="2", market="CRYPTO", exchange="binance", symbol="BTC/USDT:USDT", instrument_type="crypto_linear_perpetual", quote_asset="USDT", position_side="short", position_action="close", side="buy", price="60000", quantity="0.04", fee_amount="2"),
    ])[0]

    assert result.quantity == Decimal("0.06")
    assert result.realized_pnl == Decimal("198")


def test_perpetual_loss_can_exceed_initial_margin():
    position = PositionCalculator.replay([
        record(market="CRYPTO", exchange="binance", symbol="BTC/USDT:USDT", instrument_type="crypto_linear_perpetual", quote_asset="USDT", position_side="short", side="sell", price="50000", quantity="1", initial_margin="1000"),
    ])[0]

    assert PositionCalculator.unrealized_pnl(position, Decimal("52000")) == Decimal("-2000")
```

- [ ] **Step 3: Run calculator tests and confirm RED**

```powershell
.\.venv\Scripts\python.exe -m pytest -c tests/pytest.ini tests/unit/portfolio/test_position_calculator.py -q
```

Expected: FAIL because calculator does not exist.

- [ ] **Step 4: Implement replay state machine**

Create `PositionCalculator.replay(records)` that:

```python
records = sorted(records, key=lambda item: (item["trade_time"], item.get("created_at", ""), str(item.get("_id", ""))))
states: dict[tuple[str, str], PositionState] = {}

for item in records:
    asset = AssetNormalizer.normalize(item["market"], item.get("exchange"), item["symbol"], item["instrument_type"])
    position_side = PositionSide(item["position_side"])
    state = states.setdefault((asset.storage_key, position_side.value), PositionState(asset=asset, position_side=position_side))
    _apply_record(state, item)
```

Implement separate `_open_long`, `_close_long`, `_open_short`, `_close_short`, `_apply_opening_position`, `_apply_transfer_in`, and `_apply_transfer_out` functions. Use Decimal only. Quote-currency opening fees are embedded into average entry; closing fees reduce realized PnL. Signed funding fees reduce or increase realized PnL without changing quantity.

When `unknown_cost_quantity > 0`, return `average_entry_price=None`, `cost_value=None`, and PnL fields as `None` until the user supplies a cost basis.

- [ ] **Step 5: Run calculator tests**

```powershell
.\.venv\Scripts\python.exe -m pytest -c tests/pytest.ini tests/unit/portfolio/test_position_calculator.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit calculator**

```powershell
git add app/services/portfolio/position_calculator.py tests/unit/portfolio/test_position_calculator.py
git commit -m "feat: calculate long and short portfolio positions"
```

---

### Task 4: Add normalized quote and asset-rule gateway

**Files:**
- Create: `app/services/portfolio/quote_gateway.py`
- Modify: `tradingagents/dataflows/providers/crypto/ccxt_provider.py`
- Test: `tests/unit/portfolio/test_quote_gateway.py`

- [ ] **Step 1: Run required GitNexus impact checks before editing provider symbols**

Run:

```powershell
npx gitnexus impact get_crypto_ticker --repo TradingAgents-CN --direction upstream --depth 3
npx gitnexus impact get_exchange --repo TradingAgents-CN --direction upstream --depth 3
```

Expected: report the direct callers and risk before modifying `CCXTProvider`.

- [ ] **Step 2: Write failing gateway tests with provider mocks**

```python
# tests/unit/portfolio/test_quote_gateway.py
import pytest

from app.services.portfolio.quote_gateway import QuoteGateway


@pytest.mark.asyncio
async def test_crypto_perpetual_quote_is_normalized(monkeypatch):
    class FakeProvider:
        def get_crypto_ticker(self, symbol, exchange):
            assert symbol == "BTC/USDT:USDT"
            return {"last": 65000.12, "timestamp": "2026-07-14T12:00:00Z"}

        def get_market_rules(self, symbol, exchange):
            return {"amount_precision": 5, "min_amount": "0.00001"}

    monkeypatch.setattr("app.services.portfolio.quote_gateway.get_ccxt_provider", lambda: FakeProvider())
    quote = await QuoteGateway().get_quote("CRYPTO", "binance", "BTC/USDT:USDT", "crypto_linear_perpetual")

    assert quote.price == "65000.12"
    assert quote.quote_currency == "USDT"
    assert quote.source == "ccxt"
```

- [ ] **Step 3: Run test and confirm RED**

```powershell
.\.venv\Scripts\python.exe -m pytest -c tests/pytest.ini tests/unit/portfolio/test_quote_gateway.py -q
```

Expected: FAIL because gateway and provider rule method do not exist.

- [ ] **Step 4: Extend CCXT provider without changing existing analysis output**

Add:

```python
def get_market_rules(self, symbol: str, exchange: str = DEFAULT_EXCHANGE) -> Dict:
    ex = self.get_exchange(exchange)
    ex.load_markets()
    market = ex.market(symbol)
    amount_precision = market.get("precision", {}).get("amount")
    if isinstance(amount_precision, int):
        precision = amount_precision
    else:
        precision = max(0, -Decimal(str(amount_precision or "1")).as_tuple().exponent)
    return {
        "amount_precision": precision,
        "price_precision": market.get("precision", {}).get("price"),
        "min_amount": decimal_string(market.get("limits", {}).get("amount", {}).get("min") or Decimal(1).scaleb(-precision)),
        "min_cost": decimal_string(market.get("limits", {}).get("cost", {}).get("min") or 0),
    }
```

Ensure exchange instances include an explicit timeout, for example `timeout=15000`, while preserving `enableRateLimit=True`.

- [ ] **Step 5: Implement QuoteGateway**

`QuoteGateway.get_quote()` delegates:

- CN: `market_quotes`, rejecting missing or stale timestamps.
- HK/US: `ForeignStockService.get_quote()`.
- CRYPTO: `CCXTProvider.get_crypto_ticker()` using `asyncio.to_thread` because CCXT calls are synchronous.

Return a `NormalizedQuote` with Decimal string price, quote currency, source, timestamp, exchange, and stale flag. Add `get_asset_rules()` using the normalizer and CCXT market rules.

- [ ] **Step 6: Run gateway tests**

```powershell
.\.venv\Scripts\python.exe -m pytest -c tests/pytest.ini tests/unit/portfolio/test_quote_gateway.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit quote support**

```powershell
git add app/services/portfolio/quote_gateway.py tradingagents/dataflows/providers/crypto/ccxt_provider.py tests/unit/portfolio/test_quote_gateway.py
git commit -m "feat: add normalized portfolio quote gateway"
```

---

### Task 5: Implement FX conversion and base-currency valuation

**Files:**
- Create: `app/services/portfolio/fx_service.py`
- Create: `app/services/portfolio/valuation_service.py`
- Test: `tests/unit/portfolio/test_fx_service.py`
- Test: `tests/unit/portfolio/test_valuation_service.py`

- [ ] **Step 1: Write failing FX tests**

```python
# tests/unit/portfolio/test_fx_service.py
from datetime import datetime, timezone
from decimal import Decimal

import pytest

from app.services.portfolio.fx_service import FxService


@pytest.mark.asyncio
async def test_same_currency_rate_is_one():
    rate = await FxService().get_rate("USD", "USD", datetime.now(timezone.utc))
    assert rate.rate == Decimal("1")


@pytest.mark.asyncio
async def test_multi_hop_rate_uses_usd(monkeypatch):
    async def fake_direct(source, target, at):
        rates = {("CNY", "USD"): Decimal("0.14"), ("USD", "USDT"): Decimal("0.998")}
        return rates.get((source, target))

    service = FxService()
    monkeypatch.setattr(service, "_get_direct_rate", fake_direct)
    rate = await service.get_rate("CNY", "USDT", datetime.now(timezone.utc))
    assert rate.rate == Decimal("0.13972")
    assert rate.path == ["CNY", "USD", "USDT"]
```

- [ ] **Step 2: Write failing valuation exclusion tests**

```python
# tests/unit/portfolio/test_valuation_service.py
from decimal import Decimal
import pytest

from app.services.portfolio.valuation_service import ValuationService


@pytest.mark.asyncio
async def test_unconverted_position_is_excluded_from_weight(monkeypatch):
    service = ValuationService()
    positions = [
        {"storage_key": "US:NASDAQ:AAPL:equity", "quote_asset": "USD", "market_value": "100", "realized_pnl": "0", "unrealized_pnl": "10"},
        {"storage_key": "CRYPTO:binance:ALT/BTC:crypto_spot", "quote_asset": "BTC", "market_value": "2", "realized_pnl": "0", "unrealized_pnl": "0.1"},
    ]

    async def fake_convert(amount, source, target, at):
        if source == "BTC":
            raise ValueError("no route")
        return Decimal(amount) * Decimal("7")

    monkeypatch.setattr(service, "_convert", fake_convert)
    result = await service.value_positions(positions, "CNY")

    assert result.total_market_value == "700"
    assert result.positions[0]["weight_percent"] == "100"
    assert result.excluded[0]["storage_key"].endswith("ALT/BTC:crypto_spot")
```

- [ ] **Step 3: Run tests and confirm RED**

```powershell
.\.venv\Scripts\python.exe -m pytest -c tests/pytest.ini tests/unit/portfolio/test_fx_service.py tests/unit/portfolio/test_valuation_service.py -q
```

- [ ] **Step 4: Implement FxService with timestamped rates**

Implement `FxService.get_rate(source, target, at)` with:

- identity rate 1;
- direct fiat and USDT rates from yfinance symbols such as `CNY=X`, `USDT-USD` using `asyncio.to_thread`;
- crypto cross rates through CCXT daily candles;
- multi-hop fallback through ordered bridge currencies `USD`, `USDT`, `CNY`;
- result object containing rate, path, source, and timestamp;
- no permanent USD/USDT 1:1 shortcut.

Cache rates in MongoDB collection `portfolio_fx_rates` keyed by `(source, target, rate_date, provider)` so historical trade-time conversion is reproducible.

- [ ] **Step 5: Implement valuation service**

For each position:

```python
converted_market_value = await convert(position.market_value, position.quote_asset, base_currency, valuation_time)
converted_cost = await convert(position.cost_value, position.quote_asset, base_currency, position.cost_rate_time)
base_unrealized_pnl = converted_market_value - converted_cost
```

Convert realized PnL using the rate stored with each closing event. Keep original currency values. Exclude positions with missing quotes or FX routes, return explicit errors, and calculate weights only across included positions.

The history series is cumulative realized PnL only; current unrealized PnL remains a separate summary field.

- [ ] **Step 6: Run FX and valuation tests**

```powershell
.\.venv\Scripts\python.exe -m pytest -c tests/pytest.ini tests/unit/portfolio/test_fx_service.py tests/unit/portfolio/test_valuation_service.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit FX and valuation**

```powershell
git add app/services/portfolio/fx_service.py app/services/portfolio/valuation_service.py tests/unit/portfolio/test_fx_service.py tests/unit/portfolio/test_valuation_service.py
git commit -m "feat: value portfolio in selectable base currency"
```

---

### Task 6: Implement persistent ledger service with idempotency and optimistic locking

**Files:**
- Create: `app/services/portfolio/ledger_service.py`
- Test: `tests/services/test_portfolio_ledger_service.py`

- [ ] **Step 1: Write failing service tests with a fake Motor collection**

Use a `ledger_service` fixture backed by the fake Motor collection and this payload helper:

```python
def trade_payload(**overrides):
    payload = {
        "record_type": "trade",
        "market": "US",
        "exchange": "NASDAQ",
        "symbol": "AAPL",
        "instrument_type": "equity",
        "quote_asset": "USD",
        "side": "buy",
        "position_side": "long",
        "position_action": "open",
        "price": "200",
        "quantity": "2",
        "fee_amount": None,
        "trade_time": "2026-01-01T00:00:00+00:00",
    }
    payload.update(overrides)
    return payload


@pytest.mark.asyncio
async def test_duplicate_idempotency_key_returns_existing_record(ledger_service, records):
    payload = trade_payload(idempotency_key="import-row-1")
    first = await ledger_service.create_record("u1", payload)
    second = await ledger_service.create_record("u1", payload)
    assert second["_id"] == first["_id"]
    assert await records.count_documents({"user_id": "u1"}) == 1

@pytest.mark.asyncio
async def test_update_rejects_stale_version(ledger_service):
    created = await ledger_service.create_record("u1", trade_payload())
    with pytest.raises(VersionConflict) as error:
        await ledger_service.update_record(
            "u1", str(created["_id"]), trade_payload(price="201"), expected_version=0
        )
    assert error.value.current_version == 1

@pytest.mark.asyncio
async def test_create_rejects_close_larger_than_available_short(ledger_service):
    await ledger_service.create_record("u1", trade_payload(
        side="sell", position_side="short", position_action="open", quantity="2"
    ))
    with pytest.raises(PositionConflict) as error:
        await ledger_service.create_record("u1", trade_payload(
            side="buy", position_side="short", position_action="close", quantity="3",
            trade_time="2026-01-02T00:00:00+00:00",
        ))
    assert error.value.available_quantity == Decimal("2")

@pytest.mark.asyncio
async def test_identity_change_replays_old_and_new_assets(ledger_service):
    created = await ledger_service.create_record("u1", trade_payload())
    updated = await ledger_service.update_record(
        "u1",
        str(created["_id"]),
        trade_payload(exchange="NYSE", symbol="IBM", price="250"),
        expected_version=1,
    )
    old_positions = await ledger_service.reconstruct_positions("u1", symbol="AAPL")
    new_positions = await ledger_service.reconstruct_positions("u1", symbol="IBM")
    assert old_positions == []
    assert new_positions[0].quantity == Decimal("2")
    assert updated["version"] == 2
```

The fake collection must implement `find_one`, `find`, `insert_one`, `find_one_and_update`, `delete_one`, `count_documents`, and cursor sort/skip/limit.

- [ ] **Step 2: Run tests and confirm RED**

```powershell
.\.venv\Scripts\python.exe -m pytest -c tests/pytest.ini tests/services/test_portfolio_ledger_service.py -q
```

- [ ] **Step 3: Implement serialization and storage document mapping**

Add helpers:

```python
DECIMAL_FIELDS = {
    "price", "quantity", "gross_amount", "fee_amount", "funding_fee",
    "leverage", "initial_margin", "realized_pnl", "fx_rate",
}

def serialize_document(data: dict) -> dict:
    doc = dict(data)
    for field in DECIMAL_FIELDS:
        if doc.get(field) is not None:
            doc[field] = decimal_string(doc[field])
    return doc
```

- [ ] **Step 4: Implement create flow**

`create_record(user_id, payload)`:

1. Normalize the asset.
2. Compute canonical `storage_key`.
3. If an idempotency key exists, return the existing user-owned record.
4. Load all records for that asset and position side.
5. Replay existing plus proposed record; translate `PositionError` into a domain conflict.
6. Insert with `version=1`, UTC timestamps, canonical fields, and compatibility fields.

- [ ] **Step 5: Implement versioned update/delete**

Update query:

```python
query = {"_id": object_id, "user_id": user_id, "version": expected_version}
update = {"$set": updated_fields, "$inc": {"version": 1}}
```

Validate replay for both original and replacement asset/position-side groups before persisting. Return conflict if the matched document is missing but the ID still exists for the user.

Write an audit document to `real_trade_audit` containing action, record ID, user ID, previous document, new document, and timestamp.

- [ ] **Step 6: Implement filters and chronological record retrieval**

Filter on canonical `symbol`, market, exchange, position side, action, record type, and time range before pagination. Do not apply PnL filtering after pagination; obtain realized-PnL filter data from replayed event results.

- [ ] **Step 7: Run ledger service tests**

```powershell
.\.venv\Scripts\python.exe -m pytest -c tests/pytest.ini tests/services/test_portfolio_ledger_service.py -q
```

Expected: PASS.

- [ ] **Step 8: Commit ledger service**

```powershell
git add app/services/portfolio/ledger_service.py tests/services/test_portfolio_ledger_service.py
git commit -m "feat: add persistent real portfolio ledger"
```

---

### Task 7: Refactor real-trades API around portfolio services

**Files:**
- Modify: `app/routers/real_trades.py`
- Modify: `app/services/portfolio/__init__.py`
- Test: `tests/routers/test_real_trades_router.py`

- [ ] **Step 1: Run GitNexus impact analysis before editing route symbols**

```powershell
npx gitnexus impact create_record --repo TradingAgents-CN --direction upstream --depth 3 --include-tests
npx gitnexus impact "Function:app/routers/real_trades.py:list_positions" --repo TradingAgents-CN --direction upstream --depth 3 --include-tests
npx gitnexus impact get_dashboard --repo TradingAgents-CN --direction upstream --depth 3 --include-tests
```

Report that GitNexus sees `list_positions -> get_dashboard`, while HTTP consumers in `frontend/src/api/realTrades.ts` expand the practical risk to the frontend contract.

- [ ] **Step 2: Write failing router tests**

Use a small FastAPI app with dependency overrides. Test:

```python
def test_create_accepts_v1_aliases_and_returns_v2_fields(client):
    response = client.post("/api/real-trades/record", json={
        "code": "AAPL", "market": "US", "exchange": "NASDAQ",
        "instrument_type": "equity", "currency": "USD", "side": "buy",
        "position_side": "long", "position_action": "open",
        "price": "200", "quantity": "2", "commission": "1.5",
        "trade_date": "2026-01-01T00:00:00+00:00",
    })
    assert response.status_code == 201
    body = response.json()
    assert body["symbol"] == body["code"] == "AAPL"
    assert body["fee_amount"] == body["commission"] == "1.5"


def test_open_short_us_equity_returns_201(client):
    response = client.post("/api/real-trades/record", json=us_short_open_payload())
    assert response.status_code == 201
    assert response.json()["position_side"] == "short"


def test_a_share_short_returns_422(client):
    payload = us_short_open_payload(market="CN", exchange="SSE", symbol="600519", quote_asset="CNY")
    response = client.post("/api/real-trades/record", json=payload)
    assert response.status_code == 422
    assert "long-only" in response.json()["detail"]


def test_stale_version_returns_409(client, existing_record):
    response = client.put(
        f"/api/real-trades/record/{existing_record['_id']}",
        json={**existing_record, "price": "201", "version": 0},
    )
    assert response.status_code == 409
    assert response.json()["current_version"] == 1


def test_positions_accept_base_currency(client):
    response = client.get("/api/real-trades/positions", params={"base_currency": "USDT"})
    assert response.status_code == 200
    assert response.json()["base_currency"] == "USDT"


def test_portfolio_preference_round_trip(client):
    saved = client.put("/api/real-trades/portfolio-preference", json={"base_currency": "USD"})
    loaded = client.get("/api/real-trades/portfolio-preference")
    assert saved.status_code == loaded.status_code == 200
    assert loaded.json()["base_currency"] == "USD"


def test_invalid_object_id_returns_422(client):
    response = client.get("/api/real-trades/record/not-an-object-id")
    assert response.status_code == 422
```

Define `us_short_open_payload(**overrides)` in the test file with `side="sell"`, `position_side="short"`, and `position_action="open"`. The `client` fixture must override authentication and inject deterministic fake ledger, quote, FX, valuation, and preference services; `existing_record` creates one version-1 record through that client.

- [ ] **Step 3: Run router tests and confirm RED**

```powershell
.\.venv\Scripts\python.exe -m pytest -c tests/pytest.ini tests/routers/test_real_trades_router.py -q
```

- [ ] **Step 4: Replace router calculations with injected services**

The router must not calculate average cost or PnL. Endpoints call:

```python
ledger_service.create_record(user["id"], payload)
ledger_service.update_record(user["id"], record_id, payload)
ledger_service.delete_record(user["id"], record_id, expected_version)
portfolio_service.get_positions(user["id"], base_currency)
portfolio_service.get_dashboard(user["id"], base_currency, days)
quote_gateway.get_asset_rules(market, exchange, symbol, instrument_type)
preference_service.get_or_create(user["id"])
preference_service.update(user["id"], base_currency)
```

Map domain validation to 422, oversell/version conflicts to 409, not found to 404, and quote/FX exclusions to successful responses with exclusion metadata.

- [ ] **Step 5: Preserve compatibility response fields**

During the v1 compatibility period, each record includes:

```python
record["code"] = record["symbol"]
record["trade_date"] = record["trade_time"]
record["commission"] = record.get("fee_amount") or "0"
record["currency"] = record["quote_asset"]
record["amount"] = record.get("gross_amount")
```

- [ ] **Step 6: Run router tests**

```powershell
.\.venv\Scripts\python.exe -m pytest -c tests/pytest.ini tests/routers/test_real_trades_router.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit API refactor**

```powershell
git add app/routers/real_trades.py app/services/portfolio/__init__.py tests/routers/test_real_trades_router.py
git commit -m "refactor: route real trades through portfolio services"
```

---

### Task 8: Add indexes, portfolio preferences, and idempotent migration

**Files:**
- Modify: `app/core/database.py`
- Create: `scripts/migration/migrate_real_trades_portfolio_v2.py`
- Test: `tests/migration/test_migrate_real_trades_portfolio_v2.py`

- [ ] **Step 1: Write failing migration tests**

Test dry-run conversion:

```python
def test_convert_legacy_us_buy_to_long_open_trade():
    converted = convert_legacy_record({
        "code": "AAPL", "market": "US", "currency": "USD",
        "side": "buy", "price": 200.0, "quantity": 2,
        "commission": 1.5, "trade_date": "2026-01-01T00:00:00",
    })
    assert converted["symbol"] == "AAPL"
    assert converted["position_side"] == "long"
    assert converted["position_action"] == "open"
    assert converted["price"] == "200.0"
    assert converted["fee_amount"] == "1.5"


def test_ambiguous_oversell_is_reported_not_guessed():
    report = migrate_documents([
        {
            "_id": "sell-1", "user_id": "u1", "code": "AAPL", "market": "US",
            "exchange": "NASDAQ", "currency": "USD", "side": "sell",
            "price": 210.0, "quantity": 3, "trade_date": "2026-01-01T00:00:00+00:00",
        }
    ], apply=False)
    assert report.converted == []
    assert report.errors[0].record_id == "sell-1"
    assert report.errors[0].code == "oversell_requires_opening_position"


def test_second_migration_run_skips_v2_records():
    report = migrate_documents([
        {
            "_id": "v2-1", "user_id": "u1", "schema_version": 2,
            "market": "US", "exchange": "NASDAQ", "symbol": "AAPL",
        }
    ], apply=False)
    assert report.converted == []
    assert report.skipped == ["v2-1"]
    assert report.errors == []
```

- [ ] **Step 2: Run migration tests and confirm RED**

```powershell
.\.venv\Scripts\python.exe -m pytest -c tests/pytest.ini tests/migration/test_migrate_real_trades_portfolio_v2.py -q
```

- [ ] **Step 3: Add database indexes**

In `create_database_indexes()` create:

```python
await real_trades.create_index([("user_id", 1), ("trade_time", -1)])
await real_trades.create_index([("user_id", 1), ("market", 1), ("exchange", 1), ("symbol", 1), ("position_side", 1), ("trade_time", 1)])
await real_trades.create_index(
    [("user_id", 1), ("idempotency_key", 1)],
    unique=True,
    partialFilterExpression={"idempotency_key": {"$type": "string", "$ne": ""}},
)
await real_trades.create_index([("user_id", 1), ("analysis_id", 1)])
await db["portfolio_preferences"].create_index([("user_id", 1)], unique=True)
await db["portfolio_fx_rates"].create_index([("source", 1), ("target", 1), ("rate_date", 1), ("provider", 1)], unique=True)
```

- [ ] **Step 4: Implement migration dry-run and apply modes**

CLI:

```powershell
.\.venv\Scripts\python.exe scripts/migration/migrate_real_trades_portfolio_v2.py --dry-run --report reports/real-trades-v2-migration.json
.\.venv\Scripts\python.exe scripts/migration/migrate_real_trades_portfolio_v2.py --apply --backup-collection real_trades_backup_20260714
```

The script must:

- skip records with `schema_version >= 2`;
- copy every original document to the backup collection before update;
- convert numerics to Decimal strings;
- infer CN/HK exchanges and require explicit US exchange mapping when ambiguous;
- replay each user/asset chronologically;
- place oversells and ambiguous identities in the report without updating them;
- set `schema_version=2` only after successful conversion;
- return non-zero exit code when apply mode has unresolved errors.

- [ ] **Step 5: Run migration tests**

```powershell
.\.venv\Scripts\python.exe -m pytest -c tests/pytest.ini tests/migration/test_migrate_real_trades_portfolio_v2.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit migration and indexes**

```powershell
git add app/core/database.py scripts/migration/migrate_real_trades_portfolio_v2.py tests/migration/test_migrate_real_trades_portfolio_v2.py
git commit -m "feat: migrate real portfolio ledger schema"
```

---

### Task 9: Add frontend Decimal contract and test runner

**Files:**
- Modify: `frontend/package.json`
- Modify: `frontend/package-lock.json`
- Modify: `frontend/vite.config.ts`
- Create: `frontend/src/utils/portfolioDecimal.ts`
- Modify: `frontend/src/api/realTrades.ts`
- Test: `frontend/src/utils/__tests__/portfolioDecimal.test.ts`

- [ ] **Step 1: Add frontend dependencies and test script**

Run from `frontend/`:

```powershell
npm install decimal.js
npm install --save-dev vitest @vue/test-utils jsdom
```

Add package script:

```json
"test": "vitest run"
```

- [ ] **Step 2: Configure Vitest**

In `vite.config.ts`, add:

```ts
test: {
  environment: 'jsdom',
  globals: true,
  include: ['src/**/*.test.ts']
}
```

- [ ] **Step 3: Write failing Decimal utility tests**

```ts
// frontend/src/utils/__tests__/portfolioDecimal.test.ts
import { describe, expect, it } from 'vitest'
import { multiplyDecimal, formatDecimal, quantityStep } from '../portfolioDecimal'

describe('portfolio decimal helpers', () => {
  it('multiplies crypto values without Number rounding', () => {
    expect(multiplyDecimal('65000.1234', '0.00125')).toBe('81.25015425')
  })

  it('returns market quantity steps', () => {
    expect(quantityStep({ market: 'CN', precision: 0 })).toBe('100')
    expect(quantityStep({ market: 'CRYPTO', precision: 5 })).toBe('0.00001')
  })

  it('formats without converting through Number', () => {
    expect(formatDecimal('0.000000123456', 8)).toBe('0.00000012')
  })
})
```

- [ ] **Step 4: Run tests and confirm RED**

```powershell
cd frontend
npm test -- src/utils/__tests__/portfolioDecimal.test.ts
```

- [ ] **Step 5: Implement Decimal utilities**

```ts
// frontend/src/utils/portfolioDecimal.ts
import Decimal from 'decimal.js'

export function multiplyDecimal(a: string, b: string): string {
  return new Decimal(a || '0').mul(new Decimal(b || '0')).toFixed()
}

export function formatDecimal(value: string | null | undefined, precision = 2): string {
  if (value == null || value === '') return '-'
  return new Decimal(value).toDecimalPlaces(precision, Decimal.ROUND_HALF_UP).toFixed(precision)
}

export function quantityStep(rule: { market: string; precision: number }): string {
  if (rule.market === 'CN') return '100'
  if (rule.market === 'CRYPTO') return new Decimal(1).div(new Decimal(10).pow(rule.precision)).toFixed()
  return '1'
}
```

- [ ] **Step 6: Replace API number fields with Decimal strings**

In `frontend/src/api/realTrades.ts`, define unions and v2 fields:

```ts
export type DecimalString = string
export type Market = 'CN' | 'HK' | 'US' | 'CRYPTO'
export type InstrumentType = 'equity' | 'crypto_spot' | 'crypto_linear_perpetual'
export type PositionSide = 'long' | 'short'
export type PositionAction = 'open' | 'close'
export type RecordType = 'trade' | 'opening_position' | 'transfer_in' | 'transfer_out'

export interface CreateLedgerRecordPayload {
  record_type: RecordType
  market: Market
  exchange: string
  symbol: string
  instrument_type: InstrumentType
  quote_asset: string
  side?: 'buy' | 'sell'
  position_side: PositionSide
  position_action?: PositionAction
  price?: DecimalString
  quantity: DecimalString
  fee_amount?: DecimalString
  fee_currency?: string
  funding_fee?: DecimalString
  leverage?: DecimalString
  initial_margin?: DecimalString
  margin_mode?: 'cross' | 'isolated'
  trade_time: string
  version?: number
  reason?: string
  tags?: string[]
  notes?: string | null
}
```

Add API methods for asset rules and portfolio preference, and pass `base_currency` to positions/dashboard.

- [ ] **Step 7: Run frontend tests and type check**

```powershell
cd frontend
npm test -- src/utils/__tests__/portfolioDecimal.test.ts
npm run type-check
```

Expected: PASS.

- [ ] **Step 8: Commit frontend foundation**

```powershell
git add frontend/package.json frontend/package-lock.json frontend/vite.config.ts frontend/src/utils/portfolioDecimal.ts frontend/src/utils/__tests__/portfolioDecimal.test.ts frontend/src/api/realTrades.ts
git commit -m "feat: add decimal-safe real portfolio frontend contract"
```

---

### Task 10: Build asset-aware trade/opening/transfer form

**Files:**
- Create: `frontend/src/views/RealTrading/components/TradeRecordForm.vue`
- Create: `frontend/src/views/RealTrading/__tests__/TradeRecordForm.test.ts`
- Modify: `frontend/src/views/RealTrading/index.vue`

- [ ] **Step 1: Write failing component tests**

Mount with `global.stubs` for Element Plus and mock `realTradesApi.getAssetRules()`. Use stable `data-testid` attributes as the component contract:

```ts
it('shows step 100 and hides short controls for A-shares', async () => {
  const wrapper = mountForm({ market: 'CN', instrument_type: 'equity' })
  await flushPromises()
  expect(wrapper.get('[data-testid="quantity"]').attributes('step')).toBe('100')
  expect(wrapper.find('[data-testid="position-side-short"]').exists()).toBe(false)
})

it('shows short open/close controls for US equities', async () => {
  const wrapper = mountForm({ market: 'US', exchange: 'NASDAQ', instrument_type: 'equity' })
  await flushPromises()
  expect(wrapper.find('[data-testid="position-side-short"]').exists()).toBe(true)
  expect(wrapper.find('[data-testid="position-action-close"]').exists()).toBe(true)
})

it('accepts decimal quantity for crypto perpetuals', async () => {
  const wrapper = mountForm({
    market: 'CRYPTO', exchange: 'binance', symbol: 'BTC/USDT:USDT',
    instrument_type: 'crypto_linear_perpetual', quantity: '0.00125',
  })
  await flushPromises()
  const input = wrapper.get('[data-testid="quantity"]')
  expect(input.attributes('step')).toBe('0.00001')
  expect((input.element as HTMLInputElement).value).toBe('0.00125')
})

it('hides position action for transfer records', async () => {
  const wrapper = mountForm({ record_type: 'transfer_in', market: 'US' })
  await flushPromises()
  expect(wrapper.find('[data-testid="position-action"]').exists()).toBe(false)
  expect(wrapper.find('[data-testid="trade-side"]').exists()).toBe(false)
})

it('keeps fee controls collapsed by default', () => {
  const wrapper = mountForm()
  expect(wrapper.find('[data-testid="fee-amount"]').exists()).toBe(false)
  expect(wrapper.get('[data-testid="advanced-toggle"]').text()).toContain('费用与合约元数据')
})
```

Define `mountForm(initial = {})` in the same test file; it mounts `TradeRecordForm` with `initialValue={...defaultPayload, ...initial}`. Mock `getAssetRules()` to return `{ quantity_type: 'decimal', step: '0.00001', precision: 5, minimum: '0.00001' }` for crypto and the corresponding integer descriptor for equities.

- [ ] **Step 2: Run component tests and confirm RED**

```powershell
cd frontend
npm test -- src/views/RealTrading/__tests__/TradeRecordForm.test.ts
```

- [ ] **Step 3: Implement form state with strings**

Use this initial state:

```ts
const form = reactive<CreateLedgerRecordPayload>({
  record_type: 'trade',
  market: 'CN',
  exchange: 'SSE',
  symbol: '',
  instrument_type: 'equity',
  quote_asset: 'CNY',
  side: 'buy',
  position_side: 'long',
  position_action: 'open',
  price: '',
  quantity: '100',
  fee_amount: '',
  fee_currency: 'CNY',
  trade_time: new Date().toISOString(),
  reason: '',
  tags: [],
  notes: null,
})
```

Input prices and quantities through `el-input` with validation, not `el-input-number`, so values remain Decimal strings.

- [ ] **Step 4: Implement market and instrument behavior**

- CN: auto SSE/SZSE, equity only, long only, quantity 100-step.
- HK: SEHK, equity, long/short, quantity 1-step.
- US: NASDAQ/NYSE/AMEX required, equity, long/short, quantity 1-step.
- CRYPTO spot: exchange required, long only, CCXT spot symbol.
- CRYPTO perpetual: exchange required, long/short, `BASE/QUOTE:SETTLE` symbol.
- Trade: show side, position side, open/close, price.
- Opening position: show position side, price, quantity; hide side/action.
- Transfer: long-only spot/equity, quantity and optional cost basis; hide trade action.

- [ ] **Step 5: Implement optional fee/funding/margin metadata**

Keep fee controls inside a collapsed advanced section. Show funding fee, leverage, initial margin, and margin mode only for linear perpetuals. Clearly state that margin mode is metadata and no liquidation is calculated.

- [ ] **Step 6: Emit v2 payload and integrate into page**

Emit `submit` with Decimal strings. Replace the existing inline add/edit dialog in `RealTrading/index.vue` with `TradeRecordForm`, passing an existing record for edit mode and its `version`.

- [ ] **Step 7: Run component tests and type check**

```powershell
cd frontend
npm test -- src/views/RealTrading/__tests__/TradeRecordForm.test.ts
npm run type-check
```

Expected: PASS.

- [ ] **Step 8: Commit form**

```powershell
git add frontend/src/views/RealTrading/components/TradeRecordForm.vue frontend/src/views/RealTrading/__tests__/TradeRecordForm.test.ts frontend/src/views/RealTrading/index.vue
git commit -m "feat: add multi-asset real portfolio record form"
```

---

### Task 11: Build base-currency summary, long/short positions, and record dialog

**Files:**
- Create: `frontend/src/views/RealTrading/components/PortfolioSummary.vue`
- Create: `frontend/src/views/RealTrading/components/PositionTable.vue`
- Create: `frontend/src/views/RealTrading/components/TradeRecordsDialog.vue`
- Create: `frontend/src/views/RealTrading/__tests__/RealTradingPage.test.ts`
- Create: `frontend/src/views/RealTrading/__tests__/PositionTable.test.ts`
- Modify: `frontend/src/views/RealTrading/index.vue`
- Modify: `frontend/src/router/index.ts`
- Modify: `frontend/src/components/Layout/SidebarMenu.vue`

- [ ] **Step 1: Write failing page and position-table tests**

```ts
// RealTradingPage.test.ts
it('loads the saved base currency before requesting valuations', async () => {
  vi.mocked(realTradesApi.getPortfolioPreference).mockResolvedValue({
    data: { base_currency: 'USDT' },
  } as never)
  const wrapper = mount(RealTradingPage, { global: { stubs: pageStubs } })
  await flushPromises()
  expect(realTradesApi.getPositions).toHaveBeenCalledWith({ base_currency: 'USDT' })
  expect(realTradesApi.getDashboard).toHaveBeenCalledWith({ base_currency: 'USDT', days: 90 })
  expect(wrapper.get('[data-testid="base-currency"]').text()).toContain('USDT')
})

it('persists a changed base currency before refreshing valuations', async () => {
  const wrapper = mount(RealTradingPage, { global: { stubs: pageStubs } })
  await flushPromises()
  await wrapper.get('[data-testid="base-currency"]').trigger('change', { target: { value: 'USD' } })
  await flushPromises()
  const saveOrder = vi.mocked(realTradesApi.updatePortfolioPreference).mock.invocationCallOrder[0]
  const refreshOrder = vi.mocked(realTradesApi.getPositions).mock.invocationCallOrder.at(-1)!
  expect(saveOrder).toBeLessThan(refreshOrder)
  expect(realTradesApi.getPositions).toHaveBeenLastCalledWith({ base_currency: 'USD' })
})

// PositionTable.test.ts
it('renders long and short rows separately for the same canonical asset', () => {
  const wrapper = mount(PositionTable, { props: { positions: [longAapl, shortAapl] } })
  expect(wrapper.findAll('[data-testid="position-row"]')).toHaveLength(2)
  expect(wrapper.text()).toContain('多头')
  expect(wrapper.text()).toContain('空头')
})

it('marks missing FX and stale quotes without assigning a weight', () => {
  const wrapper = mount(PositionTable, { props: { positions: [
    { ...longAapl, converted: false, conversion_error: 'missing USD/CNY route', weight: null },
    { ...shortAapl, quote_stale: true },
  ] } })
  expect(wrapper.get('[data-testid="conversion-unavailable"]').text()).toContain('未换算')
  expect(wrapper.get('[data-testid="quote-stale"]').text()).toContain('行情过期')
  expect(wrapper.get('[data-testid="position-weight"]').text()).toBe('-')
})
```

Define `pageStubs`, `longAapl`, and `shortAapl` as complete deterministic fixtures in the test files. Reset all API mocks in `beforeEach`; mock preference, positions, dashboard, and record-list calls so no network or MongoDB access occurs.

- [ ] **Step 2: Run the new tests and confirm RED**

```powershell
cd frontend
npm test -- src/views/RealTrading/__tests__/RealTradingPage.test.ts src/views/RealTrading/__tests__/PositionTable.test.ts
```

Expected: FAIL because the extracted summary/table components and preference workflow do not exist yet.

- [ ] **Step 3: Implement preference loading and precedence**

On page load:

```ts
const preference = await realTradesApi.getPortfolioPreference()
baseCurrency.value = preference.data.base_currency
await Promise.all([fetchPositions(), fetchDashboard()])
```

When the dropdown changes, persist first, then refresh. Explicit query parameters override the stored preference only for that request; the page always persists the user's selected dropdown value.

- [ ] **Step 4: Implement PortfolioSummary**

Render:

- base currency dropdown: CNY/USD/USDT;
- included holdings market value;
- original and converted realized/unrealized/total PnL;
- holdings count and transaction count;
- disclaimer that uninvested cash is excluded;
- excluded/unconverted/stale position count.

Do not display `total_equity`.

- [ ] **Step 5: Implement PositionTable**

Render canonical asset identity, instrument type, exchange, `long/short`, quantity, average entry, mark price, original market value, converted market value, PnL, and weight. Long and short are separate rows. Use asset-aware links: stock detail only for equities; crypto rows route to analysis with the full symbol and market.

- [ ] **Step 6: Implement TradeRecordsDialog**

Filters include symbol, market, exchange, record type, position side, action, time range, tags, and PnL sign. Display Decimal strings through `portfolioDecimal` helpers. Show compatibility fields nowhere in new UI.

- [ ] **Step 7: Update page composition and charts**

Replace hard-coded yuan chart formatting with the selected base-currency symbol. The line chart uses cumulative realized PnL only; current unrealized PnL remains a summary card. Pie weights use only included positions.

- [ ] **Step 8: Rename navigation label**

Keep the route path `/real-trading` for compatibility, but change page title/menu text to “实盘持仓”.

- [ ] **Step 9: Run frontend verification**

```powershell
cd frontend
npm test
npm run type-check
npm run build
```

Expected: PASS.

- [ ] **Step 10: Commit portfolio UI**

```powershell
git add frontend/src/views/RealTrading/components/PortfolioSummary.vue frontend/src/views/RealTrading/components/PositionTable.vue frontend/src/views/RealTrading/components/TradeRecordsDialog.vue frontend/src/views/RealTrading/__tests__/RealTradingPage.test.ts frontend/src/views/RealTrading/__tests__/PositionTable.test.ts frontend/src/views/RealTrading/index.vue frontend/src/router/index.ts frontend/src/components/Layout/SidebarMenu.vue
git commit -m "feat: add real portfolio valuation interface"
```

---

### Task 12: Add end-to-end backend flow and migration verification

**Files:**
- Create: `tests/integration/test_real_portfolio_flow.py`
- Modify: only a previously planned file when a failing verification proves that file is responsible; run GitNexus upstream impact analysis before changing an existing symbol and add the exact path to the final staging command.

- [ ] **Step 1: Add an integration scenario**

The test uses a disposable Mongo database or fake repository and mocked quote/FX providers:

1. Create an A-share long opening record and reject a 150-share quantity.
2. Create US long and short records for the same symbol without netting them together.
3. Open a BTC USDT perpetual short and close part of it profitably.
4. Record a loss larger than initial margin without liquidation.
5. Switch base currency CNY -> USD -> USDT and verify totals/weights.
6. Edit a historical fill and verify later PnL recalculates.
7. Reject a stale version update.
8. Repeat an idempotent import row and verify no duplicate.
9. Mark a missing-FX position excluded rather than summing it.

- [ ] **Step 2: Run the integration test**

```powershell
.\.venv\Scripts\python.exe -m pytest -c tests/pytest.ini -m integration tests/integration/test_real_portfolio_flow.py -q
```

Expected: PASS.

- [ ] **Step 3: Run all new backend tests**

```powershell
.\.venv\Scripts\python.exe -m pytest -c tests/pytest.ini tests/unit/portfolio tests/services/test_portfolio_ledger_service.py tests/routers/test_real_trades_router.py tests/migration/test_migrate_real_trades_portfolio_v2.py -q
```

Expected: PASS.

- [ ] **Step 4: Run relevant existing tests**

```powershell
.\.venv\Scripts\python.exe -m pytest -c tests/pytest.ini tests/unit/test_stocks_kline_news_api.py tests/test_code_normalization.py -q
.\.venv\Scripts\python.exe test_real_trades.py
```

Expected: PASS after compatibility assertions are updated for v2 aliases.

- [ ] **Step 5: Run frontend verification**

```powershell
cd frontend
npm test
npm run type-check
npm run build
```

Expected: PASS.

- [ ] **Step 6: Run migration dry-run against a database copy**

```powershell
.\.venv\Scripts\python.exe scripts/migration/migrate_real_trades_portfolio_v2.py --dry-run --report reports/real-trades-v2-migration.json
```

Expected: no writes; report lists convertible, ambiguous, and oversell records.

- [ ] **Step 7: Run GitNexus change detection before the final commit**

```powershell
npx gitnexus detect-changes --repo TradingAgents-CN
```

Expected: changes limited to real portfolio services/router/models/database, CCXT rule access, migration, frontend real-portfolio files, dependencies, and tests. Warn before proceeding if GitNexus returns HIGH or CRITICAL.

- [ ] **Step 8: Review the complete diff**

```powershell
git status --short
git diff --check
git diff --stat
```

Confirm paper-trading files are unchanged and pre-existing unrelated crypto analysis edits are not staged accidentally.

- [ ] **Step 9: Stage only the integration test and proven fix files**

```powershell
git add tests/integration/test_real_portfolio_flow.py
# If Steps 2-6 required a fix, append each exact proven file path to this command.
# Never stage a directory and never stage an unrelated pre-existing modified/untracked file.
git diff --cached --name-only
git status --short
```

Expected: the staged list contains `tests/integration/test_real_portfolio_flow.py` plus only exact files changed to resolve a reproduced failure; it contains no paper-trading file and no pre-existing crypto-analysis file.

- [ ] **Step 10: Commit final integration fixes**

```powershell
git commit -m "feat: complete real multi-asset portfolio support"
```

---

## Execution Notes

- Start implementation in an isolated worktree because the current workspace already contains uncommitted crypto-analysis changes.
- Before editing any existing function, class, or method, run the project-required GitNexus upstream impact analysis and report the blast radius.
- Use `apply_patch` for source edits and preserve all unrelated user changes.
- Keep paper-trading routes, collections, API types, and UI unchanged.
- Do not add broker/exchange order execution, cash balances, liquidation, stop loss, or cross/isolated margin accounting.
- Do not use floating-point arithmetic for persisted or calculated financial values.
- Do not infer fees when the user leaves fee fields empty.

## Self-Review Checklist

- Spec coverage: domain identity, Decimal values, quantity rules, long/short, perpetuals, opening positions/transfers, fees, FX, valuation, compatibility, migration, UI, and testing each map to an implementation task.
- Scope: paper trading, cash/net equity, order execution, liquidation, and margin risk remain excluded.
- Type consistency: backend and frontend use `record_type`, `instrument_type`, `position_side`, `position_action`, Decimal strings, and `base_currency` consistently.
- PnL consistency: long and short calculations are chronological; trade-time FX is used for realized PnL and valuation-time FX for current value.
- Safety: idempotency uses a partial unique index; edits use optimistic versions; all persistence includes `user_id`.
- Placeholder scan: the plan contains no unresolved placeholder instructions.
