# 永续合约杠杆滑块 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将加密永续开仓的杠杆文本框替换为可选择 `1–200x` 任意整数、并带有八个常用快捷节点的 shadcn-vue 滑块。

**Architecture:** 使用 shadcn-vue `Slider` 作为唯一杠杆输入控件，在 `TradeRecordForm.vue` 中用一个 number-array computed 适配 Slider 的 `v-model` 与后端字符串字段。常用节点由表单组件负责展示和点击，所有变更统一经过 `setLeverage()` 更新字符串值并触发既有 Decimal 换算逻辑。

**Tech Stack:** Vue 3、TypeScript、shadcn-vue Slider、Reka UI、Decimal.js、Vitest、Docker Compose。

---

### Task 1: 添加 shadcn-vue Slider 组件

**Files:**
- Create: `frontend/src/components/ui/slider/Slider.vue`
- Create: `frontend/src/components/ui/slider/index.ts`

- [ ] **Step 1: 查询当前项目和 Slider 官方用法**

Run:

```bash
cd frontend
npx shadcn-vue@latest info
npx shadcn-vue@latest docs slider
```

Expected: 项目别名为 `@/components/ui`，基础组件库为 Reka UI，并返回 Slider 文档地址。

- [ ] **Step 2: 通过 shadcn-vue CLI 添加 Slider**

Run:

```bash
cd frontend
npx shadcn-vue@latest add slider
```

Expected: 新增 `src/components/ui/slider/Slider.vue` 和 `index.ts`，不修改 Element Plus 依赖。

- [ ] **Step 3: 审查生成组件**

确认 `Slider.vue` 使用 `SliderRoot`、`SliderTrack`、`SliderRange` 和 `SliderThumb`，并通过 `useForwardPropsEmits` 转发 Reka UI 的 props/emits；`index.ts` 只导出 `Slider`。

- [ ] **Step 4: 运行类型检查**

Run: `cd frontend && npm run type-check`

Expected: PASS，无 Vue 或 TypeScript 错误。

### Task 2: 用测试定义杠杆滑块行为

**Files:**
- Modify: `frontend/src/views/RealTrading/__tests__/TradeRecordForm.test.ts`
- Test: `frontend/src/views/RealTrading/__tests__/TradeRecordForm.test.ts`

- [ ] **Step 1: 写入失败测试**

在 `TradeRecordForm` 测试中添加：

```ts
it('uses a 1-200 leverage slider with clickable common marks', async () => {
  const wrapper = mountForm({
    market: 'CRYPTO',
    exchange: 'binance',
    symbol: 'BTC/USDT:USDT',
    instrument_type: 'crypto_linear_perpetual',
    quote_asset: 'USDT',
    price: '100000',
    quantity: '0.01',
    leverage: '10',
    initial_margin: '',
    order_notional: ''
  })
  await flushPromises()

  const slider = wrapper.get('[data-testid="leverage-slider"]')
  expect(slider.attributes('data-min')).toBe('1')
  expect(slider.attributes('data-max')).toBe('200')
  expect(wrapper.get('[data-testid="leverage-value"]').text()).toBe('10×')

  for (const mark of [1, 10, 20, 30, 50, 75, 100, 150]) {
    expect(wrapper.find(`[data-testid="leverage-mark-${mark}"]`).exists()).toBe(true)
  }

  await wrapper.get('[data-testid="leverage-mark-50"]').trigger('click')
  expect(wrapper.get('[data-testid="leverage-value"]').text()).toBe('50×')
  expect(wrapper.get('[data-testid="calculated-margin"]').text()).toBe('20')
})
```

- [ ] **Step 2: 运行测试确认失败**

Run:

```bash
cd frontend
npm test -- --run src/views/RealTrading/__tests__/TradeRecordForm.test.ts
```

Expected: FAIL，因为 `leverage-slider` 和常用节点尚不存在。

### Task 3: 接入滑块、节点和计算联动

