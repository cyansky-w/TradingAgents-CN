import { flushPromises, mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import TradeRecordForm from '../components/TradeRecordForm.vue'
import { realTradesApi, type CreateLedgerRecordPayload } from '@/api/realTrades'


vi.mock('@/api/realTrades', async () => {
  const actual = await vi.importActual<typeof import('@/api/realTrades')>('@/api/realTrades')
  return { ...actual, realTradesApi: { ...actual.realTradesApi, getAssetRules: vi.fn() } }
})

const defaults: CreateLedgerRecordPayload = {
  record_type: 'trade', market: 'CN', exchange: 'SSE', symbol: '600519',
  instrument_type: 'equity', quote_asset: 'CNY', side: 'buy',
  position_side: 'long', position_action: 'open', price: '1500', quantity: '100',
  trade_time: '2026-07-14T12:00:00Z', tags: [], notes: null
}

function mountForm(initialValue: Partial<CreateLedgerRecordPayload> = {}) {
  return mount(TradeRecordForm, {
    props: { initialValue: { ...defaults, ...initialValue } },
    global: { plugins: [ElementPlus] }
  })
}

beforeEach(() => {
  vi.mocked(realTradesApi.getAssetRules).mockResolvedValue({
    success: true, data: { quantity_type: 'decimal', step: '0.00001', precision: 5, minimum: '0.00001' }
  } as never)
})

describe('TradeRecordForm', () => {
  it('shows step 100 and hides short controls for A-shares', async () => {
    const wrapper = mountForm()
    await flushPromises()
    expect(wrapper.get('[data-testid="quantity"]').attributes('step')).toBe('100')
    expect(wrapper.find('[data-testid="position-side-short"]').exists()).toBe(false)
  })

  it('shows short open/close controls for US equities', async () => {
    const wrapper = mountForm({ market: 'US', exchange: 'NASDAQ', symbol: 'AAPL', quote_asset: 'USD' })
    await flushPromises()
    expect(wrapper.find('[data-testid="position-side-short"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="position-action-close"]').exists()).toBe(true)
  })

  it('accepts decimal quantity for crypto perpetuals', async () => {
    const wrapper = mountForm({ market: 'CRYPTO', exchange: 'binance', symbol: 'BTC/USDT:USDT', instrument_type: 'crypto_linear_perpetual', quote_asset: 'USDT', quantity: '0.00125' })
    await flushPromises()
    const input = wrapper.get('[data-testid="quantity"]')
    expect(input.attributes('step')).toBe('0.00001')
    expect((input.element as HTMLInputElement).value).toBe('0.00125')
  })

  it('hides position action for transfer records', async () => {
    const wrapper = mountForm({ record_type: 'transfer_in' })
    await flushPromises()
    expect(wrapper.find('[data-testid="position-action"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="trade-side"]').exists()).toBe(false)
  })

  it('keeps fee controls collapsed by default', () => {
    const wrapper = mountForm()
    expect(wrapper.find('[data-testid="fee-amount"]').exists()).toBe(false)
    expect(wrapper.get('[data-testid="advanced-toggle"]').text()).toContain('费用与合约元数据')
  })
})
