import type { Market, PortfolioPosition } from '@/api/realTrades'

import Decimal from 'decimal.js'

export function closePositionKey(position: PortfolioPosition): string {
  return JSON.stringify([
    position.market,
    position.exchange,
    position.symbol,
    position.instrument_type,
    position.position_side
  ])
}

export function filterClosePositions(
  positions: PortfolioPosition[],
  market: Market
): PortfolioPosition[] {
  return positions.filter(position => {
    try {
      return position.market === market && new Decimal(position.quantity).gt(0)
    } catch {
      return false
    }
  })
}

export function closePositionLabel(position: PortfolioPosition): string {
  const side = position.position_side === 'short' ? '空头' : '多头'
  return `${position.symbol} · ${position.exchange} · ${side} · 当前 ${position.quantity}`
}

export function closeQuantityError(quantity: string, available: string): string | null {
  if (!quantity.trim())
    return '请输入平仓数量'
  try {
    const requested = new Decimal(quantity)
    const current = new Decimal(available)
    if (!requested.isFinite() || requested.lte(0))
      return '平仓数量必须大于 0'
    if (requested.gt(current))
      return `平仓数量不能超过当前持仓 ${available}`
    return null
  } catch {
    return '请输入有效的平仓数量'
  }
}

export function positionQuantityUnit(position: PortfolioPosition): string {
  if (position.instrument_type === 'crypto_linear_perpetual') {
    return position.symbol.split('/')[0] || '标的币'
  }
  return '股'
}
