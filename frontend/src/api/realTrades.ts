import { ApiClient } from './request'

export type DecimalString = string
export type Market = 'CN' | 'HK' | 'US' | 'CRYPTO'
export type InstrumentType = 'equity' | 'crypto_linear_perpetual'
export type PositionSide = 'long' | 'short'
export type PositionAction = 'open' | 'close'
export type RecordType = 'trade' | 'opening_position' | 'transfer_in' | 'transfer_out'
export type BaseCurrency = 'CNY' | 'USD' | 'USDT'

export interface CreateLedgerRecordPayload {
  record_type: RecordType
  market: Market
  exchange: string
  symbol: string
  instrument_type: InstrumentType
  quote_asset: string
  side?: 'buy' | 'sell'
  position_side: PositionSide
  position_action?: PositionAction
  price?: DecimalString
  quantity: DecimalString
  fee_amount?: DecimalString
  fee_currency?: string
  funding_fee?: DecimalString
  leverage?: DecimalString
  initial_margin?: DecimalString
  margin_mode?: 'cross' | 'isolated'
  trade_time: string
  version?: number
  reason?: string
  tags?: string[]
  notes?: string | null
}

export interface AssetRules {
  quantity_type: 'integer' | 'decimal'
  step: DecimalString
  minimum: DecimalString
  precision: number
}

export interface PortfolioPosition {
  storage_key: string
  market: Market
  exchange: string
  symbol: string
  instrument_type: InstrumentType
  position_side: PositionSide
  quote_asset: string
  quantity: DecimalString
  average_entry_price?: DecimalString | null
  mark_price?: DecimalString | null
  market_value?: DecimalString | null
  base_market_value?: DecimalString | null
  base_unrealized_pnl?: DecimalString | null
  weight_percent?: DecimalString | null
  converted?: boolean
  conversion_error?: string
  quote_stale?: boolean
}

export interface PortfolioDashboard {
  base_currency: BaseCurrency
  total_market_value: DecimalString
  total_cost: DecimalString
  realized_pnl: DecimalString
  unrealized_pnl: DecimalString
  total_pnl: DecimalString
  holding_count: number
  total_trade_count: number
  excluded: Array<Record<string, unknown>>
  pnl_curve: Array<{ date: string; cumulative_pnl: DecimalString }>
}

export interface RealTradeRecord {
  id: string
  code: string
  market: string
  currency: string
  name?: string | null
  side: 'buy' | 'sell'
  price: number
  quantity: number
  amount: number
  commission: number
  fee_amount?: DecimalString
  fee_currency?: string
  base_fee_amount?: DecimalString | null
  base_fee_currency?: BaseCurrency | null
  fee_conversion_error?: string | null
  trade_date: string
  reason: string
  tags: string[]
  notes?: string | null
  pnl?: number | null
  created_at: string
  updated_at: string
}

export interface RealPositionItem {
  code: string
  market: string
  currency: string
  name?: string | null
  quantity: number
  avg_cost: number
  total_cost: number
  last_price?: number | null
  market_value: number
  unrealized_pnl?: number | null
  pnl_percent?: number | null
  weight_percent?: number | null
}

export interface DashboardData {
  total_equity?: number | null
  total_cost: number
  total_pnl: number
  realized_pnl: number
  unrealized_pnl: number
  win_rate: number
  profit_loss_ratio: number
  holding_count: number
  total_trade_count: number
  pnl_curve: Array<{ date: string; cumulative_pnl: number }>
  sector_distribution: Array<{ code: string; name: string; market_value: number; percentage: number }>
}

export interface CreateTradePayload {
  code: string
  side: 'buy' | 'sell'
  price: number
  quantity: number
  commission?: number
  trade_date: string
  reason: string
  tags?: string[]
  notes?: string | null
}

export interface UpdateTradePayload {
  code?: string
  side?: 'buy' | 'sell'
  price?: number
  quantity?: number
  commission?: number
  trade_date?: string
  reason?: string
  tags?: string[]
  notes?: string | null
}

export interface RecordsParams {
  code?: string
  side?: string
  tags?: string
  pnl?: string
  start?: string
  end?: string
  page?: number
  page_size?: number
  sort?: string
  base_currency?: BaseCurrency
}

export interface PaginatedRecords {
  items: RealTradeRecord[]
  total: number
  page: number
  page_size: number
}

export const realTradesApi = {
  async createRecord(data: CreateTradePayload | CreateLedgerRecordPayload) {
    return ApiClient.post<{ record: RealTradeRecord }>('/api/real-trades/record', data, { showLoading: true })
  },
  async updateRecord(id: string, data: UpdateTradePayload | CreateLedgerRecordPayload) {
    return ApiClient.put<{ message: string }>(`/api/real-trades/record/${id}`, data, { showLoading: true })
  },
  async deleteRecord(id: string) {
    return ApiClient.delete<{ message: string }>(`/api/real-trades/record/${id}`)
  },
  async getRecord(id: string) {
    return ApiClient.get<{ record: RealTradeRecord }>(`/api/real-trades/record/${id}`)
  },
  async getRecords(params: RecordsParams) {
    return ApiClient.get<PaginatedRecords>('/api/real-trades/records', params)
  },
  async getPositions(base_currency: BaseCurrency = 'CNY') {
    return ApiClient.get<{ items: PortfolioPosition[]; total_market_value: DecimalString; excluded: Array<Record<string, unknown>> }>('/api/real-trades/positions', { base_currency })
  },
  async getDashboard(days = 90, base_currency: BaseCurrency = 'CNY') {
    return ApiClient.get<PortfolioDashboard>('/api/real-trades/dashboard', { days, base_currency })
  },
  async getAssetRules(params: { market: Market; exchange: string; symbol: string; instrument_type: InstrumentType }) {
    return ApiClient.get<AssetRules>('/api/real-trades/asset-rules', params)
  },
  async getPortfolioPreference() {
    return ApiClient.get<{ user_id: string; base_currency: BaseCurrency }>('/api/real-trades/portfolio-preference')
  },
  async updatePortfolioPreference(base_currency: BaseCurrency) {
    return ApiClient.put<{ user_id: string; base_currency: BaseCurrency }>('/api/real-trades/portfolio-preference', { base_currency })
  },
}
