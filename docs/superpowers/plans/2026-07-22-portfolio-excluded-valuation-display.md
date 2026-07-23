# 排除估值持仓展示 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 行情不可用的实盘持仓仍显示在当前持仓表，并可从汇总卡查看被排除估值的原因。

**Architecture:** `PortfolioService` 在行情网关异常时生成带 `quote_unavailable` 标记的展示项，同时保留 excluded 明细；估值服务只接收行情成功的项目。前端将 positions items 全量传给表格，表格依据标记显示不可用状态；汇总组件将 dashboard.excluded 作为只读明细弹层的数据源。

**Tech Stack:** Python/FastAPI、Vue 3 `<script setup>`、TypeScript、Vitest、Docker Compose。

---

## File structure

- Modify: `app/services/portfolio/portfolio_service.py` — 在单个行情失败时创建不可估值的持仓展示项，并扩展 excluded 明细。
- Modify: `tests/unit/portfolio/test_portfolio_service.py` — 覆盖美股空头行情失败仍返回持仓行且不计入汇总。
- Modify: `frontend/src/api/realTrades.ts` — 为 `PortfolioPosition` 和排除明细声明行情不可用字段。
- Modify: `frontend/src/views/RealTrading/components/PositionTable.vue` — 渲染行情不可用行的 `-` 估值字段和状态。
- Modify: `frontend/src/views/RealTrading/components/PortfolioSummary.vue` — 将非零排除估值数改为可点击按钮，并显示只读原因弹层。
- Modify: `frontend/src/views/RealTrading/index.vue` — 将 dashboard.excluded 传给汇总组件。
- Modify: `frontend/src/views/RealTrading/__tests__/RealTradingPage.test.ts` — 覆盖页面表格和明细弹层的用户行为。

### Task 1: 后端行情不可用展示项

**Files:**
- Modify: `tests/unit/portfolio/test_portfolio_service.py`
- Modify: `app/services/portfolio/portfolio_service.py`

- [ ] **Step 1: 写失败测试**

在现有测试中让行情网关对 AAPL 抛异常、对 MSFT 返回 `Quote(price="100", quote_currency="USD", stale=False)`，并断言行情失败的 AAPL 空头仍在 `items`：

```python
assert [item["symbol"] for item in positions["items"]] == ["AAPL", "MSFT"]
aapl = positions["items"][0]
assert aapl["quote_unavailable"] is True
assert aapl["quote_error"] == "无法获取美股AAPL的行情数据：所有数据源均失败"
assert aapl["mark_price"] is None
assert aapl["base_market_value"] is None
assert aapl["weight_percent"] is None
assert positions["total_market_value"] == "100"
assert positions["excluded"][0]["scope"] == "quote"
assert positions["excluded"][0]["position_side"] == "short"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/unit/portfolio/test_portfolio_service.py::test_quote_failure_excludes_position_instead_of_failing_portfolio -q`

Expected: 当前实现只把 AAPL 放入 `excluded`，因此 `items` 不含 AAPL，断言失败。

- [ ] **Step 3: 实现最小后端逻辑**

在 `PortfolioService.get_positions` 中先读取 `records`，按 `market:exchange:symbol:instrument_type` 建立 `quote_assets` 映射，再重放 records。单独维护 `quote_unavailable_positions`；在行情异常分支构造并追加以下展示项，再追加具备身份字段的 excluded 明细：

```python
quote_unavailable_positions.append({
    "storage_key": state.asset.storage_key,
    "market": state.asset.market.value,
    "exchange": state.asset.exchange,
    "symbol": state.asset.symbol,
    "instrument_type": state.asset.instrument_type.value,
    "position_side": state.position_side.value,
    "quote_asset": quote_assets.get(state.asset.storage_key),
    "quantity": decimal_string(state.quantity),
    "average_entry_price": decimal_string(state.average_entry_price) if state.average_entry_price is not None else None,
    "cost_value": decimal_string(state.cost_value) if state.cost_value is not None else None,
    "realized_pnl": decimal_string(state.realized_pnl) if state.realized_pnl is not None else None,
    "mark_price": None,
    "market_value": None,
    "unrealized_pnl": None,
    "quote_unavailable": True,
    "quote_error": str(exc),
})
excluded.append({
    "scope": "quote",
    "storage_key": state.asset.storage_key,
    "market": state.asset.market.value,
    "exchange": state.asset.exchange,
    "symbol": state.asset.symbol,
    "position_side": state.position_side.value,
    "error": str(exc),
})
```

