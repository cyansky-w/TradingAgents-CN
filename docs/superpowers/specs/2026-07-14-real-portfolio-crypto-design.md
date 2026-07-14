# Real Portfolio and Crypto Asset Support Design

**Date:** 2026-07-14
**Version:** 1.1
**Status:** Approved scope, pending written-spec review
**Supersedes:** The portfolio accounting and asset-model assumptions in `2026-05-18-real-trading-design.md`

## 1. Purpose

Upgrade the existing real-trading module into a reliable real transaction ledger, position manager, and portfolio analysis system covering A-shares, Hong Kong stocks, US stocks, and USDT-margined linear cryptocurrency perpetuals.

The first release uses manually entered or imported real fills. It does not connect to brokers or exchanges for order execution.

## 2. Scope

### Included

- Manual creation, editing, deletion, and import of real fills.
- Opening positions and asset transfers for portfolios whose complete trade history is unavailable.
- Position reconstruction from chronologically ordered fills.
- Moving weighted-average cost accounting.
- Realized and unrealized profit and loss.
- Long and short positions for Hong Kong stocks, US stocks, and USDT-margined linear crypto perpetuals.
- A-share board-lot validation.
- Unit and precision handling for non-A-share assets.
- Optional commission and fee accounting.
- USDT-margined linear cryptocurrency perpetual identity, quantity precision, quotes, and valuation.
- User-selectable portfolio base currency, initially CNY, USD, and USDT.
- Portfolio valuation, weights, and PnL in the selected base currency.

### Excluded

- Paper trading and all `paper_*` collections or APIs.
- Broker or exchange order execution.
- API key custody for trading accounts.
- Open orders, cancellations, partial fills, or order routing.
- A-share short selling and all cryptocurrency spot trading.
- Coin-margined futures, dated futures, options, and non-linear contracts.
- Margin sufficiency checks, cross-versus-isolated risk behavior, liquidation, auto-deleveraging, and automatic stop loss.
- Broker or exchange cash balances and complete account net-worth accounting.
- Tax calculation and automatic reconstruction of complex broker fee schedules.
- FIFO, LIFO, or user-selectable cost methods in the first release.

## 3. Product Positioning

The current feature named "Real Trading" is a transaction journal and portfolio review tool. The UI should use a name such as "Real Portfolio" or "Transactions and Positions" so it does not imply broker execution.

The system treats user-entered trade records as completed fills, not orders. A fill immediately affects quantity, cost, realized PnL, and portfolio valuation. Opening-position and transfer records affect quantity and cost without pretending that an exchange trade occurred.

The first release is a holdings portfolio, not a complete brokerage or exchange account. It reports asset value and PnL but does not include uninvested cash in total equity.

## 4. Architecture

The current router performs validation, persistence, cost accounting, quote access, and dashboard calculations in one module. The revised design separates these responsibilities:

```text
Real Trades API
  -> Asset Normalizer
  -> Trade Ledger Service
  -> Position Calculator
  -> Quote Gateway
  -> FX Conversion Service
  -> Portfolio Valuation Service
  -> MongoDB
```

### Components

#### Asset Normalizer

Creates a canonical asset identity and validates market-specific symbol rules.

Canonical identity:

```text
(market, exchange, symbol)
```

Examples:

```text
(CN, SSE, 600519)
(HK, SEHK, 00700)
(US, NASDAQ, AAPL)
(CRYPTO, binance, BTC/USDT:USDT)
```

#### Trade Ledger Service

Owns fill validation and persistence. It rejects overselling, applies idempotency, and requests recalculation after historical records change.

#### Position Calculator

Replays fills in ascending trade-time order and calculates quantity, moving average cost, realized PnL, and fees. Positions remain derived data in the first release; MongoDB stores fills as the source of truth.

#### Quote Gateway

Returns a normalized quote containing price, quote currency, source, exchange, and timestamp. It delegates to existing A-share storage, `ForeignStockService`, or CCXT.

#### FX Conversion Service

Converts original-currency values to a user-selected base currency. Conversion results include rate, source, and valuation timestamp.

#### Portfolio Valuation Service

Calculates market value, cost, realized PnL, unrealized PnL, total PnL, and position weight only after converting each amount to the selected base currency.

## 5. Domain Model

### Portfolio Ledger Record