**Files:**
- Modify: `frontend/src/views/RealTrading/components/TradeRecordForm.vue`
- Test: `frontend/src/views/RealTrading/__tests__/TradeRecordForm.test.ts`

- [ ] **Step 1: 影响分析**

Run:

```bash
npx gitnexus impact TradeRecordForm --direction upstream --repo TradingAgents-CN
```

Expected: 报告直接使用者和风险；若索引无法识别 Vue SFC，则记录 `UNKNOWN` 并人工限定改动范围为实盘成交记录表单。

- [ ] **Step 2: 添加 Slider 状态适配**

在脚本中导入 Slider，并添加：

```ts
import { Slider } from '@/components/ui/slider'

const leverageMarks = [1, 10, 20, 30, 50, 75, 100, 150] as const

const leverageSliderValue = computed<number[]>({
  get: () => [normalizeLeverage(form.leverage)],
  set: values => setLeverage(values[0] ?? 1)
})

function normalizeLeverage(value?: string) {
  const parsed = Number(value)
  if (!Number.isFinite(parsed)) return 1
  return Math.min(200, Math.max(1, Math.round(parsed)))
}

function setLeverage(value: number) {
  form.leverage = String(normalizeLeverage(String(value)))
  recalculateFrom(calculationMode.value)
}

function leverageMarkPosition(value: number) {
  return `${((value - 1) / 199) * 100}%`
}
```

在 `applyMarketRules()` 的加密市场分支中，对缺失或越界值调用 `setLeverage(normalizeLeverage(form.leverage))`，确保表单和提交值一致。

- [ ] **Step 3: 替换杠杆文本框**

将现有杠杆 `<input>` 替换为：

```vue
<div class="leverage-control">
  <div class="leverage-heading">
    <span>杠杆</span>
    <strong data-testid="leverage-value">{{ form.leverage }}×</strong>
  </div>
  <Slider
    v-model="leverageSliderValue"
    :min="1"
    :max="200"
    :step="1"
    data-min="1"
    data-max="200"
    data-testid="leverage-slider"
    aria-label="杠杆"
  />
  <div class="leverage-marks" aria-label="常用杠杆">
    <button
      v-for="mark in leverageMarks"
      :key="mark"
      type="button"
      class="leverage-mark"
      :class="{ active: Number(form.leverage) === mark }"
      :style="{ left: leverageMarkPosition(mark) }"
      :data-testid="`leverage-mark-${mark}`"
      :aria-label="`${mark}倍杠杆`"
      @click="setLeverage(mark)"
    >
      <span class="leverage-mark-dot" />
      <span class="leverage-mark-label">{{ mark }}</span>
    </button>
  </div>
</div>
```

使用语义化颜色变量设置布局；桌面显示全部节点文字，`640px` 以下隐藏拥挤的常驻文字但保留节点按钮、可访问名称和点击区域。

- [ ] **Step 4: 运行目标测试和类型检查**

Run:

```bash
cd frontend
npm test -- --run src/views/RealTrading/__tests__/TradeRecordForm.test.ts
npm run type-check
```

Expected: `TradeRecordForm` 全部测试 PASS，类型检查 PASS。

### Task 4: Docker 构建与页面验收

**Files:**
- No source changes expected.

- [ ] **Step 1: 构建 Docker 前端**

Run:

```bash
docker compose -p tradingagents-cn up -d --build frontend
docker compose -p tradingagents-cn ps
```

Expected: `tradingagents-frontend` 状态为 healthy，页面仍由 `http://127.0.0.1:8080` 提供。

- [ ] **Step 2: 页面交互验收**

打开 `/real-trading`，选择加密货币和 USDT 永续，确认滑块范围、当前 `N×` 显示、八个常用节点和移动端不重叠。点击 `50` 后确认保证金按当前订单名义金额除以 `50` 即时变化。

- [ ] **Step 3: 最终检查**

Run:

```bash
git diff --check
npx gitnexus detect-changes --repo TradingAgents-CN
```

Expected: 无空白错误；GitNexus 影响范围仅涉及实盘成交表单、其测试和新增 Slider UI 组件。