只把行情成功的 `raw_positions` 传给 `value_positions`，然后将每个 `quote_unavailable_positions` 项补充下列字段并追加到 `valued.positions`：

```python
item.update({
    "converted": False,
    "base_currency": base_currency,
    "base_market_value": None,
    "base_cost_value": None,
    "base_realized_pnl": None,
    "base_unrealized_pnl": None,
    "weight_percent": None,
})
```

最后把行情异常的 excluded 明细追加到 `valued.excluded`。这样总市值、总盈亏和权重只来自可估值项。

- [ ] **Step 4: 运行后端验证**

Run: `python -m pytest tests/unit/portfolio/test_portfolio_service.py::test_quote_failure_excludes_position_instead_of_failing_portfolio -q`

Expected: PASS。

若主机缺少后端依赖，使用 Docker 镜像运行等价的最小复现脚本，确认行情异常后返回 items、excluded 和正确汇总。

- [ ] **Step 5: 提交后端小步**

```bash
git add app/services/portfolio/portfolio_service.py tests/unit/portfolio/test_portfolio_service.py
git commit -m "feat: retain positions with unavailable quotes"
```

### Task 2: 前端类型与持仓状态

**Files:**
- Modify: `frontend/src/api/realTrades.ts`
- Modify: `frontend/src/views/RealTrading/components/PositionTable.vue`
- Modify: `frontend/src/views/RealTrading/__tests__/RealTradingPage.test.ts`

- [ ] **Step 1: 写失败测试**

在 `RealTradingPage.test.ts` 的 mock positions 中加入：

```ts
{
  storage_key: 'US:NASDAQ:AAPL:equity', symbol: 'AAPL', exchange: 'NASDAQ',
  market: 'US', instrument_type: 'equity', position_side: 'short',
  quote_asset: 'USD', quantity: '10', average_entry_price: '100',
  mark_price: null, market_value: null, base_market_value: null,
  base_unrealized_pnl: null, weight_percent: null,
  quote_unavailable: true, quote_error: '所有行情源均失败', converted: false,
}
```

断言页面存在 AAPL、空头、三个 `-` 值以及 `行情不可用`。

- [ ] **Step 2: 运行测试确认失败**

Run: `npm test -- --run src/views/RealTrading/__tests__/RealTradingPage.test.ts`

Expected: FAIL，因为当前表格只显示“未换算”，没有“行情不可用”状态或类型字段。

- [ ] **Step 3: 实现前端类型和渲染**

为 `PortfolioPosition` 添加：

```ts
quote_unavailable?: boolean
quote_error?: string
```

在 `PositionTable.vue` 中创建：

```ts
const unavailable = (position: PortfolioPosition) => position.quote_unavailable === true
```

并令行情不可用时标记价、原币市值、基准币市值、盈亏和权重显示 `-`；状态列优先显示：

```vue
<span v-if="position.quote_unavailable" data-testid="quote-unavailable" class="warning">行情不可用</span>
<span v-else-if="position.converted === false" data-testid="conversion-unavailable" class="warning">未换算</span>
<span v-if="!position.quote_unavailable && position.quote_stale" data-testid="quote-stale" class="muted">行情过期</span>
```

- [ ] **Step 4: 运行前端验证**

Run: `npm test -- --run src/views/RealTrading/__tests__/RealTradingPage.test.ts && npm run type-check`

Expected: 测试通过，`vue-tsc --noEmit` 无类型错误。

- [ ] **Step 5: 提交前端状态小步**

```bash
git add frontend/src/api/realTrades.ts frontend/src/views/RealTrading/components/PositionTable.vue frontend/src/views/RealTrading/__tests__/RealTradingPage.test.ts
git commit -m "feat: display positions with unavailable quotes"
```