```json
{
  "_id": "ObjectId",
  "user_id": "string",
  "idempotency_key": "optional string",
  "version": 1,
  "record_type": "trade | opening_position | transfer_in | transfer_out",
  "market": "CN | HK | US | CRYPTO",
  "exchange": "SSE | SZSE | SEHK | NASDAQ | NYSE | binance | okx | ...",
  "symbol": "canonical symbol",
  "display_symbol": "user-facing symbol",
  "instrument_type": "equity | crypto_linear_perpetual",
  "base_asset": "optional, e.g. BTC",
  "quote_asset": "CNY | HKD | USD | USDT | BTC | ...",
  "name": "optional display name",
  "side": "optional buy | sell",
  "position_side": "long | short",
  "position_action": "optional open | close",
  "price": "optional Decimal string",
  "quantity": "Decimal string",
  "gross_amount": "Decimal string",
  "fee_amount": "optional Decimal string",
  "fee_currency": "optional currency or asset code",
  "fee_type": "optional commission | exchange | tax | other",
  "funding_fee": "optional Decimal string",
  "leverage": "optional Decimal string",
  "initial_margin": "optional Decimal string",
  "margin_mode": "optional cross | isolated metadata",
  "trade_time": "timezone-aware ISO-8601 timestamp",
  "analysis_id": "optional string",
  "reason": "optional string",
  "tags": ["string"],
  "notes": "optional string",
  "created_at": "UTC timestamp",
  "updated_at": "UTC timestamp"
}
```

Decimal values are serialized as strings at API and persistence boundaries. Calculations use Python `Decimal` with explicit rounding rules.

Field requirements depend on `record_type`:

- `trade` requires side, position side, position action, price, quantity, gross amount, and trade time.
- `opening_position` requires position side, entry price, quantity, and effective time; side and position action are omitted.
- `transfer_in` and `transfer_out` are long-only equity events. They require quantity and effective time, while price is optional cost-basis metadata. They do not apply to perpetual positions.
- `gross_amount` is cash consideration for equities, but notional value for linear perpetual fills.

`margin_mode` is retained only as optional source metadata. It does not change first-release accounting. Leverage and initial margin are optional and are used only for display or margin-return calculations; they do not trigger liquidation or cap losses.

### User Portfolio Preference

```json
{
  "user_id": "string",
  "base_currency": "CNY | USD | USDT",
  "updated_at": "UTC timestamp"
}
```

## 6. Quantity Rules

- A-shares: positive integer quantity and a multiple of 100.
- Hong Kong stocks: positive integer quantity with a UI step of 1 for this release.
- US stocks: positive integer quantity with a UI step of 1 for this release.
- Cryptocurrency linear perpetuals: positive decimal quantity, rounded or rejected according to exchange amount precision.
- The system does not use the term "board lot" outside A-shares in this release.
- A-shares are long-only.
- Hong Kong stocks, US stocks, and crypto linear perpetuals support separate long and short positions.
- Closing more than the reconstructed quantity for the selected position side is rejected.

The frontend obtains a quantity rule descriptor rather than hard-coding `100`:

```json
{
  "quantity_type": "integer | decimal",
  "step": "100 | 1 | 0.000001",
  "precision": 0,
  "minimum": "100"
}
```

## 7. Fee Rules

Fees are optional. When absent, the value is zero and no fee schedule is inferred.

When present:

- Buy fees paid in the quote currency are added to acquisition cost.
- Sell fees paid in the quote currency reduce realized proceeds.
- Fees paid in another currency or asset are retained in the original fee currency and converted to the portfolio base currency for reporting.
- In the first release, non-quote-currency fees do not alter position quantity or moving average cost; this avoids guessing how an exchange deducted the fee asset.
- Unknown fee currencies are reported as unconverted rather than silently discarded.

## 8. Cost and PnL Accounting

The first release uses moving weighted-average cost independently for each canonical asset and position side.

Trade intent is explicit:

```text
open long  = position_side long  + position_action open  + side buy
close long = position_side long  + position_action close + side sell
open short = position_side short + position_action open  + side sell
close short= position_side short + position_action close + side buy
```

A-share records accept only open-long and close-long operations.

For opening or increasing a long position:

```text
new_quantity = old_quantity + buy_quantity
new_cost_value = old_cost_value + gross_amount + applicable_buy_fee
new_average_cost = new_cost_value / new_quantity
```

For closing a long position:

```text
cost_released = current_average_cost * sell_quantity
net_proceeds = gross_amount - applicable_sell_fee
realized_pnl = net_proceeds - cost_released
remaining_quantity = old_quantity - sell_quantity
```

For a short position, opening sells increase short quantity and establish the moving average entry price. Closing buys release short cost and realize:

