<script setup lang="ts">
import type { BaseCurrency, CreateLedgerRecordPayload, PortfolioDashboard, PortfolioPosition } from '@/api/realTrades'
import { LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent } from 'echarts/components'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { ElMessage, ElMessageBox } from 'element-plus'
import { computed, onMounted, ref } from 'vue'
import VChart from 'vue-echarts'
import { useRouter } from 'vue-router'
import { realTradesApi } from '@/api/realTrades'
import PortfolioSummary from './components/PortfolioSummary.vue'
import PositionTable from './components/PositionTable.vue'
import TradeRecordForm from './components/TradeRecordForm.vue'
import TradeRecordsDialog from './components/TradeRecordsDialog.vue'

use([CanvasRenderer, LineChart, GridComponent, TooltipComponent])
const router = useRouter()
const baseCurrency = ref<BaseCurrency>('CNY')
const positions = ref<PortfolioPosition[]>([])
const dashboard = ref<PortfolioDashboard>({ base_currency: 'CNY', total_market_value: '0', total_cost: '0', realized_pnl: '0', unrealized_pnl: '0', total_pnl: '0', holding_count: 0, total_trade_count: 0, excluded: [], pnl_curve: [] })
const records = ref<any[]>([])
const recordsTotal = ref(0)
const recordsVisible = ref(false)
const formVisible = ref(false)
const submitting = ref(false)
const editingId = ref<string | null>(null)
const now = () => new Date().toISOString().slice(0, 19)
const defaultRecord = (): CreateLedgerRecordPayload => ({ record_type: 'trade', market: 'CN', exchange: 'SSE', symbol: '', instrument_type: 'equity', quote_asset: 'CNY', side: 'buy', position_side: 'long', position_action: 'open', price: '', quantity: '100', fee_amount: '', fee_currency: 'CNY', trade_time: now(), reason: '', tags: [], notes: null })
const formInitial = ref<CreateLedgerRecordPayload>(defaultRecord())
let valuationRequestId = 0

const chartOption = computed(() => ({ tooltip: { trigger: 'axis' }, grid: { left: 70, right: 24, top: 20, bottom: 35 }, xAxis: { type: 'category', data: dashboard.value.pnl_curve.map(item => item.date) }, yAxis: { type: 'value' }, series: [{ type: 'line', smooth: true, data: dashboard.value.pnl_curve.map(item => Number(item.cumulative_pnl)), lineStyle: { color: '#2f855a' }, itemStyle: { color: '#2f855a' } }] }))

async function loadPreference() {
  const response = await realTradesApi.getPortfolioPreference(); if (response.success)
    baseCurrency.value = response.data.base_currency
}
async function fetchPositions() { const response = await realTradesApi.getPositions(baseCurrency.value); return response }
async function fetchDashboard() { const response = await realTradesApi.getDashboard(90, baseCurrency.value); return response }
async function refreshValuation() {
  const requestId = ++valuationRequestId
  const [positionsResponse, dashboardResponse] = await Promise.all([fetchPositions(), fetchDashboard()])
  if (requestId !== valuationRequestId)
    return
  if (positionsResponse.success)
    positions.value = positionsResponse.data.items || []
  if (dashboardResponse.success)
    dashboard.value = dashboardResponse.data
}
async function changeBaseCurrency(value: BaseCurrency) { await realTradesApi.updatePortfolioPreference(value); baseCurrency.value = value; await refreshValuation() }
async function fetchRecords() { const response = await realTradesApi.getRecords({ page: 1, page_size: 100, base_currency: baseCurrency.value }); if (response.success) { records.value = response.data.items || []; recordsTotal.value = response.data.total || 0 } }

