<script setup lang="ts">
import type { AssetRules, CreateLedgerRecordPayload, PortfolioPosition } from '@/api/realTrades'
import Decimal from 'decimal.js'
import { computed, reactive, ref, watch } from 'vue'
import {

  realTradesApi
} from '@/api/realTrades'
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue
} from '@/components/ui/select'
import { Slider } from '@/components/ui/slider'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip'
import {
  closePositionKey,
  closePositionLabel,
  closeQuantityError,
  filterClosePositions,
  positionQuantityUnit
} from '../closePositionSelection'

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
const emit = defineEmits<{ submit: [payload: CreateLedgerRecordPayload] }>()
const form = reactive<CreateLedgerRecordPayload>({ ...props.initialValue })
const advancedOpen = ref(false)
const error = ref('')
const calculationMode = ref<'quantity' | 'notional' | 'margin'>('quantity')
const leverageMarks = [1, 10, 20, 30, 50, 75, 100, 150] as const
const quantityRuleReady = ref(false)
const quantityRuleLoading = ref(false)
const selectedClosePositionKey = ref('')
let quantityRuleRequest: Promise<boolean> | null = null
const quantityRule = reactive<AssetRules>({
  quantity_type: 'integer',
  step: '100',
  minimum: '100',
  precision: 0
})

const isTransfer = computed(
  () => form.record_type === 'transfer_in' || form.record_type === 'transfer_out'
)
const isPerpetual = computed(() => form.instrument_type === 'crypto_linear_perpetual')
const isPerpetualOpen = computed(
  () => isPerpetual.value && form.record_type === 'trade' && form.position_action === 'open'
)
const isCloseTrade = computed(
  () => form.record_type === 'trade' && form.position_action === 'close'
)
const isNewCloseTrade = computed(() => isCloseTrade.value && !props.editing)
const closeablePositions = computed(() => filterClosePositions(props.positions, form.market))
const selectedClosePosition = computed(
  () =>
    closeablePositions.value.find(
      position => closePositionKey(position) === selectedClosePositionKey.value
    ) || null
)
const supportsShort = computed(
  () => (form.market === 'HK' || form.market === 'US' || isPerpetual.value) && !isTransfer.value
)
const symbolPlaceholder = computed(() => (form.market === 'CRYPTO' ? 'BTC/USDT:USDT' : '输入代码'))
const intentLabel = computed(
  () =>
    `${form.position_side === 'short' ? '空头' : '多头'}${form.position_action === 'close' ? '平仓' : '开仓'}`
)
const leverageSliderValue = computed<number[]>({
  get: () => [normalizeLeverage(form.leverage)],
  set: values => setLeverage(values[0] ?? 1)
})

