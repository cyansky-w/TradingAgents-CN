import { flushPromises, mount } from '@vue/test-utils'
import { ElMessage } from 'element-plus'
import { beforeEach, expect, it, vi } from 'vitest'

import RealTradingPage from '../index.vue'
import TradeRecordForm from '../components/TradeRecordForm.vue'
import { realTradesApi, type PortfolioPosition } from '@/api/realTrades'

vi.mock('vue-router', async () => {
  const actual = await vi.importActual<typeof import('vue-router')>('vue-router')
  return { ...actual, useRouter: () => ({ push: vi.fn() }) }
})

vi.mock('@/api/realTrades', async () => {
  const actual = await vi.importActual<typeof import('@/api/realTrades')>('@/api/realTrades')
  return { ...actual, realTradesApi: {
    ...actual.realTradesApi,
    getPortfolioPreference: vi.fn(), updatePortfolioPreference: vi.fn(),
    getPositions: vi.fn(), getDashboard: vi.fn(), getRecords: vi.fn(), createRecord: vi.fn()
  } }
})

beforeEach(() => {
  vi.clearAllMocks()
  vi.mocked(realTradesApi.getPortfolioPreference).mockResolvedValue({ success: true, data: { user_id: 'u1', base_currency: 'USDT' } } as never)
  vi.mocked(realTradesApi.updatePortfolioPreference).mockResolvedValue({ success: true, data: { user_id: 'u1', base_currency: 'USD' } } as never)
  vi.mocked(realTradesApi.getPositions).mockResolvedValue({ success: true, data: { items: [], total_market_value: '0', excluded: [] } } as never)
  vi.mocked(realTradesApi.getDashboard).mockResolvedValue({ success: true, data: { base_currency: 'USDT', total_market_value: '0', total_cost: '0', realized_pnl: '0', unrealized_pnl: '0', total_pnl: '0', holding_count: 0, total_trade_count: 0, excluded: [], pnl_curve: [] } } as never)
  vi.mocked(realTradesApi.getRecords).mockResolvedValue({ success: true, data: { items: [], total: 0, page: 1, page_size: 20 } } as never)
  vi.mocked(realTradesApi.createRecord).mockResolvedValue({ success: true, data: { record: {} } } as never)
})

function mountPage() {
  return mount(RealTradingPage, {
    global: {
      stubs: { VChart: true, RouterLink: true },
    }
  })
}

it('loads saved base currency before requesting valuations', async () => {
  const wrapper = mountPage()
  await flushPromises()
  expect(realTradesApi.getPositions).toHaveBeenCalledWith('USDT')
  expect(realTradesApi.getDashboard).toHaveBeenCalledWith(90, 'USDT')
  expect((wrapper.get('[data-testid="base-currency"]').element as HTMLSelectElement).value).toBe('USDT')
})

it('persists changed base currency before refreshing valuations', async () => {
  const wrapper = mountPage()
  await flushPromises()
  await wrapper.get('[data-testid="base-currency"]').setValue('USD')
  await flushPromises()
  const saveOrder = vi.mocked(realTradesApi.updatePortfolioPreference).mock.invocationCallOrder[0]
  const refreshOrder = vi.mocked(realTradesApi.getPositions).mock.invocationCallOrder.at(-1)!
  expect(saveOrder).toBeLessThan(refreshOrder)
  expect(realTradesApi.getPositions).toHaveBeenLastCalledWith('USD')
})

it('loads transaction records in the selected base currency', async () => {
  const wrapper = mountPage()
  await flushPromises()

  await wrapper.get('.toolbar button').trigger('click')
  await flushPromises()

  expect(realTradesApi.getRecords).toHaveBeenCalledWith({
    page: 1,
    page_size: 100,
    base_currency: 'USDT',
  })
})

it('keeps the newest base-currency valuation when an older request resolves late', async () => {
  let resolveCnyPositions!: (value: unknown) => void
  let resolveCnyDashboard!: (value: unknown) => void
  vi.mocked(realTradesApi.getPortfolioPreference).mockResolvedValue({ success: true, data: { user_id: 'u1', base_currency: 'CNY' } } as never)
  vi.mocked(realTradesApi.getPositions).mockImplementation((currency) => {
    if (currency === 'CNY') return new Promise(resolve => { resolveCnyPositions = resolve }) as never
    return Promise.resolve({ success: true, data: { items: [{ symbol: 'USD-result' }], total_market_value: '100', excluded: [] } } as never)
  })
  vi.mocked(realTradesApi.getDashboard).mockImplementation((_days, currency) => {
    if (currency === 'CNY') return new Promise(resolve => { resolveCnyDashboard = resolve }) as never
    return Promise.resolve({ success: true, data: { base_currency: 'USD', total_market_value: '100', total_cost: '90', realized_pnl: '1', unrealized_pnl: '9', total_pnl: '10', holding_count: 1, total_trade_count: 1, excluded: [], pnl_curve: [] } } as never)
  })

  const wrapper = mountPage()
  await flushPromises()
  await wrapper.get('[data-testid="base-currency"]').setValue('USD')
  await flushPromises()

  resolveCnyPositions({ success: true, data: { items: [{ symbol: 'CNY-stale' }], total_market_value: '700', excluded: [] } })
  resolveCnyDashboard({ success: true, data: { base_currency: 'CNY', total_market_value: '700', total_cost: '600', realized_pnl: '10', unrealized_pnl: '90', total_pnl: '100', holding_count: 1, total_trade_count: 1, excluded: [], pnl_curve: [] } })
  await flushPromises()

  expect(wrapper.text()).toContain('$100.00')
  expect(wrapper.text()).not.toContain('CNY-stale')
})

