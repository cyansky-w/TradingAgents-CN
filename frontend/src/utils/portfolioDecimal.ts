import Decimal from 'decimal.js'


export function multiplyDecimal(a: string, b: string): string {
  return new Decimal(a || '0').mul(new Decimal(b || '0')).toFixed()
}

export function formatDecimal(value: string | null | undefined, precision = 2): string {
  if (value == null || value === '') return '-'
  return new Decimal(value).toDecimalPlaces(precision, Decimal.ROUND_HALF_UP).toFixed(precision)
}

export function quantityStep(rule: { market: string; precision: number }): string {
  if (rule.market === 'CN') return '100'
  if (rule.market === 'CRYPTO') {
    return new Decimal(1).div(new Decimal(10).pow(rule.precision)).toFixed()
  }
  return '1'
}
