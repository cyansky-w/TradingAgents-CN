from decimal import Decimal

import pytest

from app.services.portfolio.asset_normalizer import AssetNormalizer


@pytest.mark.parametrize(
    "market,exchange,symbol,instrument,expected",
    [
        ("CN", None, "600519", "equity", ("SSE", "600519")),
        ("CN", None, "000001", "equity", ("SZSE", "000001")),
        ("HK", None, "700", "equity", ("SEHK", "00700")),
        ("US", "NASDAQ", "aapl", "equity", ("NASDAQ", "AAPL")),
        (
            "CRYPTO",
            "BINANCE",
            "btc/usdt",
            "crypto_spot",
            ("binance", "BTC/USDT"),
        ),
        (
            "CRYPTO",
            "binance",
            "btc/usdt:usdt",
            "crypto_linear_perpetual",
            ("binance", "BTC/USDT:USDT"),
        ),
        (
            "CRYPTO",
            "binance",
            "btc／usdt：usdt",
            "crypto_linear_perpetual",
            ("binance", "BTC/USDT:USDT"),
        ),
    ],
)
def test_normalize_asset(market, exchange, symbol, instrument, expected):
    asset = AssetNormalizer.normalize(market, exchange, symbol, instrument)
    assert (asset.exchange, asset.symbol) == expected


def test_a_share_requires_hundred_unit_quantity():
    rules = AssetNormalizer.quantity_rules("CN", "SSE", "600519", "equity")
    assert rules.step == Decimal("100")
    assert rules.validate(Decimal("200")) is None
    assert rules.validate(Decimal("150")) == (
        "A-share quantity must be a multiple of 100"
    )


def test_hong_kong_and_us_equities_use_single_unit_step():
    hk = AssetNormalizer.quantity_rules("HK", "SEHK", "700", "equity")
    us = AssetNormalizer.quantity_rules("US", "NASDAQ", "AAPL", "equity")
    assert hk.step == us.step == Decimal("1")
    assert hk.validate(Decimal("1")) is None
    assert us.validate(Decimal("1")) is None


def test_crypto_perpetual_allows_decimal_quantity():
    rules = AssetNormalizer.quantity_rules(
        "CRYPTO",
        "binance",
        "BTC/USDT:USDT",
        "crypto_linear_perpetual",
        precision=5,
    )
    assert rules.step == Decimal("0.00001")
    assert rules.validate(Decimal("0.00125")) is None
    assert rules.validate(Decimal("0.001251")) == (
        "quantity must align to step 0.00001"
    )


def test_rejects_unsupported_crypto_exchange():
    with pytest.raises(ValueError, match="unsupported crypto exchange"):
        AssetNormalizer.normalize(
            "CRYPTO", "unknown", "BTC/USDT", "crypto_spot"
        )
