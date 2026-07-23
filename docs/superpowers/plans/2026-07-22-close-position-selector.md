# 实盘平仓持仓选择 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 新增实盘成交记录选择“平仓”时，先按市场筛选并选择当前持仓，展示可平数量，允许用户输入不超过当前持仓的部分平仓数量。

**Architecture:** 复用 `RealTrading/index.vue` 已加载的 `PortfolioPosition[]`，通过 props 传给 `TradeRecordForm`。新增纯函数模块负责持仓唯一键、市场筛选、标签和数量上限校验；表单使用已安装的 shadcn-vue Select 展示持仓并回填账本字段，后端继续通过现有 PositionCalculator 做最终并发一致性校验。

**Tech Stack:** Vue 3、TypeScript、Pinia 项目 API 层、shadcn-vue Select、Reka UI、Decimal.js、Vitest、Vue Test Utils、Docker Compose、GitNexus。

---

## 文件结构

- Create: `frontend/src/views/RealTrading/closePositionSelection.ts`
  - 只负责持仓选择的纯数据逻辑，不访问 Vue 状态或 API。
- Create: `frontend/src/views/RealTrading/__tests__/closePositionSelection.test.ts`
  - 覆盖市场筛选、多空唯一键、显示标签和数量上限校验。
- Modify: `frontend/src/views/RealTrading/index.vue`
  - 将页面已有的 `positions` 传入表单；处理并发导致的可平数量变化提示。
- Modify: `frontend/src/views/RealTrading/components/TradeRecordForm.vue`
  - 增加平仓持仓 Select、自动回填、状态清理、可平数量展示和提交前校验。
- Modify: `frontend/src/views/RealTrading/__tests__/TradeRecordForm.test.ts`
  - 覆盖平仓选择、部分平仓、超过持仓、市场切换和历史编辑。
- Modify: `frontend/src/views/RealTrading/__tests__/RealTradingPage.test.ts`
  - 覆盖父页面持仓传参和后端并发校验错误的表单保留行为。

后端文件不修改。`app/services/portfolio/position_calculator.py` 中 `_require_available()` 已负责最终的超量平仓校验。

---

### Task 1: 建立平仓持仓选择纯函数

**Files:**
- Create: `frontend/src/views/RealTrading/closePositionSelection.ts`
- Create: `frontend/src/views/RealTrading/__tests__/closePositionSelection.test.ts`

- [ ] **Step 1: 对计划修改的符号运行 GitNexus 影响分析**

Run:

```powershell
npx gitnexus impact -r "D:\1workplace\project\TradingAgents-CN\.worktrees\real-portfolio-crypto" PortfolioPosition --direction upstream
```

Expected: 输出 `PortfolioPosition` 的使用方和风险等级。若结果为 HIGH 或 CRITICAL，先向用户报告并暂停生产代码修改。

- [ ] **Step 2: 写纯函数失败测试**

Create `frontend/src/views/RealTrading/__tests__/closePositionSelection.test.ts`:

```ts
import { describe, expect, it } from 'vitest'

import type { PortfolioPosition } from '@/api/realTrades'
import {
  closePositionKey,
  closePositionLabel,
  closeQuantityError,
  filterClosePositions
} from '../closePositionSelection'

const positions: PortfolioPosition[] = [
  {
    storage_key: 'US:NASDAQ:AAPL:equity',
    market: 'US',
    exchange: 'NASDAQ',
    symbol: 'AAPL',
    instrument_type: 'equity',
    position_side: 'long',
    quote_asset: 'USD',
    quantity: '10'
  },
  {
    storage_key: 'US:NASDAQ:AAPL:equity',
    market: 'US',
    exchange: 'NASDAQ',
    symbol: 'AAPL',
    instrument_type: 'equity',
    position_side: 'short',
    quote_asset: 'USD',
    quantity: '3'
  },
  {
    storage_key: 'CRYPTO:binance:BTC/USDT:USDT:crypto_linear_perpetual',
    market: 'CRYPTO',
    exchange: 'binance',
    symbol: 'BTC/USDT:USDT',
    instrument_type: 'crypto_linear_perpetual',
    position_side: 'long',
    quote_asset: 'USDT',
    quantity: '0.004'
  },
  {
    storage_key: 'US:NYSE:ZERO:equity',
    market: 'US',
    exchange: 'NYSE',
    symbol: 'ZERO',
    instrument_type: 'equity',
    position_side: 'long',
    quote_asset: 'USD',
    quantity: '0'
  }
]

describe('closePositionSelection', () => {
  it('filters positive positions by market and keeps long and short distinct', () => {
    const result = filterClosePositions(positions, 'US')

    expect(result).toHaveLength(2)
    expect(closePositionKey(result[0])).not.toBe(closePositionKey(result[1]))
    expect(result.map(closePositionLabel)).toEqual([
      'AAPL · NASDAQ · 多头 · 当前 10',
      'AAPL · NASDAQ · 空头 · 当前 3'
    ])
  })

  it('validates empty, invalid, and excessive close quantities', () => {
    expect(closeQuantityError('', '10')).toBe('请输入平仓数量')
    expect(closeQuantityError('0', '10')).toBe('平仓数量必须大于 0')
    expect(closeQuantityError('11', '10')).toBe('平仓数量不能超过当前持仓 10')
    expect(closeQuantityError('4', '10')).toBeNull()
  })
})
```