```text
short_realized_pnl = (average_entry_price - close_price) * close_quantity
                     - applicable_close_fee
```

Unrealized PnL:

```text
long_unrealized_pnl  = (mark_price - average_entry_price) * quantity
short_unrealized_pnl = (average_entry_price - mark_price) * quantity
```

For USDT-margined linear perpetuals, quantity is expressed in base-asset units and PnL is denominated in USDT. Loss may exceed the optional initial margin because liquidation is outside scope.

Funding fees are optional ledger amounts. When supplied, they affect total realized PnL but do not change entry price or position quantity.

Opening-position records establish quantity and average cost without realized PnL. Equity transfer-in records require an explicit cost basis if they should contribute to PnL; otherwise their cost basis is marked unknown. Transfer-out records reduce quantity without being classified as a profitable or losing trade.

Historical records are always replayed by `(trade_time, created_at, _id)`. Editing or deleting a historical record recalculates all later position and PnL results for both the old and new canonical asset and position side when identity fields change.

The system must not calculate historical sell PnL using purchases that occurred after the sell.

## 9. Quotes and Currency Conversion

Normalized quote response:

```json
{
  "market": "CRYPTO",
  "exchange": "binance",
  "symbol": "BTC/USDT:USDT",
  "price": "65000.12",
  "quote_currency": "USDT",
  "source": "ccxt",
  "timestamp": "timezone-aware ISO-8601 timestamp",
  "stale": false
}
```

Portfolio base currency is selected from a dropdown, similar to Binance's display-currency selection. The initial supported choices are CNY, USD, and USDT.

Rules:

- Original-currency values remain visible and are never overwritten.
- Totals and weights use only base-currency values.
- Conversion records include rate, source, and timestamp.
- Buy cost uses the conversion rate at trade time.
- Sell proceeds and realized PnL use the conversion rate at trade time.
- Current market value and unrealized PnL use the conversion rate at valuation time.
- Original-currency cost and PnL remain authoritative and visible.
- Base-currency PnL includes both asset-price movement and FX movement.
- USD and USDT use an actual market conversion rate rather than an assumed permanent 1:1 rate.
- Crypto cross rates may use routes such as `ETH/BTC -> BTC/USDT -> USDT`.
- If no conversion route exists, the position is marked unconverted and excluded from portfolio totals and weights.
- The API returns an explicit list of excluded positions and conversion errors.
- The first-release history chart is cumulative realized PnL in the selected base currency. Current unrealized PnL is displayed separately; historical account net-value reconstruction is outside scope.

## 10. API Design

Existing `/api/real-trades` paths remain available during a compatibility period. Requests may continue to send `code`, `trade_date`, and `commission`; the API maps them to `symbol`, `trade_time`, and quote-currency `fee_amount`. Responses expose both old and new fields during the transition, and the old fields are removed only in a later versioned API.

### Required endpoints

- `POST /record`: create a trade, opening-position, or transfer record.
- `PUT /record/{id}`: update a record using optimistic version checking and recalculate affected results.
- `DELETE /record/{id}`: delete a fill and recalculate affected results.
- `GET /record/{id}`: retrieve one user-owned fill.
- `GET /records`: filter and page fills.
- `GET /positions?base_currency=USDT`: return reconstructed positions and converted valuations.
- `GET /dashboard?base_currency=USDT&days=90`: return portfolio totals and history.
- `GET /asset-rules`: return quantity and precision rules for a canonical asset.
- `GET /portfolio-preference`: return the user's base currency.
- `PUT /portfolio-preference`: update the user's base currency.
- `POST /imports`: import completed fills with per-row success, duplicate, and error results.

### Error behavior

- Invalid IDs return 422 or 404, not 500.
- Closing more than the available long or short quantity returns 409 with available quantity.
- A stale record version returns 409 and the current version.
- Duplicate idempotency keys return the existing result without creating another fill.
- Missing quotes or FX rates do not fail transaction history queries; valuation responses mark affected positions unavailable.
- A malformed crypto symbol or unsupported exchange returns 422.

## 11. Persistence and Indexes

Required indexes:

```text
real_trades: (user_id, trade_time desc)
real_trades: (user_id, market, exchange, symbol, trade_time)
real_trades: (user_id, idempotency_key) partial unique when the key exists and is non-empty
real_trades: (user_id, analysis_id)
portfolio_preferences: (user_id) unique
```

All update, delete, and lookup operations include `user_id`.

