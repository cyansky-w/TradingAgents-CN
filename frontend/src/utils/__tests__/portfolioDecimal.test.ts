import { describe, expect, it } from 'vitest'

import { formatDecimal, multiplyDecimal, quantityStep } from '../portfolioDecimal'


describe('portfolio decimal helpers', () => {
  it('multiplies crypto values without Number rounding', () => {
    expect(multiplyDecimal('65000.1234', '0.00125')).toBe('81.25015425')
  })

  it('returns market quantity steps', () => {
    expect(quantityStep({ market: 'CN', precision: 0 })).toBe('100')
    expect(quantityStep({ market: 'CRYPTO', precision: 5 })).toBe('0.00001')
    expect(quantityStep({ market: 'US', precision: 0 })).toBe('1')
  })

  it('formats without converting through Number', () => {
    expect(formatDecimal('0.000000123456', 8)).toBe('0.00000012')
  })
})