### Task 3: 排除估值原因弹层

**Files:**
- Modify: `frontend/src/views/RealTrading/components/PortfolioSummary.vue`
- Modify: `frontend/src/views/RealTrading/index.vue`
- Modify: `frontend/src/views/RealTrading/__tests__/RealTradingPage.test.ts`

- [ ] **Step 1: 写失败测试**

在 dashboard mock 中提供：

```ts
excluded: [{
  scope: 'quote', market: 'US', exchange: 'NASDAQ', symbol: 'AAPL',
  position_side: 'short', error: '所有行情源均失败',
}]
```

断言 `data-testid="excluded-valuation-button"` 显示 `1` 且可点击；点击后断言 `AAPL`、`空头`、`所有行情源均失败` 可见。再添加 `excluded: []` 场景，断言同一按钮禁用。

- [ ] **Step 2: 运行测试确认失败**

Run: `npm test -- --run src/views/RealTrading/__tests__/RealTradingPage.test.ts`

Expected: FAIL，因为汇总组件当前把排除数量渲染为不可点击 `strong`。

- [ ] **Step 3: 实现明细弹层**

在 `PortfolioSummary.vue` 增加 props：

```ts
const props = defineProps<{
  dashboard: PortfolioDashboard
  baseCurrency: BaseCurrency
  excluded: Array<Record<string, unknown>>
}>()
const excludedVisible = ref(false)
```

将排除数量替换成：

```vue
<button
  data-testid="excluded-valuation-button"
  :disabled="!excluded.length"
  @click="excludedVisible = true"
>{{ excluded.length }}</button>
```

渲染 `v-if="excludedVisible"` 的只读弹层，每项用 `symbol || storage_key || '-'`、方向（`short` 显示“空头”）、`market`、`exchange` 与 `error || '-'`。关闭按钮将 `excludedVisible=false`。

在 `index.vue` 中传递：

```vue
<PortfolioSummary
  :dashboard="dashboard"
  :base-currency="baseCurrency"
  :excluded="dashboard.excluded"
  @update:base-currency="changeBaseCurrency"
/>
```

- [ ] **Step 4: 运行前端完整验证**

Run: `npm test -- --run src/views/RealTrading/__tests__/RealTradingPage.test.ts src/views/RealTrading/__tests__/TradeRecordForm.test.ts && npm run type-check && npm run build`

Expected: 所有目标测试通过，类型检查和生产构建通过。

- [ ] **Step 5: 提交前端弹层小步**

```bash
git add frontend/src/views/RealTrading/components/PortfolioSummary.vue frontend/src/views/RealTrading/index.vue frontend/src/views/RealTrading/__tests__/RealTradingPage.test.ts
git commit -m "feat: show excluded valuation reasons"
```

### Task 4: Docker 与浏览器验收

**Files:**
- No source changes expected.

- [ ] **Step 1: 重建服务**

Run:

```bash
docker compose -p tradingagents-cn up -d --build backend frontend
docker compose -p tradingagents-cn ps
```

Expected: backend 和 frontend 为 `healthy`。

- [ ] **Step 2: 验收 AAPL 空头行情失败场景**

在 `http://127.0.0.1:8080/real-trading` 刷新页面，并确认：

1. AAPL 空头仍在当前持仓表。
2. AAPL 标记价、市值、盈亏和权重均为 `-`。
3. 状态为“行情不可用”。
4. 汇总的“排除估值”显示非零且可点击。
5. 点击后显示 AAPL、空头和行情源错误。
6. 其他持仓和组合汇总仍存在。

- [ ] **Step 3: 检查接口与控制台**

Run:

```bash
docker compose -p tradingagents-cn logs --tail=120 backend
```

Expected: `/api/real-trades/positions` 和 `/api/real-trades/dashboard` 返回 200；浏览器控制台没有本次功能相关错误。

- [ ] **Step 4: 最终变更检查与提交**

Run:

```bash
npx gitnexus detect-changes --scope staged --repo "TradingAgents-CN"
git diff --check
git status --short
```

Expected: 变更仅覆盖本计划的实盘持仓文件和测试；High/Critical 风险必须在提交前向用户报告。