Writes use optimistic concurrency through the `version` field. The source ledger remains appendable, but historical edits and deletes are audited with the previous value and user identity.

## 12. Frontend Design

### Transaction form

- Market selector: A-share, Hong Kong, US, cryptocurrency.
- Exchange selector appears when required, especially for crypto.
- Symbol input uses market-aware validation.
- Quantity label is neutral (`Quantity`), not always `Shares` or `Lots`.
- A-share quantity step is 100.
- Hong Kong and US quantity step is 1.
- Crypto quantity supports exchange precision.
- The form explicitly selects long or short and open or close where the instrument supports short positions.
- A-shares hide or disable short-position controls.
- Fee fields are collapsed under an optional advanced section.
- Currency and estimated gross amount update from the selected asset.

### Portfolio page

- Base-currency dropdown persists per user.
- Summary cards display the selected base currency.
- Position rows show original currency and converted base-currency value.
- Unconverted or stale positions are visibly marked.
- Portfolio weights exclude unconverted positions and disclose the exclusion.
- Cryptocurrency rows show exchange and full pair identity.
- Long and short positions appear as separate rows and are never netted into one unsigned quantity.

### Terminology

- Replace hard-coded `stock`, `share`, `yuan`, and `100-share lot` language with asset-aware labels.
- Rename "Real Trading" to a term that reflects transaction recording and portfolio analysis.
- Frontend price, quantity, amount, fee, FX, and PnL calculations use Decimal strings with `decimal.js`, `big.js`, or an equivalent decimal library. JavaScript `number` is used only for bounded chart rendering.

## 13. Migration

Existing records are migrated as follows:

- Rename or map `code` to canonical `symbol`.
- Infer `market`, `exchange`, `asset_type`, and `quote_asset` from existing fields.
- Convert numeric price, quantity, amount, and commission fields to Decimal strings.
- Map `commission` to `fee_amount`, set `fee_currency` to the record currency, and set `fee_type` to `commission`.
- Preserve original records in a migration backup collection or export.
- Reject ambiguous records into a migration report rather than guessing.
- Existing records become long-position trade records. Historical sells that exceed known buys are reported for manual conversion to opening-position or transfer records.
- Recalculate all positions and dashboard values after migration.

The migration is idempotent and supports dry-run mode.

## 14. Testing

### Unit tests

- Canonical identity for every market and exchange.
- A-share 100-unit validation.
- Hong Kong and US unit quantity validation.
- Crypto decimal precision and minimum quantity.
- Moving average cost across buys, partial sells, full exits, and re-entry.
- Fee-present and fee-absent accounting.
- Oversell rejection.
- Long and short opening, partial closing, full closing, and re-entry.
- USDT linear perpetual long and short PnL.
- Loss greater than optional initial margin without automatic liquidation.
- Opening-position and transfer accounting.
- Direct and multi-hop FX conversion.

### Integration tests

- CRUD recalculates positions chronologically.
- Same symbol in different markets or exchanges remains isolated.
- User data isolation.
- Idempotent import and duplicate detection.
- Missing quote and missing FX behavior.
- Base-currency switching among CNY, USD, and USDT.
- Trade-time FX for realized PnL and valuation-time FX for unrealized PnL.
- Invalid ObjectId handling.

### Frontend tests

- Dynamic quantity step and precision.
- Long/short and open/close controls by instrument type.
- Optional fee controls.
- Base-currency persistence and display.
- Crypto exchange and pair rendering.
- Unconverted and stale valuation states.

## 15. Acceptance Criteria

- A user can record A-share, Hong Kong, US, and USDT linear perpetual fills in one real portfolio.
- A user can record long and short Hong Kong, US, and USDT linear perpetual positions.
- A-shares remain long-only.
- A-share quantities enforce multiples of 100; other supported assets do not inherit this rule.
- Crypto quantities preserve exchange-compatible decimal precision.
- Positions and realized PnL are reconstructed correctly from chronological fills.
- Opening positions and transfers allow an existing real portfolio to be introduced without complete historical trades.
- Optional fees affect cost and PnL only when supplied.
- The user can select CNY, USD, or USDT as portfolio base currency.
- Portfolio totals and weights never add different currencies without conversion.
- Missing quotes or rates are disclosed and excluded rather than replaced with misleading values.
- The portfolio reports holdings value rather than claiming complete account equity because cash balances are outside scope.
- Perpetual losses may exceed optional initial margin, and no liquidation or cross/isolated risk simulation occurs.
- Paper trading remains unchanged.
- No broker or exchange order execution is introduced.