- [ ] **Step 3: 运行测试并确认因为模块不存在而失败**

Run:

```powershell
cd frontend
npm test -- --run src/views/RealTrading/__tests__/closePositionSelection.test.ts
```

Expected: FAIL，错误包含 `Failed to resolve import "../closePositionSelection"`。

- [ ] **Step 4: 实现最小纯函数模块**

Create `frontend/src/views/RealTrading/closePositionSelection.ts`:

```ts
import Decimal from 'decimal.js'

import type { Market, PortfolioPosition } from '@/api/realTrades'

export function closePositionKey(position: PortfolioPosition): string {
  return JSON.stringify([
    position.market,
    position.exchange,
    position.symbol,
    position.instrument_type,
    position.position_side
  ])
}

export function filterClosePositions(
  positions: PortfolioPosition[],
  market: Market
): PortfolioPosition[] {
  return positions.filter(position => {
    try {
      return position.market === market && new Decimal(position.quantity).gt(0)
    } catch {
      return false
    }
  })
}

export function closePositionLabel(position: PortfolioPosition): string {
  const side = position.position_side === 'short' ? '空头' : '多头'
  return `${position.symbol} · ${position.exchange} · ${side} · 当前 ${position.quantity}`
}

export function closeQuantityError(quantity: string, available: string): string | null {
  if (!quantity.trim()) return '请输入平仓数量'
  try {
    const requested = new Decimal(quantity)
    const current = new Decimal(available)
    if (!requested.isFinite() || requested.lte(0)) return '平仓数量必须大于 0'
    if (requested.gt(current)) return `平仓数量不能超过当前持仓 ${available}`
    return null
  } catch {
    return '请输入有效的平仓数量'
  }
}

export function positionQuantityUnit(position: PortfolioPosition): string {
  if (position.instrument_type === 'crypto_linear_perpetual') {
    return position.symbol.split('/')[0] || '标的币'
  }
  return '股'
}
```

- [ ] **Step 5: 运行纯函数测试并确认通过**

Run:

```powershell
cd frontend
npm test -- --run src/views/RealTrading/__tests__/closePositionSelection.test.ts
```

Expected: PASS，2 tests passed。

- [ ] **Step 6: 提交纯函数和测试**

```powershell
git add -- frontend/src/views/RealTrading/closePositionSelection.ts frontend/src/views/RealTrading/__tests__/closePositionSelection.test.ts
git commit -m "test: define close position selection rules"
```

---

### Task 2: 将当前持仓传入交易表单

**Files:**
- Modify: `frontend/src/views/RealTrading/index.vue:1-65`
- Modify: `frontend/src/views/RealTrading/__tests__/RealTradingPage.test.ts`

- [ ] **Step 1: 对父页面符号运行 GitNexus 影响分析**

Run:

```powershell
npx gitnexus impact -r "D:\1workplace\project\TradingAgents-CN\.worktrees\real-portfolio-crypto" openCreate --direction upstream
npx gitnexus impact -r "D:\1workplace\project\TradingAgents-CN\.worktrees\real-portfolio-crypto" refreshValuation --direction upstream
```

Expected: 报告直接调用方和风险等级。Vue 模板若显示 UNKNOWN，记录结果后只修改父页面传参和测试。

- [ ] **Step 2: 写父页面传参失败测试**

Update `frontend/src/views/RealTrading/__tests__/RealTradingPage.test.ts` imports:

```ts
import RealTradingPage from '../index.vue'
import TradeRecordForm from '../components/TradeRecordForm.vue'
import { realTradesApi, type PortfolioPosition } from '@/api/realTrades'
```

Append:

```ts
it('passes the current positions into the create-record form', async () => {
  const currentPositions: PortfolioPosition[] = [{
    storage_key: 'US:NASDAQ:AAPL:equity',
    market: 'US',
    exchange: 'NASDAQ',
    symbol: 'AAPL',
    instrument_type: 'equity',
    position_side: 'short',
    quote_asset: 'USD',
    quantity: '3'
  }]
  vi.mocked(realTradesApi.getPositions).mockResolvedValue({
    success: true,
    data: { items: currentPositions, total_market_value: '0', excluded: [] }
  } as never)

  const wrapper = mountPage()
  await flushPromises()
  await wrapper.get('[data-testid="create-record"]').trigger('click')

  expect(wrapper.getComponent(TradeRecordForm).props('positions')).toEqual(currentPositions)
  expect(wrapper.getComponent(TradeRecordForm).props('editing')).toBe(false)
})
```

- [ ] **Step 3: 运行测试并确认缺少测试标识或 props**

Run:

```powershell
cd frontend
npm test -- --run src/views/RealTrading/__tests__/RealTradingPage.test.ts
```

Expected: FAIL，原因是找不到 `[data-testid="create-record"]` 或表单没有 `positions` prop。

- [ ] **Step 4: 给父页面增加稳定按钮标识和表单 props**

In `frontend/src/views/RealTrading/index.vue`, replace the toolbar create button and form usage with:

```vue
<button data-testid="create-record" @click="openCreate">新增</button>
```

```vue
<TradeRecordForm
  :initial-value="formInitial"
  :positions="positions"
  :editing="Boolean(editingId)"
  :submitting="submitting"
  @submit="submitRecord"
/>
```

- [ ] **Step 5: 扩展表单 props 类型以让父页面编译**

In `TradeRecordForm.vue` imports and props, use:

```ts
import {
  realTradesApi,
  type AssetRules,
  type CreateLedgerRecordPayload,
  type PortfolioPosition
} from '@/api/realTrades'

const props = withDefaults(
  defineProps<{
    initialValue: CreateLedgerRecordPayload
    positions?: PortfolioPosition[]
    editing?: boolean
    submitting?: boolean
  }>(),
  {
    positions: () => [],
    editing: false,
    submitting: false
  }
)
```

Do not add close-selection behavior in this task.

- [ ] **Step 6: 运行父页面测试和类型检查**

Run:

```powershell
cd frontend
npm test -- --run src/views/RealTrading/__tests__/RealTradingPage.test.ts
npm run type-check
```

Expected: RealTradingPage tests PASS；`vue-tsc --noEmit` exit 0。

- [ ] **Step 7: 提交父页面传参**

```powershell
git add -- frontend/src/views/RealTrading/index.vue frontend/src/views/RealTrading/components/TradeRecordForm.vue frontend/src/views/RealTrading/__tests__/RealTradingPage.test.ts
git commit -m "feat: pass current positions to trade form"
```

---

### Task 3: 实现 shadcn-vue 平仓持仓选择和数量校验

**Files:**
- Modify: `frontend/src/views/RealTrading/components/TradeRecordForm.vue:1-500`
- Modify: `frontend/src/views/RealTrading/__tests__/TradeRecordForm.test.ts`

- [ ] **Step 1: 对表单关键函数运行 GitNexus 影响分析**

Run:

```powershell
npx gitnexus impact -r "D:\1workplace\project\TradingAgents-CN\.worktrees\real-portfolio-crypto" applyMarketRules --direction upstream
npx gitnexus impact -r "D:\1workplace\project\TradingAgents-CN\.worktrees\real-portfolio-crypto" syncTradeSide --direction upstream
npx gitnexus impact -r "D:\1workplace\project\TradingAgents-CN\.worktrees\real-portfolio-crypto" submit --direction upstream
```

Expected: `applyMarketRules`、`syncTradeSide` 和 `submit` 的风险为 LOW 或可解释的 UNKNOWN。HIGH/CRITICAL 必须先报告用户。

- [ ] **Step 2: 扩展表单测试挂载器和测试持仓**

Update imports in `TradeRecordForm.test.ts`:

```ts
import {
  realTradesApi,
  type CreateLedgerRecordPayload,
  type PortfolioPosition
} from '@/api/realTrades'
import { Select, SelectItem } from '@/components/ui/select'
import { closePositionKey } from '../closePositionSelection'
```

Replace `mountForm` with:

