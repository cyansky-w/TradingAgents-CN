import { ApiClient } from './request'

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
}

export interface PaginatedRecords {
  items: RealTradeRecord[]
  total: number
  page: number
  page_size: number
}

export const realTradesApi = {
  async createRecord(data: CreateTradePayload) {
    return ApiClient.post<{ record: RealTradeRecord }>('/api/real-trades/record', data, { showLoading: true })
  },
  async updateRecord(id: string, data: UpdateTradePayload) {
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
  async getPositions() {
    return ApiClient.get<{ items: RealPositionItem[]; total_market_value: number }>('/api/real-trades/positions')
  },
  async getDashboard(days = 90) {
    return ApiClient.get<DashboardData>('/api/real-trades/dashboard', { days })
  },
}
