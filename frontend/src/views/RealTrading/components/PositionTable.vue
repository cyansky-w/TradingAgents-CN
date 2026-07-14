<template>
  <div class="table-wrap">
    <table><thead><tr><th>标的</th><th>方向</th><th>数量</th><th>均价 / 标记价</th><th>原币市值</th><th>{{ baseCurrency }} 市值</th><th>盈亏</th><th>权重</th><th>状态</th></tr></thead>
      <tbody><tr v-for="position in positions" :key="position.storage_key" data-testid="position-row" @click="emit('open', position)">
        <td><strong>{{ position.symbol }}</strong><small>{{ position.exchange }} · {{ instrument(position.instrument_type) }}</small></td>
        <td><span :class="['side', position.position_side]">{{ position.position_side === 'long' ? '多头' : '空头' }}</span></td>
        <td>{{ position.quantity }}</td>
        <td>{{ value(position.average_entry_price) }} / {{ value(position.mark_price) }}</td>
        <td>{{ position.quote_asset }} {{ value(position.market_value) }}</td>
        <td>{{ position.converted === false ? '-' : value(position.base_market_value) }}</td>
        <td>{{ value(position.base_unrealized_pnl) }}</td>
        <td data-testid="position-weight">{{ position.converted === false || position.weight_percent == null ? '-' : formatDecimal(position.weight_percent, 2) + '%' }}</td>
        <td><span v-if="position.converted === false" data-testid="conversion-unavailable" class="warning">未换算</span><span v-if="position.quote_stale" data-testid="quote-stale" class="muted">行情过期</span></td>
      </tr></tbody>
    </table>
    <div v-if="positions.length === 0" class="empty">暂无持仓</div>
  </div>
</template>

<script setup lang="ts">
import type { BaseCurrency, InstrumentType, PortfolioPosition } from '@/api/realTrades'
import { formatDecimal } from '@/utils/portfolioDecimal'
defineProps<{ positions: PortfolioPosition[]; baseCurrency: BaseCurrency }>()
const emit = defineEmits<{ open: [position: PortfolioPosition] }>()
const value = (input?: string | null) => input == null ? '-' : formatDecimal(input, 4)
const instrument = (value: InstrumentType) => ({ equity: '股票', crypto_spot: '现货', crypto_linear_perpetual: 'USDT 永续' }[value])
</script>

<style scoped>
.table-wrap { overflow-x: auto; background: #fff; } table { width: 100%; min-width: 1050px; border-collapse: collapse; } th, td { padding: 12px; text-align: left; border-bottom: 1px solid #ebeef5; font-size: 13px; white-space: nowrap; } th { color: #606266; background: #f7f8fa; } td small { display: block; margin-top: 4px; color: #909399; } .side { font-weight: 600; } .long { color: #2f855a; } .short { color: #c53030; } .warning { color: #b7791f; } .muted { display: block; color: #909399; } .empty { padding: 44px; text-align: center; color: #909399; }
</style>
