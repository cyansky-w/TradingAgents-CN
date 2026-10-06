import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import PositionTable from '../components/PositionTable.vue'

const longAapl = {
  storage_key: 'US:NASDAQ:AAPL:equity',
  market: 'US',
  exchange: 'NASDAQ',
  symbol: 'AAPL',
  instrument_type: 'equity',
  position_side: 'long',
  quote_asset: 'USD',
  quantity: '2',
  average_entry_price: '190',
  mark_price: '200',
  market_value: '400',
  base_market_value: '2800',
  base_unrealized_pnl: '140',
  weight_percent: '60',
  converted: true
}
const shortAapl = { ...longAapl, storage_key: 'US:NASDAQ:AAPL:equity:short', position_side: 'short', quantity: '1', weight_percent: '40' }

describe('positionTable', () => {
  it('renders long and short rows separately for the same asset', () => {
    const wrapper = mount(PositionTable, { props: { positions: [longAapl, shortAapl], baseCurrency: 'CNY' } })
    expect(wrapper.findAll('[data-testid="position-row"]')).toHaveLength(2)
    expect(wrapper.text()).toContain('多头')
    expect(wrapper.text()).toContain('空头')
  })

  it('marks missing FX and stale quotes without assigning a weight', () => {
    const wrapper = mount(PositionTable, { props: { baseCurrency: 'CNY', positions: [
      { ...longAapl, converted: false, conversion_error: 'missing USD/CNY route', weight_percent: null },
      { ...shortAapl, quote_stale: true }
    ] } })
    expect(wrapper.get('[data-testid="conversion-unavailable"]').text()).toContain('未换算')
    expect(wrapper.get('[data-testid="quote-stale"]').text()).toContain('行情过期')
    expect(wrapper.get('[data-testid="position-weight"]').text()).toBe('-')
  })
})
