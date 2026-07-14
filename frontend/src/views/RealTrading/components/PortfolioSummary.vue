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
      <div><span>排除估值</span><strong>{{ dashboard.excluded?.length || 0 }}</strong></div>
    </div>
  </section>
</template>

<script setup lang="ts">
import Decimal from 'decimal.js'
import type { BaseCurrency, PortfolioDashboard } from '@/api/realTrades'
import { formatDecimal } from '@/utils/portfolioDecimal'

const props = defineProps<{ dashboard: PortfolioDashboard; baseCurrency: BaseCurrency }>()
const emit = defineEmits<{ 'update:baseCurrency': [value: BaseCurrency] }>()
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
.metrics div { display: grid; gap: 7px; padding: 14px; background: #fff; } .metrics span { color: #909399; font-size: 12px; } .metrics strong { font-size: 18px; }
.positive { color: #2f855a; } .negative { color: #c53030; }
@media (max-width: 900px) { .metrics { grid-template-columns: repeat(2, 1fr); } .summary-heading { align-items: start; } }
</style>
