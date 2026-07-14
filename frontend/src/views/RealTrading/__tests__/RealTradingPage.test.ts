import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, expect, it, vi } from 'vitest'

import RealTradingPage from '../index.vue'
import { realTradesApi } from '@/api/realTrades'

vi.mock('vue-router', async () => {
  const actual = await vi.importActual<typeof import('vue-router')>('vue-router')
  return { ...actual, useRouter: () => ({ push: vi.fn() }) }
})

vi.mock('@/api/realTrades', async () => {
  const actual = await vi.importActual<typeof import('@/api/realTrades')>('@/api/realTrades')
  return { ...actual, realTradesApi: {
    ...actual.realTradesApi,
    getPortfolioPreference: vi.fn(), updatePortfolioPreference: vi.fn(),
    getPositions: vi.fn(), getDashboard: vi.fn(), getRecords: vi.fn()
  } }
})

beforeEach(() => {
  vi.clearAllMocks()
  vi.mocked(realTradesApi.getPortfolioPreference).mockResolvedValue({ success: true, data: { user_id: 'u1', base_currency: 'USDT' } } as never)
  vi.mocked(realTradesApi.updatePortfolioPreference).mockResolvedValue({ success: true, data: { user_id: 'u1', base_currency: 'USD' } } as never)
  vi.mocked(realTradesApi.getPositions).mockResolvedValue({ success: true, data: { items: [], total_market_value: '0', excluded: [] } } as never)
  vi.mocked(realTradesApi.getDashboard).mockResolvedValue({ success: true, data: { base_currency: 'USDT', total_market_value: '0', total_cost: '0', realized_pnl: '0', unrealized_pnl: '0', total_pnl: '0', holding_count: 0, total_trade_count: 0, excluded: [], pnl_curve: [] } } as never)
  vi.mocked(realTradesApi.getRecords).mockResolvedValue({ success: true, data: { items: [], total: 0, page: 1, page_size: 20 } } as never)
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