function openCreate() { editingId.value = null; formInitial.value = defaultRecord(); formVisible.value = true }
function openEdit(record: any) { editingId.value = record.id; formInitial.value = { record_type: record.record_type || 'trade', market: record.market, exchange: record.exchange, symbol: record.symbol || record.code, instrument_type: record.instrument_type || 'equity', quote_asset: record.quote_asset || record.currency, side: record.side, position_side: record.position_side || 'long', position_action: record.position_action || (record.side === 'buy' ? 'open' : 'close'), price: String(record.price || ''), quantity: String(record.quantity), fee_amount: String(record.fee_amount ?? record.commission ?? ''), fee_currency: record.fee_currency || record.currency, trade_time: record.trade_time || record.trade_date, version: record.version, reason: record.reason, tags: record.tags || [], notes: record.notes || null }; recordsVisible.value = false; formVisible.value = true }
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
    const responseDetail
      = typeof error === 'object' && error !== null
        ? (error as { response?: { data?: { detail?: unknown } } }).response?.data?.detail
        : undefined
    const message
      = typeof responseDetail === 'string'
        ? responseDetail
        : error instanceof Error
          ? error.message
          : String(error)
    if (
      payload.position_action === 'close'
      && message.includes('close quantity exceeds available')
    ) {
      ElMessage.warning('当前持仓已变化，请刷新持仓后重新选择平仓标的')
      return
    }
    throw error
  } finally {
    submitting.value = false
  }
}
async function removeRecord(record: any) { await ElMessageBox.confirm(`确认删除 ${record.symbol || record.code} 记录？`, '删除确认', { type: 'warning' }); const response = await realTradesApi.deleteRecord(record.id); if (response.success) { await Promise.all([refreshValuation(), fetchRecords()]); ElMessage.success('记录已删除') } }
function openPosition(position: PortfolioPosition) {
  if (position.instrument_type === 'equity')
    router.push({ name: 'StockDetail', params: { code: position.symbol } }); else router.push({ name: 'SingleAnalysis', query: { stock: position.symbol, market: 'CRYPTO', exchange: position.exchange } })
}

onMounted(async () => { try { await loadPreference(); await refreshValuation() } catch (error) { console.error('加载实盘持仓失败', error) } })
</script>

<template>
  <main class="portfolio-page">
    <PortfolioSummary :dashboard="dashboard" :base-currency="baseCurrency" :excluded="dashboard.excluded" @update:base-currency="changeBaseCurrency" />
    <div class="toolbar">
      <div><strong>当前持仓</strong><span>{{ positions.length }} 个持仓方向</span></div><div>
        <button @click="recordsVisible = true; fetchRecords()">
          记录
        </button><button data-testid="create-record" @click="openCreate">
          新增
        </button><button title="刷新" @click="refreshValuation">
          ↻
        </button>
      </div>
    </div>
    <PositionTable :positions="positions" :base-currency="baseCurrency" @open="openPosition" />
    <section class="history">
      <header><h2>累计已实现盈亏</h2><span>{{ baseCurrency }}</span></header><VChart v-if="dashboard.pnl_curve.length" :option="chartOption" class="chart" /><div v-else class="empty">
        暂无已实现盈亏记录
      </div>
    </section>

    <div v-if="formVisible" class="overlay" @click.self="formVisible = false">
      <section class="form-dialog">
        <header>
          <h2>{{ editingId ? '编辑记录' : '新增记录' }}</h2><button @click="formVisible = false">
            ×
          </button>
        </header><TradeRecordForm :initial-value="formInitial" :positions="positions" :editing="Boolean(editingId)" :submitting="submitting" @submit="submitRecord" />
      </section>
    </div>
    <TradeRecordsDialog v-model="recordsVisible" :records="records" :total="recordsTotal" @refresh="fetchRecords" @edit="openEdit" @delete="removeRecord" />
  </main>
</template>

<style scoped>
.portfolio-page { min-height: 100%; background: #f5f7fa; color: #303133; } .toolbar { display: flex; justify-content: space-between; align-items: center; gap: 16px; padding: 14px 20px; } .toolbar span { margin-left: 10px; color: #909399; font-size: 12px; } button { min-height: 34px; border: 1px solid #dcdfe6; border-radius: 4px; padding: 0 13px; background: #fff; cursor: pointer; } .toolbar button + button { margin-left: 8px; } .toolbar button:nth-child(2) { border-color: #409eff; background: #409eff; color: #fff; } .history { margin-top: 16px; padding: 18px 20px; background: #fff; } .history header { display: flex; justify-content: space-between; } .history h2 { margin: 0; font-size: 16px; } .chart { height: 260px; } .empty { padding: 48px; text-align: center; color: #909399; } .overlay { position: fixed; inset: 0; z-index: 1900; display: grid; place-items: center; padding: 20px; background: rgba(0,0,0,.45); } .form-dialog { width: min(720px, 100%); max-height: 90vh; overflow: auto; border-radius: 6px; padding: 18px; background: #fff; } .form-dialog header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; } .form-dialog h2 { margin: 0; font-size: 18px; } .form-dialog header button { border: 0; font-size: 24px; }
</style>