watch(
  () => props.initialValue,
  value => Object.assign(form, value),
  { deep: true }
)
watch([() => form.market, () => form.instrument_type, () => form.record_type], applyMarketRules, {
  immediate: true
})
watch([() => form.position_side, () => form.position_action], syncTradeSide, { immediate: true })
watch(
  () => form.position_action,
  (action, previous) => {
    if (props.editing || action === previous)
      return
    if (action === 'close')
      resetClosePosition()
    else selectedClosePositionKey.value = ''
  }
)
watch(
  () => form.market,
  (market, previous) => {
    if (!props.editing && isCloseTrade.value && market !== previous)
      resetClosePosition()
  }
)
watch(
  () => props.positions,
  () => {
    if (
      selectedClosePositionKey.value
      && !closeablePositions.value.some(
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
watch(
  isPerpetualOpen,
  enabled => {
    if (enabled)
      recalculateFrom(calculationMode.value)
  },
  { immediate: true }
)

function applyMarketRules() {
  const switchingFromTransfer = form.market === 'CRYPTO' && isTransfer.value
  if (form.market === 'CN') {
    Object.assign(form, {
      exchange: form.symbol?.startsWith('6') ? 'SSE' : 'SZSE',
      instrument_type: 'equity',
      quote_asset: 'CNY',
      position_side: 'long'
    })
  }
  if (form.market === 'HK')
    Object.assign(form, { exchange: 'SEHK', instrument_type: 'equity', quote_asset: 'HKD' })
  if (form.market === 'US') {
    Object.assign(form, {
      exchange: form.exchange || 'NASDAQ',
      instrument_type: 'equity',
      quote_asset: 'USD'
    })
  }
  if (form.market === 'CRYPTO') {
    Object.assign(form, {
      exchange: 'binance',
      instrument_type: 'crypto_linear_perpetual',
      quote_asset: 'USDT',
      leverage: String(normalizeLeverage(form.leverage)),
      record_type: switchingFromTransfer ? 'trade' : form.record_type,
      position_action: switchingFromTransfer ? 'open' : form.position_action
    })
  }
  if (!supportsShort.value)
    form.position_side = 'long'
  if (isTransfer.value) {
    form.position_action = undefined
    form.side = undefined
  }
  quantityRule.step = form.market === 'CN' ? '100' : '1'
  quantityRule.minimum = quantityRule.step
  quantityRule.precision = 0
  quantityRuleReady.value = false
  syncTradeSide()
  void loadRules()
}

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
  if (!position)
    return

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
  if (position.market === 'CRYPTO')
    await loadRules()
}

function syncTradeSide() {
  if (form.record_type !== 'trade' || !form.position_action)
    return
  form.side
    = form.position_side === 'long'
      ? form.position_action === 'open'
        ? 'buy'
        : 'sell'
      : form.position_action === 'open'
        ? 'sell'
        : 'buy'
}

function validDecimal(value?: string) {
  try {
    const decimal = new Decimal(value || '')
    return decimal.isFinite() && decimal.gt(0) ? decimal : null
  } catch {
    return null
  }
}

function decimalString(value: Decimal) {
  return value.toFixed()
}

function normalizeCryptoSymbol(value?: string) {
  return (value || '').trim().toUpperCase().replace(/／/g, '/').replace(/：/g, ':')
}

function normalizeLeverage(value?: string) {
  const parsed = Number(value)
  if (!Number.isFinite(parsed))
    return 1
  return Math.min(200, Math.max(1, Math.round(parsed)))
}

function setLeverage(value: number) {
  form.leverage = String(normalizeLeverage(String(value)))
  recalculateFrom(calculationMode.value)
}

function leverageMarkPosition(value: number) {
  return `${((value - 1) / 199) * 100}%`
}

function quantizeQuantity(value: Decimal) {
  if (!quantityRuleReady.value)
    return value
  const step = validDecimal(quantityRule.step)
  return step ? value.div(step).floor().mul(step) : value
}

function applyPerpetualQuantity(rawQuantity: Decimal, price: Decimal, leverage: Decimal) {
  const quantity = quantizeQuantity(rawQuantity)
  const minimum = quantityRuleReady.value ? validDecimal(quantityRule.minimum) : null
  if (!quantity.gt(0) || (minimum && quantity.lt(minimum))) {
    const rawNotional = rawQuantity.mul(price)
    form.quantity = ''
    form.order_notional = decimalString(rawNotional)
    form.initial_margin = decimalString(rawNotional.div(leverage))
    return
  }
  const notional = quantity.mul(price)
  form.quantity = decimalString(quantity)
  form.order_notional = decimalString(notional)
  form.initial_margin = decimalString(notional.div(leverage))
}

function recalculateFrom(mode: 'quantity' | 'notional' | 'margin') {
  if (!isPerpetualOpen.value)
    return
  const price = validDecimal(form.price)
  const leverage = validDecimal(form.leverage)
  if (!price || !leverage)
    return
  if (mode === 'quantity') {
    const quantity = validDecimal(form.quantity)
    if (!quantity)
      return
    applyPerpetualQuantity(quantity, price, leverage)
  } else if (mode === 'notional') {
    const notional = validDecimal(form.order_notional)
    if (!notional)
      return
    applyPerpetualQuantity(notional.div(price), price, leverage)
  } else {
    const margin = validDecimal(form.initial_margin)
    if (!margin)
      return
    const notional = margin.mul(leverage)
    applyPerpetualQuantity(notional.div(price), price, leverage)
  }
}

async function loadRules(): Promise<boolean> {
  if (!form.symbol || form.market !== 'CRYPTO')
    return false
  form.symbol = normalizeCryptoSymbol(form.symbol)
  if (quantityRuleReady.value)
    return true
  if (quantityRuleRequest)
    return quantityRuleRequest

  quantityRuleLoading.value = true
  quantityRuleRequest = (async () => {
    try {
      const response = await realTradesApi.getAssetRules({
        market: form.market,
        exchange: form.exchange,
        symbol: form.symbol,
        instrument_type: form.instrument_type
      })
      if (!response.success)
        return false
      Object.assign(quantityRule, response.data)
      quantityRuleReady.value = true
      recalculateFrom(calculationMode.value)
      return true
    } catch {
      return false
    } finally {
      quantityRuleLoading.value = false
      quantityRuleRequest = null
    }
  })()
  return quantityRuleRequest
}

async function submit() {
  error.value = ''
  if (form.market === 'CRYPTO')
    form.symbol = normalizeCryptoSymbol(form.symbol)
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
  if (form.market === 'CRYPTO' && !quantityRuleReady.value && !(await loadRules())) {
    error.value = '无法获取交易所数量规则，请稍后重试'
    return
  }
  recalculateFrom(calculationMode.value)
  if (isPerpetualOpen.value && !form.quantity) {
    const minimum = validDecimal(quantityRule.minimum)
    const price = validDecimal(form.price)
    if (minimum && price) {
      const minimumNotional = decimalString(minimum.mul(price))
      error.value = `当前开仓金额不足，最小下单数量为 ${quantityRule.minimum}，最小订单金额约 ${minimumNotional} ${form.quote_asset}`
      return
    }
  }
  if (!form.symbol || !form.quantity || (form.record_type === 'trade' && !form.price)) {
    error.value = '请填写标的、数量和价格'
    return
  }
  if (
    isPerpetualOpen.value
    && (!validDecimal(form.leverage)
      || !validDecimal(form.order_notional)
      || !validDecimal(form.initial_margin))
  ) {
    error.value = '请填写价格、杠杆和当前方式对应的开仓金额'
    return
  }
  const feeAmount = form.fee_amount?.trim()
  emit('submit', {
    ...form,
    fee_amount: feeAmount || undefined,
    fee_currency: feeAmount ? form.fee_currency?.trim() || undefined : undefined,
    tags: [...(form.tags || [])]
  })
}
</script>

<template>
  <form class="record-form" @submit.prevent="submit">
    <div class="form-grid">
      <label>记录类型
        <select v-model="form.record_type" data-testid="record-type">
          <option value="trade">成交</option>
          <option value="opening_position">期初持仓</option>
          <option v-if="form.market !== 'CRYPTO'" value="transfer_in">转入</option>
          <option v-if="form.market !== 'CRYPTO'" value="transfer_out">转出</option>
        </select>
      </label>
      <label>市场
        <select v-model="form.market" data-testid="market">
          <option value="CN">A 股</option>
          <option value="HK">港股</option>
          <option value="US">美股</option>
          <option value="CRYPTO">加密货币</option>
        </select>
      </label>
      <label v-if="form.market === 'CRYPTO'">品种
        <select v-model="form.instrument_type" data-testid="instrument-type">
          <option value="crypto_linear_perpetual">USDT 永续</option>
        </select>
      </label>
      <label>交易所
        <select v-if="form.market === 'US'" v-model="form.exchange">
          <option value="NASDAQ">NASDAQ</option>
          <option value="NYSE">NYSE</option>
          <option value="AMEX">AMEX</option>
        </select>
        <input
          v-else
          v-model.trim="form.exchange"
          data-testid="exchange"
          :disabled="form.market !== 'CRYPTO'"
        >
      </label>
      <label v-if="!isNewCloseTrade" class="span-2">
        <span>标的
          <TooltipProvider v-if="form.market === 'CRYPTO'"><Tooltip><TooltipTrigger as-child><button class="symbol-help" type="button" aria-label="加密标的格式说明">
            ?
          </button></TooltipTrigger><TooltipContent side="top">USDT 永续格式：BTC/USDT:USDT（交易对:结算币）</TooltipContent></Tooltip></TooltipProvider>
        </span>
        <input
          v-model.trim="form.symbol"
          data-testid="symbol"
          :placeholder="symbolPlaceholder"
          @blur="loadRules"
        >
      </label>
      <fieldset v-if="supportsShort && !isTransfer && !isNewCloseTrade" class="span-2 position-side">
        <legend>持仓方向</legend>
        <label><input v-model="form.position_side" type="radio" value="long">多头</label>
        <label data-testid="position-side-short"><input v-model="form.position_side" type="radio" value="short">空头</label>
      </fieldset>
      <fieldset v-if="form.record_type === 'trade'" class="span-2" data-testid="position-action">
        <legend>操作</legend>
        <label><input v-model="form.position_action" type="radio" value="open">开仓</label>
        <label data-testid="position-action-close"><input v-model="form.position_action" type="radio" value="close">平仓</label>
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
      <label v-if="form.record_type !== 'transfer_in' || form.price">价格
        <input
          v-model.trim="form.price"
          inputmode="decimal"
          data-testid="price"
          @input="recalculateFrom(calculationMode)"
        >
      </label>
      <label v-if="!isPerpetualOpen">数量
        <input
          v-model.trim="form.quantity"
          inputmode="decimal"
          data-testid="quantity"
          :step="quantityRule.step"
          :min="quantityRule.minimum"
        >
      </label>
      <fieldset
        v-if="isPerpetualOpen"
        class="span-2 perpetual-order"
        data-testid="perpetual-order-inputs"
      >
        <legend>下单计算方式</legend>
        <div class="mode-selector">
          <label><input
            v-model="calculationMode"
            type="radio"
            value="quantity"
            @change="recalculateFrom('quantity')"
          >按数量</label>
          <label><input
            v-model="calculationMode"
            type="radio"
            value="notional"
            @change="recalculateFrom('notional')"
          >按订单金额</label>
          <label><input
            v-model="calculationMode"
            type="radio"
            value="margin"
            @change="recalculateFrom('margin')"
          >按初始保证金</label>
        </div>
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
        <label v-if="calculationMode === 'quantity'">数量（{{ form.symbol.split('/')[0] || '标的币' }}）<input
          v-model.trim="form.quantity"
          inputmode="decimal"
          data-testid="quantity"
          :step="quantityRule.step"
          :min="quantityRule.minimum"
          @input="recalculateFrom('quantity')"
        ></label>
        <label v-else-if="calculationMode === 'notional'">订单金额（USDT）<input
          v-model.trim="form.order_notional"
          inputmode="decimal"
          data-testid="order-notional"
          @input="recalculateFrom('notional')"
        ></label>
        <label v-else>初始保证金（USDT）<input
          v-model.trim="form.initial_margin"
          inputmode="decimal"
          data-testid="initial-margin"
          @input="recalculateFrom('margin')"
        ></label>
        <div class="calculated-values">
          <span v-if="calculationMode !== 'quantity'">数量
            <strong data-testid="calculated-quantity">{{ form.quantity || '-' }}</strong></span>
          <span v-if="calculationMode !== 'notional'">订单金额
            <strong data-testid="calculated-notional">{{ form.order_notional || '-' }}</strong>
            USDT</span>
          <span v-if="calculationMode !== 'margin'">初始保证金
            <strong data-testid="calculated-margin">{{ form.initial_margin || '-' }}</strong>
            USDT</span>
        </div>
      </fieldset>
      <label class="span-2">时间
        <input v-model="form.trade_time" type="datetime-local" step="1">
      </label>
      <label class="span-2">原因
        <textarea v-model.trim="form.reason" rows="2" />
      </label>
    </div>

    <button
      class="advanced-toggle"
      type="button"
      data-testid="advanced-toggle"
      @click="advancedOpen = !advancedOpen"
    >
      费用与合约元数据
    </button>
    <div v-if="advancedOpen" class="form-grid advanced-fields">
      <label>手续费<input v-model.trim="form.fee_amount" data-testid="fee-amount" inputmode="decimal"></label>
      <label>手续费币种<input v-model.trim="form.fee_currency"></label>
      <template v-if="isPerpetual">
        <label>资金费<input v-model.trim="form.funding_fee" inputmode="decimal"></label>
      </template>
    </div>
    <p v-if="error" class="form-error">
      {{ error }}
    </p>
    <div class="form-actions">
      <button type="submit" :disabled="submitting || quantityRuleLoading">
        {{ submitting ? '提交中' : quantityRuleLoading ? '加载交易规则中' : '保存记录' }}
      </button>
    </div>
  </form>
</template>

<style scoped>
.record-form {
  display: grid;
  gap: 14px;
}
.form-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}
label,
fieldset {
  display: grid;
  gap: 6px;
  font-size: 13px;
  color: #606266;
}
input,
select,
textarea {
  box-sizing: border-box;
  width: 100%;
  min-height: 36px;
  border: 1px solid #dcdfe6;
  border-radius: 4px;
  padding: 7px 10px;
  background: #fff;
  color: #303133;
}
fieldset {
  grid-template-columns: auto auto 1fr;
  align-items: center;
  border: 0;
  padding: 0;
}
fieldset label {
  display: flex;
  align-items: center;
  gap: 5px;
}
fieldset input {
  width: auto;
  min-height: auto;
}
.span-2 {
  grid-column: 1 / -1;
}
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
.intent {
  justify-self: end;
  color: #409eff;
}
.symbol-help {
  display: inline-grid;
  width: 16px;
  height: 16px;
  place-items: center;
  border: 1px solid #909399;
  border-radius: 50%;
  padding: 0;
  background: #fff;
  color: #606266;
  font-size: 11px;
  cursor: help;
}
.advanced-toggle {
  justify-self: start;
  border: 0;
  background: transparent;
  color: #409eff;
  cursor: pointer;
  padding: 0;
}
.advanced-fields {
  padding-top: 4px;
  border-top: 1px solid #ebeef5;
}
.perpetual-order {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}
.perpetual-order legend,
.mode-selector,
.calculated-values {
  grid-column: 1 / -1;
}
.mode-selector {
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
}
.mode-selector label {
  display: flex;
  align-items: center;
  gap: 5px;
}
.mode-selector input {
  width: auto;
  min-height: auto;
}
.leverage-control {
  grid-column: 1 / -1;
  display: grid;
  gap: 10px;
  padding: 2px 10px 0;
}
.leverage-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  color: hsl(var(--muted-foreground));
}
.leverage-heading strong {
  color: hsl(var(--primary));
  font-size: 15px;
}
.leverage-marks {
  position: relative;
  height: 28px;
}
.leverage-mark {
  position: absolute;
  top: 0;
  display: grid;
  min-width: 24px;
  min-height: 28px;
  justify-items: center;
  gap: 3px;
  border: 0;
  padding: 0;
  background: transparent;
  color: hsl(var(--muted-foreground));
  font-size: 11px;
  cursor: pointer;
  transform: translateX(-50%);
}
.leverage-mark:first-child {
  justify-items: start;
  transform: none;
}
.leverage-mark-dot {
  width: 2px;
  height: 6px;
  border-radius: 999px;
  background: hsl(var(--border));
}
.leverage-mark.active {
  color: hsl(var(--primary));
  font-weight: 600;
}
.leverage-mark.active .leverage-mark-dot {
  background: hsl(var(--primary));
}
.calculated-values {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
  padding: 10px 12px;
  background: #f7f8fa;
  color: #606266;
  font-size: 12px;
}
.calculated-values span {
  display: grid;
  gap: 3px;
}
.calculated-values strong {
  color: #303133;
  font-size: 14px;
}
.form-error {
  color: #f56c6c;
  margin: 0;
}
.form-actions {
  display: flex;
  justify-content: flex-end;
}
.form-actions button {
  min-width: 96px;
  border: 0;
  border-radius: 4px;
  padding: 9px 16px;
  background: #409eff;
  color: white;
  cursor: pointer;
}
@media (max-width: 640px) {
  .form-grid,
  .perpetual-order,
  .calculated-values {
    grid-template-columns: 1fr;
  }
  .span-2 {
    grid-column: auto;
  }
  .perpetual-order legend,
  .mode-selector,
  .calculated-values {
    grid-column: auto;
  }
  .leverage-mark-label {
    position: absolute;
    width: 1px;
    height: 1px;
    overflow: hidden;
    clip: rect(0, 0, 0, 0);
    white-space: nowrap;
  }
}
</style>
