<template>
  <form class="record-form" @submit.prevent="submit">
    <div class="form-grid">
      <label>记录类型
        <select v-model="form.record_type" data-testid="record-type">
          <option value="trade">成交</option>
          <option value="opening_position">期初持仓</option>
          <option value="transfer_in">转入</option>
          <option value="transfer_out">转出</option>
        </select>
      </label>
      <label>市场
        <select v-model="form.market" data-testid="market">
          <option value="CN">A 股</option><option value="HK">港股</option>
          <option value="US">美股</option><option value="CRYPTO">加密货币</option>
        </select>
      </label>
      <label v-if="form.market === 'CRYPTO'">品种
        <select v-model="form.instrument_type" data-testid="instrument-type">
          <option value="crypto_spot">现货</option>
          <option value="crypto_linear_perpetual">USDT 永续</option>
        </select>
      </label>
      <label>交易所
        <select v-if="form.market === 'US'" v-model="form.exchange">
          <option value="NASDAQ">NASDAQ</option><option value="NYSE">NYSE</option><option value="AMEX">AMEX</option>
        </select>
        <input v-else v-model.trim="form.exchange" :disabled="form.market !== 'CRYPTO'" />
      </label>
      <label class="span-2">标的
        <input v-model.trim="form.symbol" data-testid="symbol" :placeholder="symbolPlaceholder" @blur="loadRules" />
      </label>
      <fieldset v-if="supportsShort && !isTransfer" class="span-2 position-side">
        <legend>持仓方向</legend>
        <label><input v-model="form.position_side" type="radio" value="long" />多头</label>
        <label data-testid="position-side-short"><input v-model="form.position_side" type="radio" value="short" />空头</label>
      </fieldset>
      <fieldset v-if="form.record_type === 'trade'" class="span-2" data-testid="position-action">
        <legend>操作</legend>
        <label><input v-model="form.position_action" type="radio" value="open" />开仓</label>
        <label data-testid="position-action-close"><input v-model="form.position_action" type="radio" value="close" />平仓</label>
        <span data-testid="trade-side" class="intent">{{ intentLabel }}</span>
      </fieldset>
      <label v-if="form.record_type !== 'transfer_in' || form.price">价格
        <input v-model.trim="form.price" inputmode="decimal" data-testid="price" />
      </label>
      <label>数量
        <input v-model.trim="form.quantity" inputmode="decimal" data-testid="quantity" :step="quantityRule.step" :min="quantityRule.minimum" />
      </label>
      <label class="span-2">时间
        <input v-model="form.trade_time" type="datetime-local" />
      </label>
      <label class="span-2">原因
        <textarea v-model.trim="form.reason" rows="2" />
      </label>
    </div>

    <button class="advanced-toggle" type="button" data-testid="advanced-toggle" @click="advancedOpen = !advancedOpen">
      费用与合约元数据
    </button>
    <div v-if="advancedOpen" class="form-grid advanced-fields">
      <label>手续费<input v-model.trim="form.fee_amount" data-testid="fee-amount" inputmode="decimal" /></label>
      <label>手续费币种<input v-model.trim="form.fee_currency" /></label>
      <template v-if="isPerpetual">
        <label>资金费<input v-model.trim="form.funding_fee" inputmode="decimal" /></label>
        <label>杠杆<input v-model.trim="form.leverage" inputmode="decimal" /></label>
        <label>初始保证金<input v-model.trim="form.initial_margin" inputmode="decimal" /></label>
        <label>保证金模式
          <select v-model="form.margin_mode"><option value="cross">全仓</option><option value="isolated">逐仓</option></select>
        </label>
      </template>
    </div>
    <p v-if="error" class="form-error">{{ error }}</p>
    <div class="form-actions"><button type="submit" :disabled="submitting">{{ submitting ? '提交中' : '保存记录' }}</button></div>
  </form>
</template>

<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { realTradesApi, type AssetRules, type CreateLedgerRecordPayload } from '@/api/realTrades'

const props = defineProps<{ initialValue: CreateLedgerRecordPayload; submitting?: boolean }>()
const emit = defineEmits<{ submit: [payload: CreateLedgerRecordPayload] }>()
const form = reactive<CreateLedgerRecordPayload>({ ...props.initialValue })
const advancedOpen = ref(false)
const error = ref('')
const quantityRule = reactive<AssetRules>({ quantity_type: 'integer', step: '100', minimum: '100', precision: 0 })

