import { mount } from '@vue/test-utils'
import { expect, it } from 'vitest'

import TradeRecordsDialog from '../components/TradeRecordsDialog.vue'

it('shows original and converted fee amounts', () => {
  const wrapper = mount(TradeRecordsDialog, {
    props: {
      modelValue: true,
      total: 1,
      records: [{
        id: 'record-1',
        trade_time: '2026-07-14T12:00:00+00:00',
        symbol: 'BTC/USDT:USDT',
        record_type: 'trade',
        position_side: 'long',
        position_action: 'open',
        price: '60000',
        quantity: '0.01',
        fee_amount: '0.01',
        fee_currency: 'BNB',
        base_fee_amount: '2.5',
        base_fee_currency: 'CNY',
        fee_conversion_error: null
      }]
    }
  })

  expect(wrapper.text()).toContain('0.01 BNB')
  expect(wrapper.text()).toContain('2.5 CNY')
})

it('uses the responsive filter layout hook', () => {
  const wrapper = mount(TradeRecordsDialog, {
    props: { modelValue: true, total: 0, records: [] }
  })

  expect(wrapper.find('.filters.responsive-filters').exists()).toBe(true)
})
