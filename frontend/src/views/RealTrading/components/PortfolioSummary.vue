<template>
  <section class="summary-band">
    <div class="summary-heading">
      <div><h1>实盘持仓</h1><p>持仓市值与盈亏，不包含未投资现金</p></div>
      <label>基准币种
        <select data-testid="base-currency" :value="baseCurrency" @change="changeCurrency">
          <option value="CNY">CNY</option><option value="USD">USD</option><option value="USDT">USDT</option>
        </select>
      </label>
    </div>
    <div class="metrics">
      <div><span>持仓市值</span><strong>{{ money(dashboard.total_market_value) }}</strong></div>
      <div><span>总盈亏</span><strong :class="tone(dashboard.total_pnl)">{{ money(dashboard.total_pnl) }}</strong></div>
      <div><span>已实现</span><strong :class="tone(dashboard.realized_pnl)">{{ money(dashboard.realized_pnl) }}</strong></div>
      <div><span>未实现</span><strong :class="tone(dashboard.unrealized_pnl)">{{ money(dashboard.unrealized_pnl) }}</strong></div>
      <div><span>持仓 / 记录</span><strong>{{ dashboard.holding_count }} / {{ dashboard.total_trade_count }}</strong></div>
      <div><span>排除估值</span><button data-testid="excluded-valuation-button" :disabled="!excluded.length" @click="excludedVisible = true">{{ excluded.length }}</button></div>
    </div>
  </section>
  <div v-if="excludedVisible" class="excluded-overlay" @click.self="excludedVisible = false">
    <section class="excluded-dialog">
      <header><h2>排除估值明细</h2><button type="button" aria-label="关闭" @click="excludedVisible = false">×</button></header>
      <div v-for="(item, index) in excluded" :key="`${String(item.storage_key || item.symbol || 'item')}-${index}`" class="excluded-item">
        <strong>{{ item.symbol || item.storage_key || '-' }}</strong>
        <span>{{ item.position_side === 'short' ? '空头' : item.position_side === 'long' ? '多头' : '-' }} · {{ item.market || '-' }} / {{ item.exchange || '-' }}</span>
        <p>{{ item.error || '-' }}</p>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import Decimal from 'decimal.js'
import type { BaseCurrency, PortfolioDashboard } from '@/api/realTrades'
import { formatDecimal } from '@/utils/portfolioDecimal'

const props = defineProps<{ dashboard: PortfolioDashboard; baseCurrency: BaseCurrency; excluded: Array<Record<string, unknown>> }>()
const emit = defineEmits<{ 'update:baseCurrency': [value: BaseCurrency] }>()
const excludedVisible = ref(false)
const excluded = computed(() => props.excluded || [])
const symbols = { CNY: '¥', USD: '$', USDT: '₮' }
const money = (value: string) => `${symbols[props.baseCurrency]}${formatDecimal(value || '0', 2)}`
const tone = (value: string) => new Decimal(value || '0').isNegative() ? 'negative' : 'positive'
function changeCurrency(event: Event) { emit('update:baseCurrency', (event.target as HTMLSelectElement).value as BaseCurrency) }
</script>

<style scoped>
.summary-band { padding: 20px; background: #fff; border-bottom: 1px solid #e4e7ed; }
.summary-heading { display: flex; justify-content: space-between; gap: 20px; align-items: end; }
h1 { margin: 0; font-size: 22px; } p { margin: 5px 0 0; color: #909399; font-size: 13px; }
label { display: grid; gap: 5px; color: #606266; font-size: 12px; } select { min-width: 110px; height: 34px; border: 1px solid #dcdfe6; border-radius: 4px; }
.metrics { display: grid; grid-template-columns: repeat(6, minmax(110px, 1fr)); gap: 1px; margin-top: 18px; background: #ebeef5; border: 1px solid #ebeef5; }
.metrics div { display: grid; gap: 7px; padding: 14px; background: #fff; } .metrics span { color: #909399; font-size: 12px; } .metrics strong, .metrics button { font-size: 18px; }
.metrics button { width: fit-content; border: 0; padding: 0; background: transparent; cursor: pointer; } .metrics button:disabled { cursor: default; color: inherit; }
.positive { color: #2f855a; } .negative { color: #c53030; }
.excluded-overlay { position: fixed; inset: 0; z-index: 2000; display: grid; place-items: center; padding: 20px; background: rgba(0,0,0,.45); }
.excluded-dialog { width: min(560px, 100%); max-height: 80vh; overflow: auto; border-radius: 6px; padding: 18px; background: #fff; }
.excluded-dialog header { display: flex; justify-content: space-between; align-items: center; } .excluded-dialog h2 { margin: 0 0 12px; font-size: 18px; } .excluded-dialog header button { border: 0; background: transparent; font-size: 24px; cursor: pointer; }
.excluded-item { display: grid; gap: 4px; padding: 12px 0; border-top: 1px solid #ebeef5; } .excluded-item span, .excluded-item p { margin: 0; color: #606266; font-size: 13px; } .excluded-item p { color: #c53030; word-break: break-word; }
@media (max-width: 900px) { .metrics { grid-template-columns: repeat(2, 1fr); } .summary-heading { align-items: start; } }
</style>