```ts
function mountForm(
  initialValue: Partial<CreateLedgerRecordPayload> = {},
  positions: PortfolioPosition[] = [],
  editing = false
) {
  return mount(TradeRecordForm, {
    props: {
      initialValue: { ...defaults, ...initialValue },
      positions,
      editing
    },
    global: { plugins: [ElementPlus] }
  })
}
```

Add fixtures:

```ts
const longAapl: PortfolioPosition = {
  storage_key: 'US:NASDAQ:AAPL:equity',
  market: 'US',
  exchange: 'NASDAQ',
  symbol: 'AAPL',
  instrument_type: 'equity',
  position_side: 'long',
  quote_asset: 'USD',
  quantity: '10'
}

const shortAapl: PortfolioPosition = {
  ...longAapl,
  position_side: 'short',
  quantity: '3'
}

const longBtc: PortfolioPosition = {
  storage_key: 'CRYPTO:binance:BTC/USDT:USDT:crypto_linear_perpetual',
  market: 'CRYPTO',
  exchange: 'binance',
  symbol: 'BTC/USDT:USDT',
  instrument_type: 'crypto_linear_perpetual',
  position_side: 'long',
  quote_asset: 'USDT',
  quantity: '0.004'
}
```

- [ ] **Step 3: 写市场筛选和多空选项失败测试**

Append:

```ts
it('lists only closeable positions from the selected market and keeps sides distinct', async () => {
  const wrapper = mountForm(
    { market: 'US', exchange: 'NASDAQ', symbol: '', position_action: 'close', quantity: '' },
    [longAapl, shortAapl, longBtc]
  )
  await flushPromises()

  const labels = wrapper.findAllComponents(SelectItem).map(item => item.text())
  expect(labels).toEqual([
    'AAPL · NASDAQ · 多头 · 当前 10',
    'AAPL · NASDAQ · 空头 · 当前 3'
  ])
  expect(wrapper.findComponent(Select).exists()).toBe(true)
})
```

- [ ] **Step 4: 写选择后回填但不默认数量的失败测试**

Append:

```ts
it('fills asset fields from the selected position and leaves close quantity empty', async () => {
  const wrapper = mountForm(
    { market: 'US', exchange: 'NASDAQ', symbol: '', position_action: 'close', quantity: '' },
    [shortAapl]
  )
  await flushPromises()

  wrapper.getComponent(Select).vm.$emit('update:modelValue', closePositionKey(shortAapl))
  await flushPromises()

  expect(wrapper.get('[data-testid="available-close-quantity"]').text()).toContain('3 股')
  expect((wrapper.get('[data-testid="quantity"]').element as HTMLInputElement).value).toBe('')
  expect(wrapper.get('[data-testid="selected-position-side"]').text()).toContain('空头')

  await wrapper.get('[data-testid="price"]').setValue('190')
  await wrapper.get('[data-testid="quantity"]').setValue('2')
  await wrapper.get('form').trigger('submit')

  const [payload] = wrapper.emitted('submit')![0] as [CreateLedgerRecordPayload]
  expect(payload).toMatchObject({
    market: 'US',
    exchange: 'NASDAQ',
    symbol: 'AAPL',
    instrument_type: 'equity',
    quote_asset: 'USD',
    position_side: 'short',
    position_action: 'close',
    side: 'buy',
    quantity: '2'
  })
})
```

- [ ] **Step 5: 写超量平仓、市场切换和历史编辑失败测试**

Append:

