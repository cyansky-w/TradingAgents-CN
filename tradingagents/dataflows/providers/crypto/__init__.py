"""
加密货币数据提供器
"""

try:
    from .ccxt_provider import CCXTProvider, get_ccxt_provider
    CCXT_PROVIDER_AVAILABLE = True
except ImportError:
    CCXTProvider = None
    get_ccxt_provider = None
    CCXT_PROVIDER_AVAILABLE = False

__all__ = [
    'CCXTProvider',
    'get_ccxt_provider',
    'CCXT_PROVIDER_AVAILABLE',
]
