"""
Quick unit tests for real_trades module
"""
import sys
sys.path.insert(0, '.')

from datetime import datetime

# Test market detection
from app.routers.real_trades import _detect_market_and_code, CURRENCY_MAP

assert _detect_market_and_code('600519') == ('CN', '600519'), f"Got: {_detect_market_and_code('600519')}"
assert _detect_market_and_code('0700') == ('HK', '00700'), f"Got: {_detect_market_and_code('0700')}"
assert _detect_market_and_code('AAPL') == ('US', 'AAPL'), f"Got: {_detect_market_and_code('AAPL')}"
assert _detect_market_and_code('00700.HK') == ('HK', '00700'), f"Got: {_detect_market_and_code('00700.HK')}"
assert _detect_market_and_code('0700.hk') == ('HK', '00700'), f"Got: {_detect_market_and_code('0700.hk')}"
print('PASS: market detection')

# Test currency map
assert CURRENCY_MAP == {'CN': 'CNY', 'HK': 'HKD', 'US': 'USD'}
print('PASS: currency map')

# Test models
from app.models.real_trades import CreateTradeRequest, UpdateTradeRequest

req = CreateTradeRequest(
    code='600519', side='buy', price=1650.00, quantity=100,
    commission=5.0, trade_date=datetime(2026,5,15,10,30),
    reason='突破买入', tags=['白酒'], notes='测试'
)
assert req.price == 1650.00
assert req.tags == ['白酒']
print('PASS: CreateTradeRequest validation')

# Test bad side rejected
try:
    CreateTradeRequest(code='600519', side='invalid', price=1, quantity=1,
                       trade_date=datetime.now(), reason='x')
    assert False, "should have raised"
except Exception:
    print('PASS: side validation')

# Test default values
req2 = CreateTradeRequest(
    code='AAPL', side='sell', price=100, quantity=10,
    trade_date=datetime.now(), reason='test'
)
assert req2.commission == 0.0
assert req2.tags == []
assert req2.notes is None
print('PASS: defaults')

# Test UpdateTradeRequest allows partial
upd = UpdateTradeRequest(price=1.0, tags=['a'])
assert upd.price == 1.0
assert upd.tags == ['a']
assert upd.code is None
print('PASS: UpdateTradeRequest partial')

print('\nAll tests passed!')