const isTransfer = computed(() => form.record_type === 'transfer_in' || form.record_type === 'transfer_out')
const isPerpetual = computed(() => form.instrument_type === 'crypto_linear_perpetual')
const supportsShort = computed(() => (form.market === 'HK' || form.market === 'US' || isPerpetual.value) && !isTransfer.value)
const symbolPlaceholder = computed(() => form.market === 'CRYPTO' ? (isPerpetual.value ? 'BTC/USDT:USDT' : 'BTC/USDT') : '输入代码')
const intentLabel = computed(() => `${form.position_side === 'short' ? '空头' : '多头'}${form.position_action === 'close' ? '平仓' : '开仓'}`)

watch(() => props.initialValue, value => Object.assign(form, value), { deep: true })
watch([() => form.market, () => form.instrument_type, () => form.record_type], applyMarketRules, { immediate: true })
watch([() => form.position_side, () => form.position_action], syncTradeSide, { immediate: true })

function applyMarketRules() {
  if (form.market === 'CN') Object.assign(form, { exchange: form.symbol?.startsWith('6') ? 'SSE' : 'SZSE', instrument_type: 'equity', quote_asset: 'CNY', position_side: 'long' })
  if (form.market === 'HK') Object.assign(form, { exchange: 'SEHK', instrument_type: 'equity', quote_asset: 'HKD' })
  if (form.market === 'US') Object.assign(form, { exchange: form.exchange || 'NASDAQ', instrument_type: 'equity', quote_asset: 'USD' })
  if (form.market === 'CRYPTO') Object.assign(form, { exchange: form.exchange || 'binance', quote_asset: 'USDT' })
  if (!supportsShort.value) form.position_side = 'long'
  if (isTransfer.value) { form.position_action = undefined; form.side = undefined }
  quantityRule.step = form.market === 'CN' ? '100' : '1'
  quantityRule.minimum = quantityRule.step
  quantityRule.precision = 0
  syncTradeSide()
  void loadRules()
}

function syncTradeSide() {
  if (form.record_type !== 'trade' || !form.position_action) return
  form.side = form.position_side === 'long'
    ? (form.position_action === 'open' ? 'buy' : 'sell')
    : (form.position_action === 'open' ? 'sell' : 'buy')
}

async function loadRules() {
  if (!form.symbol || form.market !== 'CRYPTO') return
  const response = await realTradesApi.getAssetRules({ market: form.market, exchange: form.exchange, symbol: form.symbol, instrument_type: form.instrument_type })
  if (response.success) Object.assign(quantityRule, response.data)
}

function submit() {
  error.value = ''
  if (!form.symbol || !form.quantity || (form.record_type === 'trade' && !form.price)) {
    error.value = '请填写标的、数量和价格'
    return
  }
  emit('submit', { ...form, tags: [...(form.tags || [])] })
}
</script>

<style scoped>
.record-form { display: grid; gap: 14px; }
.form-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }
label, fieldset { display: grid; gap: 6px; font-size: 13px; color: #606266; }
input, select, textarea { box-sizing: border-box; width: 100%; min-height: 36px; border: 1px solid #dcdfe6; border-radius: 4px; padding: 7px 10px; background: #fff; color: #303133; }
fieldset { grid-template-columns: auto auto 1fr; align-items: center; border: 0; padding: 0; }
fieldset label { display: flex; align-items: center; gap: 5px; }
fieldset input { width: auto; min-height: auto; }
.span-2 { grid-column: 1 / -1; }
.intent { justify-self: end; color: #409eff; }
.advanced-toggle { justify-self: start; border: 0; background: transparent; color: #409eff; cursor: pointer; padding: 0; }
.advanced-fields { padding-top: 4px; border-top: 1px solid #ebeef5; }
.form-error { color: #f56c6c; margin: 0; }
.form-actions { display: flex; justify-content: flex-end; }
.form-actions button { min-width: 96px; border: 0; border-radius: 4px; padding: 9px 16px; background: #409eff; color: white; cursor: pointer; }
@media (max-width: 640px) { .form-grid { grid-template-columns: 1fr; } .span-2 { grid-column: auto; } }
</style>