it('keeps an unavailable short position visible and explains excluded valuation', async () => {
  vi.mocked(realTradesApi.getPortfolioPreference).mockResolvedValue({ success: true, data: { user_id: 'u1', base_currency: 'USD' } } as never)
  vi.mocked(realTradesApi.getPositions).mockResolvedValue({ success: true, data: {
    items: [{
      storage_key: 'US:NASDAQ:AAPL:equity', market: 'US', exchange: 'NASDAQ', symbol: 'AAPL',
      instrument_type: 'equity', position_side: 'short', quote_asset: 'USD', quantity: '10',
      average_entry_price: '100', mark_price: null, market_value: null, base_market_value: null,
      base_unrealized_pnl: null, weight_percent: null, converted: false,
      quote_unavailable: true, quote_error: '所有行情源均失败',
    }], total_market_value: '0', excluded: [],
  } } as never)
  vi.mocked(realTradesApi.getDashboard).mockResolvedValue({ success: true, data: {
    base_currency: 'USD', total_market_value: '0', total_cost: '0', realized_pnl: '0',
    unrealized_pnl: '0', total_pnl: '0', holding_count: 1, total_trade_count: 1,
    excluded: [{ scope: 'quote', market: 'US', exchange: 'NASDAQ', symbol: 'AAPL', position_side: 'short', error: '所有行情源均失败' }], pnl_curve: [],
  } } as never)

  const wrapper = mountPage()
  await flushPromises()

  expect(wrapper.text()).toContain('AAPL')
  expect(wrapper.text()).toContain('空头')
  expect(wrapper.text()).toContain('行情不可用')
  expect(wrapper.findAll('[data-testid="position-row"]')[0].text()).toContain('-')

  await wrapper.get('[data-testid="excluded-valuation-button"]').trigger('click')
  expect(wrapper.text()).toContain('排除估值明细')
  expect(wrapper.text()).toContain('所有行情源均失败')
})

it('passes the current positions into the create-record form', async () => {
  const currentPositions: PortfolioPosition[] = [{
    storage_key: 'US:NASDAQ:AAPL:equity',
    market: 'US',
    exchange: 'NASDAQ',
    symbol: 'AAPL',
    instrument_type: 'equity',
    position_side: 'short',
    quote_asset: 'USD',
    quantity: '3'
  }]
  vi.mocked(realTradesApi.getPositions).mockResolvedValue({
    success: true,
    data: { items: currentPositions, total_market_value: '0', excluded: [] }
  } as never)

  const wrapper = mountPage()
  await flushPromises()
  await wrapper.get('[data-testid="create-record"]').trigger('click')

  expect(wrapper.getComponent(TradeRecordForm).props('positions')).toEqual(currentPositions)
  expect(wrapper.getComponent(TradeRecordForm).props('editing')).toBe(false)
})

it('keeps the form open and asks for a refresh when available quantity changed', async () => {
  vi.mocked(realTradesApi.createRecord).mockRejectedValueOnce(
    Object.assign(new Error('Request failed with status code 422'), {
      response: { data: { detail: 'close quantity exceeds available long quantity 1' } }
    })
  )
  const warning = vi.spyOn(ElMessage, 'warning').mockImplementation(() => undefined as never)

  const wrapper = mount(RealTradingPage, {
    global: {
      stubs: {
        VChart: true,
        RouterLink: true,
        TradeRecordForm: {
          emits: ['submit'],
          template: `<button data-testid="emit-close" @click="$emit('submit', {
            record_type: 'trade', market: 'US', exchange: 'NASDAQ', symbol: 'AAPL',
            instrument_type: 'equity', quote_asset: 'USD', side: 'sell',
            position_side: 'long', position_action: 'close', price: '190', quantity: '2',
            trade_time: '2026-07-22T12:00:00'
          })">emit</button>`
        }
      }
    }
  })
  await flushPromises()
  await wrapper.get('[data-testid="create-record"]').trigger('click')
  await wrapper.get('[data-testid="emit-close"]').trigger('click')
  await flushPromises()

  expect(wrapper.find('[data-testid="emit-close"]').exists()).toBe(true)
  expect(warning).toHaveBeenCalledWith('当前持仓已变化，请刷新持仓后重新选择平仓标的')
})
