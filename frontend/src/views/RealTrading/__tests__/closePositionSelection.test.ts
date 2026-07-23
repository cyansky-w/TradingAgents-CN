import { describe, expect, it } from 'vitest'

import type { PortfolioPosition } from '@/api/realTrades'
import {
  closePositionKey,
  closePositionLabel,
  closeQuantityError,
  filterClosePositions
} from '../closePositionSelection'

const positions: PortfolioPosition[] = [
  {
    storage_key: 'US:NASDAQ:AAPL:equity',
    market: 'US',
    exchange: 'NASDAQ',
    symbol: 'AAPL',
    instrument_type: 'equity',
    position_side: 'long',
    quote_asset: 'USD',
    quantity: '10'
  },
  {
    storage_key: 'US:NASDAQ:AAPL:equity',
    market: 'US',
    exchange: 'NASDAQ',
    symbol: 'AAPL',
    instrument_type: 'equity',
    position_side: 'short',
    quote_asset: 'USD',
    quantity: '3'
  },
  {
    storage_key: 'CRYPTO:binance:BTC/USDT:USDT:crypto_linear_perpetual',
    market: 'CRYPTO',
    exchange: 'binance',
    symbol: 'BTC/USDT:USDT',
    instrument_type: 'crypto_linear_perpetual',
    position_side: 'long',
    quote_asset: 'USDT',
    quantity: '0.004'
  },
  {
    storage_key: 'US:NYSE:ZERO:equity',
    market: 'US',
    exchange: 'NYSE',
    symbol: 'ZERO',
    instrument_type: 'equity',
    position_side: 'long',
    quote_asset: 'USD',
    quantity: '0'
  }
]

describe('closePositionSelection', () => {
  it('filters positive positions by market and keeps long and short distinct', () => {
    const result = filterClosePositions(positions, 'US')

    expect(result).toHaveLength(2)
    expect(closePositionKey(result[0])).not.toBe(closePositionKey(result[1]))
    expect(result.map(closePositionLabel)).toEqual([
      'AAPL · NASDAQ · 多头 · 当前 10',
      'AAPL · NASDAQ · 空头 · 当前 3'
    ])
  })

  it('validates empty, invalid, and excessive close quantities', () => {
    expect(closeQuantityError('', '10')).toBe('请输入平仓数量')
    expect(closeQuantityError('0', '10')).toBe('平仓数量必须大于 0')
    expect(closeQuantityError('11', '10')).toBe('平仓数量不能超过当前持仓 10')
    expect(closeQuantityError('4', '10')).toBeNull()
  })
})
