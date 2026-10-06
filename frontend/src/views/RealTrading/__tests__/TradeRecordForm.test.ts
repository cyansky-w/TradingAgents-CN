import type { CreateLedgerRecordPayload, PortfolioPosition } from '@/api/realTrades'
import { flushPromises, mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'

import { beforeEach, describe, expect, it, vi } from 'vitest'
import {

  realTradesApi
} from '@/api/realTrades'
import { Select, SelectItem } from '@/components/ui/select'
import { TooltipProvider } from '@/components/ui/tooltip'
import { closePositionKey } from '../closePositionSelection'
import TradeRecordForm from '../components/TradeRecordForm.vue'

vi.stubGlobal(
  'ResizeObserver',
  class {
    observe() {}
    unobserve() {}
    disconnect() {}
  }
)

vi.mock('@/api/realTrades', async () => {
  const actual = await vi.importActual<typeof import('@/api/realTrades')>('@/api/realTrades')
  return { ...actual, realTradesApi: { ...actual.realTradesApi, getAssetRules: vi.fn() } }
})

const defaults: CreateLedgerRecordPayload = {
  record_type: 'trade',
  market: 'CN',
  exchange: 'SSE',
  symbol: '600519',
  instrument_type: 'equity',
  quote_asset: 'CNY',
  side: 'buy',
  position_side: 'long',
  position_action: 'open',
  price: '1500',
  quantity: '100',
  trade_time: '2026-07-14T12:00:00Z',
  tags: [],
  notes: null
}

function mountForm(
  initialValue: Partial<CreateLedgerRecordPayload> = {},
  positions: PortfolioPosition[] = [],
  editing = false
) {
  return mount(TradeRecordForm, {
    props: { initialValue: { ...defaults, ...initialValue }, positions, editing },
    global: { plugins: [ElementPlus] }
  })
}

const longAapl: PortfolioPosition = {
  storage_key: 'US:NASDAQ:AAPL:equity',
  market: 'US',
  exchange: 'NASDAQ',
  symbol: 'AAPL',
  instrument_type: 'equity',
  position_side: 'long',
  quote_asset: 'USD',
  quantity: '10'
}

const shortAapl: PortfolioPosition = {
  ...longAapl,
  position_side: 'short',
  quantity: '3'
}

const longBtc: PortfolioPosition = {
  storage_key: 'CRYPTO:binance:BTC/USDT:USDT:crypto_linear_perpetual',
  market: 'CRYPTO',
  exchange: 'binance',
  symbol: 'BTC/USDT:USDT',
  instrument_type: 'crypto_linear_perpetual',
  position_side: 'long',
  quote_asset: 'USDT',
  quantity: '0.004'
}

beforeEach(() => {
  vi.mocked(realTradesApi.getAssetRules).mockResolvedValue({
    success: true,
    data: { quantity_type: 'decimal', step: '0.00001', precision: 5, minimum: '0.00001' }
  } as never)
})

describe('tradeRecordForm', () => {
  it('shows step 100 and hides short controls for A-shares', async () => {
    const wrapper = mountForm()
    await flushPromises()
    expect(wrapper.get('[data-testid="quantity"]').attributes('step')).toBe('100')
    expect(wrapper.find('[data-testid="position-side-short"]').exists()).toBe(false)
  })

  it('shows short open/close controls for US equities', async () => {
    const wrapper = mountForm({
      market: 'US',
      exchange: 'NASDAQ',
      symbol: 'AAPL',
      quote_asset: 'USD'
    })
    await flushPromises()
    expect(wrapper.find('[data-testid="position-side-short"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="position-action-close"]').exists()).toBe(true)
  })

  it('lists only closeable positions from the selected market and keeps sides distinct', async () => {
    const wrapper = mountForm(
      { market: 'US', exchange: 'NASDAQ', symbol: '', position_action: 'close', quantity: '' },
      [longAapl, shortAapl, longBtc]
    )
    await flushPromises()

    const labels = wrapper.findAllComponents(SelectItem).map(item => item.text())
    expect(labels).toEqual([
      'AAPL · NASDAQ · 多头 · 当前 10',
      'AAPL · NASDAQ · 空头 · 当前 3'
    ])
    expect(wrapper.findComponent(Select).exists()).toBe(true)
  })

  it('fills asset fields from the selected position and leaves close quantity empty', async () => {
    const wrapper = mountForm(
      { market: 'US', exchange: 'NASDAQ', symbol: '', position_action: 'close', quantity: '' },
      [shortAapl]
    )
    await flushPromises()

    wrapper.getComponent(Select).vm.$emit('update:modelValue', closePositionKey(shortAapl))
    await flushPromises()

    expect(wrapper.get('[data-testid="available-close-quantity"]').text()).toContain('3 股')
    expect((wrapper.get('[data-testid="quantity"]').element as HTMLInputElement).value).toBe('')
    expect(wrapper.get('[data-testid="selected-position-side"]').text()).toContain('空头')

    await wrapper.get('[data-testid="price"]').setValue('190')
    await wrapper.get('[data-testid="quantity"]').setValue('2')
    await wrapper.get('form').trigger('submit')

    const [payload] = wrapper.emitted('submit')![0] as [CreateLedgerRecordPayload]
    expect(payload).toMatchObject({
      market: 'US',
      exchange: 'NASDAQ',
      symbol: 'AAPL',
      instrument_type: 'equity',
      quote_asset: 'USD',
      position_side: 'short',
      position_action: 'close',
      side: 'buy',
      quantity: '2'
    })
  })

  it('blocks a close quantity above the selected current position', async () => {
    const wrapper = mountForm(
      { market: 'US', exchange: 'NASDAQ', symbol: '', position_action: 'close', quantity: '' },
      [longAapl]
    )
    await flushPromises()
    wrapper.getComponent(Select).vm.$emit('update:modelValue', closePositionKey(longAapl))
    await flushPromises()

    await wrapper.get('[data-testid="price"]').setValue('190')
    await wrapper.get('[data-testid="quantity"]').setValue('11')
    await wrapper.get('form').trigger('submit')

    expect(wrapper.emitted('submit')).toBeUndefined()
    expect(wrapper.get('.form-error').text()).toBe('平仓数量不能超过当前持仓 10')
  })

  it('clears the selected close position and quantity after changing market', async () => {
    const wrapper = mountForm(
      { market: 'US', exchange: 'NASDAQ', symbol: '', position_action: 'close', quantity: '' },
      [longAapl, longBtc]
    )
    await flushPromises()
    wrapper.getComponent(Select).vm.$emit('update:modelValue', closePositionKey(longAapl))
    await flushPromises()
    await wrapper.get('[data-testid="quantity"]').setValue('4')

    await wrapper.get('[data-testid="market"]').setValue('CRYPTO')
    await flushPromises()

    expect(wrapper.find('[data-testid="available-close-quantity"]').exists()).toBe(false)
    expect((wrapper.get('[data-testid="quantity"]').element as HTMLInputElement).value).toBe('')
    expect(wrapper.findAllComponents(SelectItem).map(item => item.text())).toEqual([
      'BTC/USDT:USDT · binance · 多头 · 当前 0.004'
    ])
  })

  it('shows an empty state and blocks submit when the selected market has no closeable position', async () => {
    const wrapper = mountForm(
      { market: 'HK', exchange: 'HKEX', symbol: '', position_action: 'close', quantity: '' },
      [longAapl, longBtc]
    )
    await flushPromises()

    expect(wrapper.text()).toContain('该市场暂无可平持仓')
    expect(wrapper.get('[data-testid="close-position-select"]').attributes('disabled')).toBeDefined()

    await wrapper.get('[data-testid="price"]').setValue('100')
    await wrapper.get('[data-testid="quantity"]').setValue('1')
    await wrapper.get('form').trigger('submit')

    expect(wrapper.emitted('submit')).toBeUndefined()
    expect(wrapper.get('.form-error').text()).toBe('请选择当前持仓')
  })

  it('updates available quantity and invalidates a position that is no longer closeable', async () => {
    const wrapper = mountForm(
      { market: 'US', exchange: 'NASDAQ', symbol: '', position_action: 'close', quantity: '' },
      [longAapl]
    )
    await flushPromises()
    wrapper.getComponent(Select).vm.$emit('update:modelValue', closePositionKey(longAapl))
    await flushPromises()

    await wrapper.setProps({ positions: [{ ...longAapl, quantity: '6' }] })
    await flushPromises()
    expect(wrapper.get('[data-testid="available-close-quantity"]').text()).toContain('6 股')

    await wrapper.get('[data-testid="quantity"]').setValue('2')
    await wrapper.setProps({ positions: [{ ...longAapl, quantity: '0' }] })
    await flushPromises()

    expect(wrapper.find('[data-testid="available-close-quantity"]').exists()).toBe(false)
    expect((wrapper.get('[data-testid="quantity"]').element as HTMLInputElement).value).toBe('')
    expect(wrapper.get('.form-error').text()).toBe('所选持仓已变化，请重新选择平仓标的')
  })

  it('allows editing a historical close record without a current position', async () => {
    const wrapper = mountForm(
      {
        market: 'US',
        exchange: 'NASDAQ',
        symbol: 'AAPL',
        quote_asset: 'USD',
        position_side: 'long',
        position_action: 'close',
        side: 'sell',
        price: '190',
        quantity: '2'
      },
      [],
      true
    )

    expect(wrapper.find('[data-testid="close-position-select"]').exists()).toBe(false)
    await wrapper.get('form').trigger('submit')
    expect(wrapper.emitted('submit')).toHaveLength(1)
  })

  it('accepts decimal quantity for crypto perpetuals', async () => {
    const wrapper = mountForm({
      market: 'CRYPTO',
      exchange: 'binance',
      symbol: 'BTC/USDT:USDT',
      instrument_type: 'crypto_linear_perpetual',
      quote_asset: 'USDT',
      quantity: '0.00125'
    })
    await flushPromises()
    const input = wrapper.get('[data-testid="quantity"]')
    expect(input.attributes('step')).toBe('0.00001')
    expect((input.element as HTMLInputElement).value).toBe('0.00125')
  })

  it('uses the shared shadcn-vue tooltip for crypto symbol guidance', async () => {
    const wrapper = mountForm({
      market: 'CRYPTO',
      exchange: 'binance',
      symbol: 'BTC/USDT:USDT',
      instrument_type: 'crypto_linear_perpetual',
      quote_asset: 'USDT'
    })
    await flushPromises()

    expect(wrapper.findComponent(TooltipProvider).exists()).toBe(true)
    expect(wrapper.get('[aria-label="加密标的格式说明"]').text()).toBe('?')
  })

  it('converts perpetual quantity, notional, and initial margin modes', async () => {
    const wrapper = mountForm({
      market: 'CRYPTO',
      exchange: 'binance',
      symbol: 'BTC/USDT:USDT',
      instrument_type: 'crypto_linear_perpetual',
      quote_asset: 'USDT',
      price: '100000',
      quantity: '0.01',
      leverage: '10',
      initial_margin: '',
      order_notional: ''
    })
    await flushPromises()

    expect(wrapper.get('[data-testid="calculated-notional"]').text()).toBe('1000')
    expect(wrapper.get('[data-testid="calculated-margin"]').text()).toBe('100')

    await wrapper.get('input[value="notional"]').setValue(true)
    await wrapper.get('[data-testid="order-notional"]').setValue('2000')
    expect(wrapper.get('[data-testid="calculated-quantity"]').text()).toBe('0.02')
    expect(wrapper.get('[data-testid="calculated-margin"]').text()).toBe('200')

    await wrapper.get('input[value="margin"]').setValue(true)
    await wrapper.get('[data-testid="initial-margin"]').setValue('300')
    expect(wrapper.get('[data-testid="calculated-notional"]').text()).toBe('3000')
    expect(wrapper.get('[data-testid="calculated-quantity"]').text()).toBe('0.03')
  })

  it('uses a 1-200 leverage slider with clickable common marks', async () => {
    const wrapper = mountForm({
      market: 'CRYPTO',
      exchange: 'binance',
      symbol: 'BTC/USDT:USDT',
      instrument_type: 'crypto_linear_perpetual',
      quote_asset: 'USDT',
      price: '100000',
      quantity: '0.01',
      leverage: '10',
      initial_margin: '',
      order_notional: ''
    })
    await flushPromises()

    const slider = wrapper.get('[data-testid="leverage-slider"]')
    expect(slider.attributes('data-min')).toBe('1')
    expect(slider.attributes('data-max')).toBe('200')
    expect(wrapper.get('[data-testid="leverage-value"]').text()).toBe('10×')

    for (const mark of [1, 10, 20, 30, 50, 75, 100, 150]) {
      expect(wrapper.find(`[data-testid="leverage-mark-${mark}"]`).exists()).toBe(true)
    }

    await wrapper.get('[data-testid="leverage-mark-50"]').trigger('click')
    expect(wrapper.get('[data-testid="leverage-value"]').text()).toBe('50×')
    expect(wrapper.get('[data-testid="calculated-margin"]').text()).toBe('20')
  })

  it('normalizes full-width crypto symbol separators before submit', async () => {
    const wrapper = mountForm({
      market: 'CRYPTO',
      exchange: 'binance',
      symbol: 'BTC／USDT：USDT',
      instrument_type: 'crypto_linear_perpetual',
      quote_asset: 'USDT',
      price: '66012.2',
      quantity: '0.0045446144803536316014',
      leverage: '10',
      order_notional: '300',
      initial_margin: '30'
    })
    await flushPromises()

    await wrapper.get('form').trigger('submit')

    const [payload] = wrapper.emitted('submit')![0] as [CreateLedgerRecordPayload]
    expect(payload.symbol).toBe('BTC/USDT:USDT')
  })

  it('rounds derived perpetual quantity down to the exchange step', async () => {
    vi.mocked(realTradesApi.getAssetRules).mockResolvedValueOnce({
      success: true,
      data: { quantity_type: 'decimal', step: '0.001', precision: 3, minimum: '0.001' }
    } as never)
    const wrapper = mountForm({
      market: 'CRYPTO',
      exchange: 'binance',
      symbol: 'BTC/USDT:USDT',
      instrument_type: 'crypto_linear_perpetual',
      quote_asset: 'USDT',
      price: '66012.2',
      quantity: '',
      leverage: '10',
      order_notional: '',
      initial_margin: ''
    })
    await flushPromises()

    await wrapper.get('input[value="notional"]').setValue(true)
    await wrapper.get('[data-testid="order-notional"]').setValue('300')

    expect(wrapper.get('[data-testid="calculated-quantity"]').text()).toBe('0.004')
    expect((wrapper.get('[data-testid="order-notional"]').element as HTMLInputElement).value).toBe(
      '264.0488'
    )
    expect(wrapper.get('[data-testid="calculated-margin"]').text()).toBe('26.40488')
  })

  it('waits for asset rules and blocks a perpetual order below the minimum quantity', async () => {
    let resolveRules!: (value: unknown) => void
    vi.mocked(realTradesApi.getAssetRules).mockReturnValueOnce(
      new Promise(resolve => {
        resolveRules = resolve
      }) as never
    )
    const wrapper = mountForm({
      market: 'CRYPTO',
      exchange: 'binance',
      symbol: 'BTC/USDT:USDT',
      instrument_type: 'crypto_linear_perpetual',
      quote_asset: 'USDT',
      price: '66012.2',
      quantity: '0.00045446144803536316014',
      leverage: '1',
      order_notional: '30',
      initial_margin: '30'
    })

    await wrapper.get('form').trigger('submit')
    expect(wrapper.emitted('submit')).toBeUndefined()

    resolveRules({
      success: true,
      data: { quantity_type: 'decimal', step: '0.001', precision: 3, minimum: '0.001' }
    })
    await flushPromises()

    expect(wrapper.emitted('submit')).toBeUndefined()
    expect(wrapper.get('.form-error').text()).toContain('最小下单数量为 0.001')
    expect(wrapper.get('.form-error').text()).toContain('最小订单金额约 66.0122 USDT')
    expect(wrapper.get('[data-testid="calculated-notional"]').text()).toBe('30')
    expect(wrapper.get('[data-testid="calculated-margin"]').text()).toBe('30')
  })

  it('replaces stale derived values when a notional is below the minimum quantity', async () => {
    vi.mocked(realTradesApi.getAssetRules).mockResolvedValueOnce({
      success: true,
      data: { quantity_type: 'decimal', step: '0.001', precision: 3, minimum: '0.001' }
    } as never)
    const wrapper = mountForm({
      market: 'CRYPTO',
      exchange: 'binance',
      symbol: 'BTC/USDT:USDT',
      instrument_type: 'crypto_linear_perpetual',
      quote_asset: 'USDT',
      price: '66012.2',
      quantity: '100',
      leverage: '1',
      order_notional: '',
      initial_margin: ''
    })
    await flushPromises()

    await wrapper.get('input[value="notional"]').setValue(true)
    expect(wrapper.get('[data-testid="calculated-margin"]').text()).toBe('6601220')
    await wrapper.get('[data-testid="order-notional"]').setValue('30')

    expect(wrapper.get('[data-testid="calculated-quantity"]').text()).toBe('-')
    expect(wrapper.get('[data-testid="calculated-margin"]').text()).toBe('30')
  })

  it('offers only USDT perpetuals for the crypto market', async () => {
    const wrapper = mountForm({
      market: 'CRYPTO',
      exchange: 'binance',
      instrument_type: 'crypto_spot' as any,
      quote_asset: 'USDT'
    })
    await flushPromises()

    expect(wrapper.find('option[value="crypto_spot"]').exists()).toBe(false)
    expect(
      (wrapper.get('[data-testid="instrument-type"]').element as HTMLSelectElement).value
    ).toBe('crypto_linear_perpetual')
    expect((wrapper.get('[data-testid="exchange"]').element as HTMLInputElement).value).toBe(
      'binance'
    )
  })

  it('removes transfer records when switching to crypto perpetuals', async () => {
    const wrapper = mountForm({
      market: 'CRYPTO',
      exchange: 'binance',
      record_type: 'transfer_in',
      instrument_type: 'crypto_linear_perpetual',
      quote_asset: 'USDT'
    })
    await flushPromises()

    expect(wrapper.find('option[value="transfer_in"]').exists()).toBe(false)
    expect((wrapper.get('[data-testid="record-type"]').element as HTMLSelectElement).value).toBe(
      'trade'
    )
    expect(wrapper.find('[data-testid="position-action"]').exists()).toBe(true)
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

  it('omits blank optional fee values on submit', async () => {
    const wrapper = mountForm({ fee_amount: '', fee_currency: 'CNY' })

    await wrapper.get('form').trigger('submit')

    const [payload] = wrapper.emitted('submit')![0] as [CreateLedgerRecordPayload]
    expect(payload.fee_amount).toBeUndefined()
    expect(payload.fee_currency).toBeUndefined()
  })

  it('allows datetime values with seconds', () => {
    const wrapper = mountForm()
    expect(wrapper.get('input[type="datetime-local"]').attributes('step')).toBe('1')
  })
})
