<template>
  <div class="real-trading">
    <!-- ==================== 仪表盘 ==================== -->
    <div class="dashboard-section">
      <div class="stat-cards">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-label">总盈亏</div>
          <div class="stat-value" :style="{ color: dash.total_pnl >= 0 ? '#67C23A' : '#F56C6C' }">
            ¥{{ fmtAmount(dash.total_pnl) }}
          </div>
        </el-card>
        <el-card shadow="hover" class="stat-card">
          <div class="stat-label">已实现盈亏</div>
          <div
            class="stat-value"
            :style="{ color: dash.realized_pnl >= 0 ? '#67C23A' : '#F56C6C' }"
          >
            ¥{{ fmtAmount(dash.realized_pnl) }}
          </div>
        </el-card>
        <el-card shadow="hover" class="stat-card">
          <div class="stat-label">未实现盈亏</div>
          <div
            class="stat-value"
            :style="{ color: dash.unrealized_pnl >= 0 ? '#67C23A' : '#F56C6C' }"
          >
            ¥{{ fmtAmount(dash.unrealized_pnl) }}
          </div>
        </el-card>
        <el-card shadow="hover" class="stat-card">
          <div class="stat-label">胜率</div>
          <div class="stat-value">{{ (dash.win_rate * 100).toFixed(1) }}%</div>
        </el-card>
        <el-card shadow="hover" class="stat-card">
          <div class="stat-label">盈亏比</div>
          <div class="stat-value">{{ fmtAmount(dash.profit_loss_ratio) }}</div>
        </el-card>
        <el-card shadow="hover" class="stat-card">
          <div class="stat-label">持仓数</div>
          <div class="stat-value">{{ dash.holding_count }}</div>
        </el-card>
      </div>

      <el-row :gutter="16" style="margin-top: 16px">
        <el-col :span="12">
          <el-card shadow="hover">
            <template #header><div class="card-hd">收益率曲线</div></template>
            <v-chart
              :option="pnlChartOption"
              style="height: 260px"
              v-if="dash.pnl_curve.length > 0"
            />
            <el-empty v-else description="暂无数据" :image-size="80" />
          </el-card>
        </el-col>
        <el-col :span="12">
          <el-card shadow="hover">
            <template #header><div class="card-hd">持仓分布</div></template>
            <v-chart
              :option="sectorChartOption"
              style="height: 260px"
              v-if="dash.sector_distribution.length > 0"
            />
            <el-empty v-else description="暂无数据" :image-size="80" />
          </el-card>
        </el-col>
      </el-row>
    </div>

    <!-- ==================== 操作栏 ==================== -->
    <div class="action-bar">
      <div class="action-bar-title">持仓列表</div>
      <div class="action-bar-btns">
        <el-button type="primary" :icon="Plus" @click="openAddDialog">添加交易</el-button>
        <el-button :icon="List" @click="openRecordsDialog">交易记录</el-button>
        <el-button :icon="Refresh" text @click="refreshAll">刷新</el-button>
      </div>
    </div>

    <!-- ==================== 持仓列表 ==================== -->
    <el-card shadow="hover" class="positions-section">
      <el-table :data="positions" v-loading="loadingPositions" size="small" stripe>
        <el-table-column label="代码" width="100">
          <template #default="{ row }">
            <el-link type="primary" @click="goStockDetail(row.code)">{{ row.code }}</el-link>
          </template>
        </el-table-column>
        <el-table-column label="名称" width="110">
          <template #default="{ row }">{{ row.name || '-' }}</template>
        </el-table-column>
        <el-table-column label="市场" width="70">
          <template #default="{ row }">
            <el-tag v-if="row.market === 'CN'" type="success" size="small">A股</el-tag>
            <el-tag v-else-if="row.market === 'HK'" type="warning" size="small">港股</el-tag>
            <el-tag v-else-if="row.market === 'US'" type="info" size="small">美股</el-tag>
            <el-tag v-else size="small">{{ row.market }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="数量" width="80" prop="quantity" />
        <el-table-column label="成本价" width="100">
          <template #default="{ row }"
            >{{ curSymbol(row.currency) }}{{ fmtPrice(row.avg_cost) }}</template
          >
        </el-table-column>
        <el-table-column label="成本总价" width="110">
          <template #default="{ row }"
            >{{ curSymbol(row.currency) }}{{ fmtAmount(row.total_cost) }}</template
          >
        </el-table-column>
        <el-table-column label="现价" width="100">
          <template #default="{ row }"
            >{{ curSymbol(row.currency) }}{{ fmtPrice(row.last_price) }}</template
          >
        </el-table-column>
        <el-table-column label="市值" width="110">
          <template #default="{ row }"
            >{{ curSymbol(row.currency) }}{{ fmtAmount(row.market_value) }}</template
          >
        </el-table-column>
        <el-table-column label="浮盈" width="120">
          <template #default="{ row }">
            <span :style="{ color: (row.unrealized_pnl ?? 0) >= 0 ? '#67C23A' : '#F56C6C' }">
              {{ curSymbol(row.currency) }}{{ fmtAmount(row.unrealized_pnl) }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="盈亏%" width="90">
          <template #default="{ row }">
            <span :style="{ color: (row.pnl_percent ?? 0) >= 0 ? '#67C23A' : '#F56C6C' }">
              {{ row.pnl_percent != null ? fmtAmount(row.pnl_percent) + '%' : '-' }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="占比%" width="80">
          <template #default="{ row }">{{
            row.weight_percent != null ? fmtAmount(row.weight_percent) + '%' : '-'
          }}</template>
        </el-table-column>
        <el-table-column label="操作" width="180">
          <template #default="{ row }">
            <el-button size="small" type="primary" link @click="goStockDetail(row.code)"
              >详情</el-button
            >
            <el-button size="small" type="success" link @click="goAnalysis(row.code)"
              >分析</el-button
            >
          </template>
        </el-table-column>
      </el-table>
      <el-empty
        v-if="!loadingPositions && positions.length === 0"
        description="暂无持仓"
        :image-size="100"
      />
    </el-card>

    <!-- ==================== 添加/编辑交易弹窗 ==================== -->
    <el-dialog
      v-model="addDialogVisible"
      :title="editingId ? '编辑交易记录' : '新增交易记录'"
      width="520px"
      @opened="onAddDialogOpened"
    >
      <el-form :model="form" label-width="90px">
        <el-form-item label="股票代码" required>
          <el-input
            v-model="form.code"
            placeholder="A股:600519 | 港股:0700 | 美股:AAPL"
            @input="detectMarket"
          />
          <div v-if="detectedMarket" style="margin-top: 4px">
            <el-tag v-if="detectedMarket === 'CN'" type="success" size="small">A股 (CNY)</el-tag>
            <el-tag v-else-if="detectedMarket === 'HK'" type="warning" size="small"
              >港股 (HKD)</el-tag
            >
            <el-tag v-else-if="detectedMarket === 'US'" type="info" size="small">美股 (USD)</el-tag>
            <span style="margin-left: 8px; font-size: 12px; color: #909399">
              {{ detectedMarket === 'CN' ? 'T+1结算' : 'T+0结算' }}
            </span>
          </div>
        </el-form-item>
        <el-form-item label="交易类型" required>
          <el-radio-group v-model="form.side">
            <el-radio-button label="buy">买入</el-radio-button>
            <el-radio-button label="sell">卖出</el-radio-button>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="交易日期" required>
          <el-date-picker
            v-model="form.trade_date"
            type="datetime"
            placeholder="选择时间"
            format="YYYY-MM-DD HH:mm"
            value-format="YYYY-MM-DDTHH:mm:ss"
            style="width: 100%"
          />
        </el-form-item>
        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item label="成交单价" required>
              <el-input-number
                v-model="form.price"
                :min="0.01"
                :precision="2"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="数量(股)" required>
              <el-input-number v-model="form.quantity" :min="1" style="width: 100%" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item label="预估金额">
              <el-input :model-value="estimatedAmount" disabled />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="手续费">
              <el-input-number
                v-model="form.commission"
                :min="0"
                :precision="2"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="交易原因" required>
          <el-input
            v-model="form.reason"
            type="textarea"
            :rows="2"
            placeholder="记录交易原因，便于复盘"
          />
        </el-form-item>
        <el-form-item label="标签">
          <el-select
            v-model="form.tags"
            multiple
            filterable
            allow-create
            placeholder="输入后回车"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="备注">
          <el-input
            v-model="form.notes"
            type="textarea"
            :rows="2"
            placeholder="止损计划、后续跟踪等"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="addDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitAddRecord" :loading="submitting">{{
          editingId ? '确认修改' : '确认添加'
        }}</el-button>
      </template>
    </el-dialog>

    <!-- ==================== 交易记录列表弹窗 ==================== -->
    <el-dialog v-model="recordsDialogVisible" title="交易记录" width="1000px">
      <!-- 筛选栏 -->
      <div class="records-filter">
        <el-input
          v-model="recordsFilter.code"
          placeholder="标的代码"
          clearable
          style="width: 120px"
        />
        <el-date-picker
          v-model="recordsFilter.dateRange"
          type="daterange"
          range-separator="~"
          start-placeholder="起始"
          end-placeholder="结束"
          format="YYYY-MM-DD"
          value-format="YYYY-MM-DD"
          style="width: 240px"
        />
        <el-select v-model="recordsFilter.side" placeholder="方向" clearable style="width: 90px">
          <el-option label="买入" value="buy" />
          <el-option label="卖出" value="sell" />
        </el-select>
        <el-input
          v-model="recordsFilter.tags"
          placeholder="标签(逗号分隔)"
          clearable
          style="width: 150px"
        />
        <el-select v-model="recordsFilter.pnl" placeholder="盈亏" clearable style="width: 90px">
          <el-option label="盈利" value="profit" />
          <el-option label="亏损" value="loss" />
        </el-select>
        <el-button type="primary" :icon="Search" @click="searchRecords">搜索</el-button>
        <el-button :icon="RefreshLeft" @click="resetRecordsFilter">重置</el-button>
      </div>

      <el-table
        :data="records"
        v-loading="loadingRecords"
        size="small"
        stripe
        style="margin-top: 12px"
      >
        <el-table-column label="时间" width="160">
          <template #default="{ row }">{{ formatDateTime(row.trade_date) }}</template>
        </el-table-column>
        <el-table-column label="代码" width="100">
          <template #default="{ row }">
            <el-link type="primary" @click="goStockDetail(row.code)">{{ row.code }}</el-link>
          </template>
        </el-table-column>
        <el-table-column label="名称" width="100">
          <template #default="{ row }">{{ row.name || '-' }}</template>
        </el-table-column>
        <el-table-column label="方向" width="70">
          <template #default="{ row }">
            <el-tag :type="row.side === 'buy' ? 'success' : 'danger'" size="small">
              {{ row.side === 'buy' ? '买入' : '卖出' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="价格" width="90">
          <template #default="{ row }"
            >{{ curSymbol(row.currency) }}{{ fmtPrice(row.price) }}</template
          >
        </el-table-column>
        <el-table-column label="数量" width="80" prop="quantity" />
        <el-table-column label="金额" width="110">
          <template #default="{ row }"
            >{{ curSymbol(row.currency) }}{{ fmtAmount(row.amount) }}</template
          >
        </el-table-column>
        <el-table-column label="盈亏" width="110">
          <template #default="{ row }">
            <span
              v-if="row.side === 'sell' && row.pnl != null"
              :style="{ color: row.pnl >= 0 ? '#67C23A' : '#F56C6C' }"
            >
              {{ curSymbol(row.currency) }}{{ fmtAmount(row.pnl) }}
            </span>
            <span v-else style="color: #909399">-</span>
          </template>
        </el-table-column>
        <el-table-column label="原因" min-width="150">
          <template #default="{ row }">{{ row.reason }}</template>
        </el-table-column>
        <el-table-column label="标签" width="120">
          <template #default="{ row }">
            <el-tag v-for="tag in row.tags" :key="tag" size="small" style="margin: 1px 2px">{{
              tag
            }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="130">
          <template #default="{ row }">
            <el-button size="small" type="primary" link @click="openEditDialog(row)"
              >编辑</el-button
            >
            <el-button size="small" type="danger" link @click="deleteRecord(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="records-pagination" v-if="recordsTotal > 0">
        <el-pagination
          v-model:current-page="recordsPage"
          v-model:page-size="recordsPageSize"
          :total="recordsTotal"
          :page-sizes="[10, 20, 50, 100]"
          layout="total, sizes, prev, pager, next"
          @change="searchRecords"
        />
      </div>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, List, Refresh, Search, RefreshLeft } from '@element-plus/icons-vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart, PieChart } from 'echarts/charts'
import {
  TitleComponent,
  TooltipComponent,
  LegendComponent,
  GridComponent
} from 'echarts/components'
import {
  realTradesApi,
  type RealPositionItem,
  type RealTradeRecord,
  type DashboardData
} from '@/api/realTrades'
import { formatDateTime } from '@/utils/datetime'

use([
  CanvasRenderer,
  LineChart,
  PieChart,
  TitleComponent,
  TooltipComponent,
  LegendComponent,
  GridComponent
])

const router = useRouter()

// ---- 仪表盘 ----
const dash = reactive<DashboardData>({
  total_cost: 0,
  total_pnl: 0,
  realized_pnl: 0,
  unrealized_pnl: 0,
  win_rate: 0,
  profit_loss_ratio: 0,
  holding_count: 0,
  total_trade_count: 0,
  pnl_curve: [],
  sector_distribution: []
})

const pnlChartOption = computed(() => ({
  tooltip: { trigger: 'axis' as const },
  grid: { left: 60, right: 20, top: 20, bottom: 30 },
  xAxis: {
    type: 'category' as const,
    data: dash.pnl_curve.map(i => i.date),
    axisLabel: { rotate: 30, fontSize: 10 }
  },
  yAxis: {
    type: 'value' as const,
    axisLabel: { formatter: (v: number) => '¥' + (v / 1000).toFixed(0) + 'k' }
  },
  series: [
    {
      type: 'line',
      data: dash.pnl_curve.map(i => i.cumulative_pnl),
      smooth: true,
      lineStyle: { color: '#67C23A' },
      itemStyle: { color: '#67C23A' },
      areaStyle: {
        color: {
          type: 'linear',
          x: 0,
          y: 0,
          x2: 0,
          y2: 1,
          colorStops: [
            { offset: 0, color: 'rgba(103,194,58,0.25)' },
            { offset: 1, color: 'rgba(103,194,58,0.02)' }
          ]
        }
      }
    }
  ]
}))

const sectorChartOption = computed(() => ({
  tooltip: { trigger: 'item' as const, formatter: '{b}: {c} ({d}%)' },
  series: [
    {
      type: 'pie',
      radius: ['40%', '70%'],
      center: ['50%', '50%'],
      data: dash.sector_distribution.map(i => ({ name: i.name || i.code, value: i.market_value })),
      label: { formatter: '{b}\n{d}%', fontSize: 11 }
    }
  ]
}))

// ---- 持仓 ----
const positions = ref<RealPositionItem[]>([])
const loadingPositions = ref(false)

// ---- 添加/编辑交易表单 ----
const addDialogVisible = ref(false)
const submitting = ref(false)
const editingId = ref<string | null>(null)
const detectedMarket = ref('')

const nowStr = () => {
  const d = new Date()
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
}

const form = reactive({
  code: '',
  side: 'buy' as 'buy' | 'sell',
  price: 0,
  quantity: 100,
  commission: 0,
  trade_date: nowStr(),
  reason: '',
  tags: [] as string[],
  notes: ''
})

const estimatedAmount = computed(() => {
  const amt = (form.price || 0) * (form.quantity || 0)
  return '¥' + amt.toFixed(2)
})

function detectMarket() {
  const code = form.code.trim().toUpperCase()
  if (!code) {
    detectedMarket.value = ''
    return
  }
  if (/^[A-Z]+$/.test(code)) {
    detectedMarket.value = 'US'
    return
  }
  if (/^\d{4,5}$/.test(code) || code.endsWith('.HK')) {
    detectedMarket.value = 'HK'
    return
  }
  if (/^\d{6}$/.test(code)) {
    detectedMarket.value = 'CN'
    return
  }
  detectedMarket.value = 'CN'
}

function openAddDialog() {
  editingId.value = null
  form.code = ''
  form.side = 'buy'
  form.price = 0
  form.quantity = 100
  form.commission = 0
  form.trade_date = nowStr()
  form.reason = ''
  form.tags = []
  form.notes = ''
  detectedMarket.value = ''
  addDialogVisible.value = true
}

async function openEditDialog(row: RealTradeRecord) {
  editingId.value = row.id
  form.code = row.code
  form.side = row.side
  form.price = row.price
  form.quantity = row.quantity
  form.commission = row.commission
  form.trade_date = row.trade_date
  form.reason = row.reason
  form.tags = [...row.tags]
  form.notes = row.notes || ''
  detectMarket()
  addDialogVisible.value = true
}

function onAddDialogOpened() {
  // optional focus
}

async function submitAddRecord() {
  if (!form.code || !form.price || !form.quantity || !form.reason) {
    ElMessage.warning('请填写必填项')
    return
  }
  try {
    submitting.value = true
    const payload = {
      code: form.code,
      side: form.side,
      price: form.price,
      quantity: form.quantity,
      commission: form.commission || 0,
      trade_date: form.trade_date,
      reason: form.reason,
      tags: form.tags,
      notes: form.notes || null
    }
    if (editingId.value) {
      const res = await realTradesApi.updateRecord(editingId.value, payload)
      if (res.success) {
        ElMessage.success('修改成功')
        addDialogVisible.value = false
        await refreshAll()
      }
    } else {
      const res = await realTradesApi.createRecord(payload)
      if (res.success) {
        ElMessage.success('添加成功')
        addDialogVisible.value = false
        await refreshAll()
      }
    }
  } catch (e: any) {
    ElMessage.error(e?.message || '操作失败')
  } finally {
    submitting.value = false
  }
}

// ---- 交易记录列表 ----
const recordsDialogVisible = ref(false)
const records = ref<RealTradeRecord[]>([])
const loadingRecords = ref(false)
const recordsTotal = ref(0)
const recordsPage = ref(1)
const recordsPageSize = ref(20)

const recordsFilter = reactive({
  code: '',
  side: '',
  tags: '',
  pnl: '',
  dateRange: null as string[] | null
})

async function searchRecords() {
  try {
    loadingRecords.value = true
    const params: any = {
      page: recordsPage.value,
      page_size: recordsPageSize.value,
      sort: 'desc'
    }
    if (recordsFilter.code) params.code = recordsFilter.code
    if (recordsFilter.side) params.side = recordsFilter.side
    if (recordsFilter.tags) params.tags = recordsFilter.tags
    if (recordsFilter.pnl) params.pnl = recordsFilter.pnl
    if (recordsFilter.dateRange?.length === 2) {
      params.start = recordsFilter.dateRange[0]
      params.end = recordsFilter.dateRange[1]
    }
    const res = await realTradesApi.getRecords(params)
    if (res.success) {
      records.value = res.data.items || []
      recordsTotal.value = res.data.total || 0
    }
  } catch (e: any) {
    ElMessage.error(e?.message || '查询失败')
  } finally {
    loadingRecords.value = false
  }
}

function resetRecordsFilter() {
  recordsFilter.code = ''
  recordsFilter.side = ''
  recordsFilter.tags = ''
  recordsFilter.pnl = ''
  recordsFilter.dateRange = null
  recordsPage.value = 1
  searchRecords()
}

function openRecordsDialog() {
  recordsPage.value = 1
  searchRecords()
  recordsDialogVisible.value = true
}

async function deleteRecord(row: RealTradeRecord) {
  try {
    await ElMessageBox.confirm(
      `确认删除 ${row.code} ${row.side === 'buy' ? '买入' : '卖出'} 记录？`,
      '删除确认',
      { type: 'warning' }
    )
    const res = await realTradesApi.deleteRecord(row.id)
    if (res.success) {
      ElMessage.success('已删除')
      await searchRecords()
      await refreshAll()
    }
  } catch {
    /* cancelled */
  }
}

// ---- 公共 ----
function fmtPrice(n: number | null | undefined) {
  if (n == null || Number.isNaN(n)) return '-'
  return Number(n).toFixed(2)
}
function fmtAmount(n: number | null | undefined) {
  if (n == null || Number.isNaN(n)) return '-'
  return Number(n).toFixed(2)
}
function curSymbol(c: string | undefined) {
  if (!c) return '¥'
  if (c === 'CNY') return '¥'
  if (c === 'HKD') return 'HK$'
  if (c === 'USD') return '$'
  return ''
}
function goStockDetail(code: string) {
  if (!code) return
  router.push({ name: 'StockDetail', params: { code } })
}
function goAnalysis(code: string) {
  if (!code) return
  router.push({ name: 'SingleAnalysis', query: { stock: code } })
}

async function fetchDashboard() {
  try {
    const res = await realTradesApi.getDashboard(90)
    if (res.success) Object.assign(dash, res.data)
  } catch (e: any) {
    console.error('获取仪表盘失败:', e)
  }
}

async function fetchPositions() {
  try {
    loadingPositions.value = true
    const res = await realTradesApi.getPositions()
    if (res.success) positions.value = res.data.items || []
  } catch (e: any) {
    ElMessage.error(e?.message || '获取持仓失败')
  } finally {
    loadingPositions.value = false
  }
}

async function refreshAll() {
  const tasks = [fetchDashboard(), fetchPositions()]
  if (recordsDialogVisible.value) tasks.push(searchRecords())
  await Promise.all(tasks)
}

onMounted(() => {
  refreshAll()
})
</script>

<style scoped>
.real-trading {
  padding: 16px;
}

.stat-cards {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}
.stat-card {
  flex: 1;
  min-width: 140px;
  text-align: center;
}
.stat-label {
  font-size: 13px;
  color: #909399;
  margin-bottom: 6px;
}
.stat-value {
  font-size: 22px;
  font-weight: 700;
}

.card-hd {
  font-weight: 600;
}

.action-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin: 16px 0 12px;
}
.action-bar-title {
  font-weight: 600;
  font-size: 15px;
}
.action-bar-btns {
  display: flex;
  gap: 8px;
}

.positions-section {
  margin-bottom: 16px;
}

.records-filter {
  display: flex;
  gap: 8px;
  align-items: center;
  flex-wrap: wrap;
}
.records-pagination {
  display: flex;
  justify-content: flex-end;
  margin-top: 12px;
}
</style>