```ts
it('blocks a close quantity above the selected current position', async () => {
  const wrapper = mountForm(
    { market: 'US', exchange: 'NASDAQ', symbol: '', position_action: 'close', quantity: '' },
    [longAapl]
  )
  await flushPromises()
  wrapper.getComponent(Select).vm.$emit('update:modelValue', closePositionKey(longAapl))
  await flushPromises()

  await wrapper.get('[data-testid="price"]').setValue('190')
  await wrapper.get('[data-testid="quantity"]').setValue('11')
  await wrapper.get('form').trigger('submit')

  expect(wrapper.emitted('submit')).toBeUndefined()
  expect(wrapper.get('.form-error').text()).toBe('平仓数量不能超过当前持仓 10')
})

it('clears the selected close position and quantity after changing market', async () => {
  const wrapper = mountForm(
    { market: 'US', exchange: 'NASDAQ', symbol: '', position_action: 'close', quantity: '' },
    [longAapl, longBtc]
  )
  await flushPromises()
  wrapper.getComponent(Select).vm.$emit('update:modelValue', closePositionKey(longAapl))
  await flushPromises()
  await wrapper.get('[data-testid="quantity"]').setValue('4')

  await wrapper.get('[data-testid="market"]').setValue('CRYPTO')
  await flushPromises()

  expect(wrapper.find('[data-testid="available-close-quantity"]').exists()).toBe(false)
  expect((wrapper.get('[data-testid="quantity"]').element as HTMLInputElement).value).toBe('')
  expect(wrapper.findAllComponents(SelectItem).map(item => item.text())).toEqual([
    'BTC/USDT:USDT · binance · 多头 · 当前 0.004'
  ])
})

it('shows an empty state and blocks submit when the selected market has no closeable position', async () => {
  const wrapper = mountForm(
    { market: 'HK', exchange: 'HKEX', symbol: '', position_action: 'close', quantity: '' },
    [longAapl, longBtc]
  )
  await flushPromises()

  expect(wrapper.text()).toContain('该市场暂无可平持仓')
  expect(wrapper.get('[data-testid="close-position-select"]').attributes('disabled')).toBeDefined()

  await wrapper.get('[data-testid="price"]').setValue('100')
  await wrapper.get('[data-testid="quantity"]').setValue('1')
  await wrapper.get('form').trigger('submit')

  expect(wrapper.emitted('submit')).toBeUndefined()
  expect(wrapper.get('.form-error').text()).toBe('请选择当前持仓')
})

it('updates the available quantity and invalidates a position that is no longer closeable', async () => {
  const wrapper = mountForm(
    { market: 'US', exchange: 'NASDAQ', symbol: '', position_action: 'close', quantity: '' },
    [longAapl]
  )
  await flushPromises()
  wrapper.getComponent(Select).vm.$emit('update:modelValue', closePositionKey(longAapl))
  await flushPromises()

  await wrapper.setProps({ positions: [{ ...longAapl, quantity: '6' }] })
  await flushPromises()
  expect(wrapper.get('[data-testid="available-close-quantity"]').text()).toContain('6 股')

  await wrapper.get('[data-testid="quantity"]').setValue('2')
  await wrapper.setProps({ positions: [{ ...longAapl, quantity: '0' }] })
  await flushPromises()

  expect(wrapper.find('[data-testid="available-close-quantity"]').exists()).toBe(false)
  expect((wrapper.get('[data-testid="quantity"]').element as HTMLInputElement).value).toBe('')
  expect(wrapper.get('.form-error').text()).toBe('所选持仓已变化，请重新选择平仓标的')
})

it('allows editing a historical close record without a current position', async () => {
  const wrapper = mountForm(
    {
      market: 'US',
      exchange: 'NASDAQ',
      symbol: 'AAPL',
      quote_asset: 'USD',
      position_side: 'long',
      position_action: 'close',
      side: 'sell',
      price: '190',
      quantity: '2'
    },
    [],
    true
  )

  expect(wrapper.find('[data-testid="close-position-select"]').exists()).toBe(false)
  await wrapper.get('form').trigger('submit')
  expect(wrapper.emitted('submit')).toHaveLength(1)
})
```

- [ ] **Step 6: 运行表单测试并确认新测试失败**

Run:

```powershell
cd frontend
npm test -- --run src/views/RealTrading/__tests__/TradeRecordForm.test.ts
```

Expected: 新测试 FAIL，缺少 Select、可平数量展示和超量校验；原有测试继续通过。

- [ ] **Step 7: 导入 shadcn-vue Select 和纯函数**

In `TradeRecordForm.vue` script imports:

```ts
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue
} from '@/components/ui/select'
import {
  closePositionKey,
  closePositionLabel,
  closeQuantityError,
  filterClosePositions,
  positionQuantityUnit
} from '../closePositionSelection'
```

- [ ] **Step 8: 增加平仓选择状态和派生值**

Add after existing refs:

```ts
const selectedClosePositionKey = ref('')
const isCloseTrade = computed(
  () => form.record_type === 'trade' && form.position_action === 'close'
)
const isNewCloseTrade = computed(() => isCloseTrade.value && !props.editing)
const closeablePositions = computed(() =>
  filterClosePositions(props.positions, form.market)
)
const selectedClosePosition = computed(() =>
  closeablePositions.value.find(
    position => closePositionKey(position) === selectedClosePositionKey.value
  ) || null
)
```

- [ ] **Step 9: 增加选择、清理和持仓刷新逻辑**

Add functions:

```ts
function resetClosePosition() {
  selectedClosePositionKey.value = ''
  form.symbol = ''
  form.quantity = ''
  form.order_notional = undefined
  form.initial_margin = undefined
}

async function selectClosePosition(value: string) {
  selectedClosePositionKey.value = value
  const position = props.positions.find(item => closePositionKey(item) === value)
  if (!position) return

  Object.assign(form, {
    market: position.market,
    exchange: position.exchange,
    symbol: position.symbol,
    instrument_type: position.instrument_type,
    quote_asset: position.quote_asset,
    position_side: position.position_side,
    quantity: '',
    order_notional: undefined,
    initial_margin: undefined
  })
  quantityRuleReady.value = false
  syncTradeSide()
  if (position.market === 'CRYPTO') await loadRules()
}
```

Add watchers without `immediate: true`, so historical edit initialization is not cleared:

```ts
watch(
  () => form.position_action,
  (action, previous) => {
    if (props.editing || action === previous) return
    if (action === 'close') resetClosePosition()
    else selectedClosePositionKey.value = ''
  }
)

watch(
  () => form.market,
  (market, previous) => {
    if (!props.editing && isCloseTrade.value && market !== previous) resetClosePosition()
  }
)

watch(
  () => props.positions,
  () => {
    if (
      selectedClosePositionKey.value &&
      !closeablePositions.value.some(
        position => closePositionKey(position) === selectedClosePositionKey.value
      )
    ) {
      selectedClosePositionKey.value = ''
      form.quantity = ''
      error.value = '所选持仓已变化，请重新选择平仓标的'
    }
  },
  { deep: true }
)
```

- [ ] **Step 10: 调整模板顺序并加入持仓 Select**

Move the existing “操作” fieldset to immediately after market/instrument fields. Hide manual symbol and direction controls for new close records:

```vue
<fieldset v-if="form.record_type === 'trade'" class="span-2" data-testid="position-action">
  <legend>操作</legend>
  <label><input v-model="form.position_action" type="radio" value="open" />开仓</label>
  <label data-testid="position-action-close">
    <input v-model="form.position_action" type="radio" value="close" />平仓
  </label>
  <span data-testid="trade-side" class="intent">{{ intentLabel }}</span>
</fieldset>

<label v-if="isNewCloseTrade" class="span-2 close-position-field">
  <span>当前持仓</span>
  <Select
    :model-value="selectedClosePositionKey || undefined"
    :disabled="closeablePositions.length === 0"
    @update:model-value="selectClosePosition(String($event))"
  >
    <SelectTrigger data-testid="close-position-select">
      <SelectValue placeholder="选择当前持仓" />
    </SelectTrigger>
    <SelectContent>
      <SelectGroup>
        <SelectItem
          v-for="position in closeablePositions"
          :key="closePositionKey(position)"
          :value="closePositionKey(position)"
        >
          {{ closePositionLabel(position) }}
        </SelectItem>
      </SelectGroup>
    </SelectContent>
  </Select>
  <small v-if="closeablePositions.length === 0" class="field-help">
    该市场暂无可平持仓
  </small>
  <small
    v-else-if="selectedClosePosition"
    class="field-help"
    data-testid="available-close-quantity"
  >
    当前持仓数量：{{ selectedClosePosition.quantity }}
    {{ positionQuantityUnit(selectedClosePosition) }}
  </small>
</label>

<div
  v-if="isNewCloseTrade && selectedClosePosition"
  class="span-2 selected-position-side"
  data-testid="selected-position-side"
>
  持仓方向：{{ selectedClosePosition.position_side === 'short' ? '空头' : '多头' }}
</div>
```

Apply these visibility conditions to the existing fields:

```vue
<label v-if="!isNewCloseTrade" class="span-2">
  <!-- existing symbol input -->
</label>

<fieldset
  v-if="supportsShort && !isTransfer && !isNewCloseTrade"
  class="span-2 position-side"
>
  <!-- existing long/short radios -->
</fieldset>
```

Keep the existing quantity input visible for close trades. Do not assign the current position quantity to `form.quantity`.

- [ ] **Step 11: 在 submit 中增加平仓选择和数量上限校验**

At the beginning of `submit()`, after symbol normalization and before generic required-field validation, add:

```ts
if (isNewCloseTrade.value) {
  if (!selectedClosePosition.value) {
    error.value = '请选择当前持仓'
    return
  }
  const quantityError = closeQuantityError(
    form.quantity,
    selectedClosePosition.value.quantity
  )
  if (quantityError) {
    error.value = quantityError
    return
  }
}
```

Do not remove the existing generic price/quantity validation or backend request validation.

- [ ] **Step 12: 增加最小布局样式**

Add scoped styles using existing semantic form colors:

```css
.close-position-field,
.selected-position-side {
  min-width: 0;
}
.field-help {
  color: #909399;
  font-size: 12px;
}
.selected-position-side {
  color: #606266;
  font-size: 13px;
}
```

Do not create a custom dropdown and do not add Element Plus components.

- [ ] **Step 13: 运行表单测试和类型检查**

Run:

```powershell
cd frontend
npm test -- --run src/views/RealTrading/__tests__/closePositionSelection.test.ts src/views/RealTrading/__tests__/TradeRecordForm.test.ts
npm run type-check
```

Expected: 所有目标测试 PASS；`vue-tsc --noEmit` exit 0。

- [ ] **Step 14: 提交表单功能**

```powershell
git add -- frontend/src/views/RealTrading/components/TradeRecordForm.vue frontend/src/views/RealTrading/__tests__/TradeRecordForm.test.ts
git commit -m "feat: select current position when closing"
```

---

### Task 4: 处理并发持仓变化错误并保留表单

**Files:**
- Modify: `frontend/src/views/RealTrading/index.vue:55-65`
- Modify: `frontend/src/views/RealTrading/__tests__/RealTradingPage.test.ts`

- [ ] **Step 1: 对 submitRecord 运行 GitNexus 影响分析**

Run:

```powershell
npx gitnexus impact -r "D:\1workplace\project\TradingAgents-CN\.worktrees\real-portfolio-crypto" submitRecord --direction upstream
```

Expected: 风险为 LOW 或 UNKNOWN，调用边界仅限当前页面表单提交。

- [ ] **Step 2: 扩展 API mock 并写失败测试**

Add `createRecord: vi.fn()` to the `realTradesApi` mock and default setup:

```ts
vi.mocked(realTradesApi.createRecord).mockResolvedValue({
  success: true,
  data: { record: {} }
} as never)
```

Append a test using a form stub that emits a close payload:

```ts
it('keeps the form open and asks for a refresh when available quantity changed', async () => {
  vi.mocked(realTradesApi.createRecord).mockRejectedValueOnce(
    new Error('close quantity exceeds available long quantity 1')
  )
  const warning = vi.spyOn(ElMessage, 'warning').mockImplementation(() => undefined as never)

  const wrapper = mount(RealTradingPage, {
    global: {
      stubs: {
        VChart: true,
        RouterLink: true,
        TradeRecordForm: {
          emits: ['submit'],
          template: `<button data-testid="emit-close" @click="$emit('submit', {
            record_type: 'trade', market: 'US', exchange: 'NASDAQ', symbol: 'AAPL',
            instrument_type: 'equity', quote_asset: 'USD', side: 'sell',
            position_side: 'long', position_action: 'close', price: '190', quantity: '2',
            trade_time: '2026-07-22T12:00:00'
          })">emit</button>`
        }
      }
    }
  })
  await flushPromises()
  await wrapper.get('[data-testid="create-record"]').trigger('click')
  await wrapper.get('[data-testid="emit-close"]').trigger('click')
  await flushPromises()

  expect(wrapper.find('[data-testid="emit-close"]').exists()).toBe(true)
  expect(warning).toHaveBeenCalledWith('当前持仓已变化，请刷新持仓后重新选择平仓标的')
})
```

Add this import:

```ts
import { ElMessage } from 'element-plus'
```

- [ ] **Step 3: 运行测试并确认当前没有专用提示**

Run:

```powershell
cd frontend
npm test -- --run src/views/RealTrading/__tests__/RealTradingPage.test.ts
```

Expected: FAIL，`ElMessage.warning` 未被调用；表单仍保持打开。

- [ ] **Step 4: 在 submitRecord 中识别后端可平数量变化**

Replace the one-line `submitRecord` with:

```ts
async function submitRecord(payload: CreateLedgerRecordPayload) {
  submitting.value = true
  try {
    const response = editingId.value
      ? await realTradesApi.updateRecord(editingId.value, payload)
      : await realTradesApi.createRecord(payload)
    if (response.success) {
      ElMessage.success('记录已保存')
      formVisible.value = false
      await Promise.all([refreshValuation(), fetchRecords()])
    }
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error)
    if (
      payload.position_action === 'close' &&
      message.includes('close quantity exceeds available')
    ) {
      ElMessage.warning('当前持仓已变化，请刷新持仓后重新选择平仓标的')
      return
    }
    throw error
  } finally {
    submitting.value = false
  }
}
```

Do not close or reset the form in the catch branch.

- [ ] **Step 5: 运行父页面和表单回归测试**

Run:

```powershell
cd frontend
npm test -- --run src/views/RealTrading/__tests__/RealTradingPage.test.ts src/views/RealTrading/__tests__/TradeRecordForm.test.ts
```

Expected: 所有测试 PASS。

- [ ] **Step 6: 提交并发错误反馈**

```powershell
git add -- frontend/src/views/RealTrading/index.vue frontend/src/views/RealTrading/__tests__/RealTradingPage.test.ts
git commit -m "fix: preserve close form when position changed"
```

---

### Task 5: 全量验证、Docker 部署和浏览器验收

**Files:**
- Verify only; no planned production file changes.

- [ ] **Step 1: 运行全部实盘页面目标测试**

Run:

```powershell
cd frontend
npm test -- --run src/views/RealTrading/__tests__/closePositionSelection.test.ts src/views/RealTrading/__tests__/TradeRecordForm.test.ts src/views/RealTrading/__tests__/RealTradingPage.test.ts src/views/RealTrading/__tests__/PositionTable.test.ts src/views/RealTrading/__tests__/TradeRecordsDialog.test.ts
```

Expected: 5 test files PASS，0 failed。

- [ ] **Step 2: 运行类型检查和差异格式检查**

Run:

```powershell
cd frontend
npm run type-check
cd ..
git diff --check
```

Expected: 两条命令 exit 0，无 TypeScript 错误和空白错误。

- [ ] **Step 3: 运行 GitNexus 变更检测**

Run:

```powershell
npx gitnexus detect-changes -r "D:\1workplace\project\TradingAgents-CN\.worktrees\real-portfolio-crypto"
```

Expected: 变更集中在 RealTrading 页面、表单、纯函数和测试。若出现无关执行流或 HIGH/CRITICAL 风险，暂停并复核差异。

- [ ] **Step 4: 只重建前端 Docker 镜像和容器**

Run:

```powershell
docker compose -p tradingagents-cn build frontend
docker compose -p tradingagents-cn up -d --no-deps frontend
docker compose -p tradingagents-cn ps
```

Expected: `tradingagents-frontend` 与 `tradingagents-backend` 均为 healthy；不新增容器，不重建后端容器。

- [ ] **Step 5: 使用内置 Browser 验收新建部分平仓**

Target flow:

```text
/real-trading → 新增 → 市场选择美股 → 操作选择平仓
→ 下拉框只显示美股持仓 → 选择 AAPL 空头
→ 显示当前数量且数量输入为空 → 输入小于当前数量的值 → 保存成功
```

Browser checks:

1. URL 和标题仍为实盘持仓页面。
2. 页面无 Vite/框架错误覆盖层。
3. “当前持仓”使用 shadcn-vue Select，可选择市场内持仓。
4. 多头和空头显示为独立选项。
5. 选择后显示当前持仓数量，数量输入为空。
6. 输入超过当前数量时显示前端错误，后端日志没有 POST。
7. 输入合法部分数量时 POST 成功，持仓数量刷新。
8. 控制台没有本功能新增的 error/warn。
9. 截图保存为验收证据，不写入仓库。

- [ ] **Step 6: 验收加密永续平仓数量规则**

Target flow:

```text
市场选择加密货币 → 操作选择平仓 → 选择 BTC/USDT:USDT 持仓
→ 展示标的币持仓数量 → 输入符合 Binance step 且不超过持仓的部分数量
→ 保存成功
```

Expected: 平仓不显示开仓的订单金额/保证金三模式；数量遵守资产规则，持仓方向由选择项决定。

- [ ] **Step 7: 检查工作区和提交范围**

Run:

```powershell
git status --short
git log -4 --oneline
```

Expected: 新功能提交只包含计划列出的前端文件；用户原有未提交改动保持原状。

---

## 完成标准

- 新建平仓必须从所选市场的当前持仓中选择标的。
- 当前持仓多头和空头不会混淆。
- 选择后展示可平数量，但不默认填充平仓数量。
- 部分平仓允许提交，超量平仓在前端阻止。
- 市场或持仓变化会清空旧数量。
- 历史平仓记录编辑不依赖当前持仓仍存在。
- 后端并发校验继续生效，错误时表单内容保留。
- 不新增后端接口，不修改模拟交易，不新增 Element Plus 控件。
- Docker 前端部署和内置 Browser 验收通过。
