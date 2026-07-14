from dataclasses import dataclass
from decimal import Decimal
import re

from app.services.portfolio.types import AssetKey, InstrumentType, Market


SUPPORTED_CRYPTO_EXCHANGES = {"binance", "okx", "bybit", "bitget", "gate"}
SUPPORTED_US_EXCHANGES = {"NASDAQ", "NYSE", "AMEX"}


@dataclass(frozen=True)
class QuantityRules:
    quantity_type: str
    step: Decimal
    minimum: Decimal
    precision: int
    market: Market

    def validate(self, quantity: Decimal) -> str | None:
        if quantity < self.minimum:
            return f"quantity must be at least {self.minimum}"
        if quantity % self.step != 0:
            if self.market == Market.CN:
                return "A-share quantity must be a multiple of 100"
            return f"quantity must align to step {self.step}"
        return None


class AssetNormalizer:
    @staticmethod
    def normalize(market, exchange, symbol, instrument_type) -> AssetKey:
        normalized_market = Market(str(market).upper())
        instrument = InstrumentType(str(instrument_type))
        normalized_symbol = str(symbol).strip().upper()

        if normalized_market == Market.CN:
            if not re.fullmatch(r"\d{6}", normalized_symbol):
                raise ValueError("A-share symbol must be 6 digits")
            normalized_exchange = (
                "SSE" if normalized_symbol.startswith(("5", "6", "9")) else "SZSE"
            )
        elif normalized_market == Market.HK:
            normalized_symbol = normalized_symbol.removesuffix(".HK")
            if not re.fullmatch(r"\d{1,5}", normalized_symbol):
                raise ValueError("Hong Kong symbol must be 1-5 digits")
            normalized_symbol = normalized_symbol.zfill(5)
            normalized_exchange = "SEHK"
        elif normalized_market == Market.US:
            normalized_exchange = str(exchange or "").upper()
            if normalized_exchange not in SUPPORTED_US_EXCHANGES:
                raise ValueError("US exchange must be NASDAQ, NYSE, or AMEX")
            if not re.fullmatch(r"[A-Z][A-Z0-9.-]{0,14}", normalized_symbol):
                raise ValueError("invalid US symbol")
        else:
            normalized_exchange = str(exchange or "").lower()
            if normalized_exchange not in SUPPORTED_CRYPTO_EXCHANGES:
                raise ValueError("unsupported crypto exchange")
            if instrument == InstrumentType.CRYPTO_SPOT:
                pattern = r"[A-Z0-9]+/[A-Z0-9]+"
            elif instrument == InstrumentType.CRYPTO_LINEAR_PERPETUAL:
                pattern = r"[A-Z0-9]+/[A-Z0-9]+:[A-Z0-9]+"
            else:
                raise ValueError("crypto market requires a crypto instrument type")
            if not re.fullmatch(pattern, normalized_symbol):
                raise ValueError("invalid crypto symbol for instrument type")

        return AssetKey(
            normalized_market,
            normalized_exchange,
            normalized_symbol,
            instrument,
        )

    @staticmethod
    def quantity_rules(
        market,
        exchange,
        symbol,
        instrument_type,
        precision: int = 0,
    ) -> QuantityRules:
        if precision < 0:
            raise ValueError("precision must be non-negative")

        asset = AssetNormalizer.normalize(market, exchange, symbol, instrument_type)
        if asset.market == Market.CN:
            return QuantityRules(
                "integer", Decimal("100"), Decimal("100"), 0, asset.market
            )
        if asset.instrument_type in {
            InstrumentType.CRYPTO_SPOT,
            InstrumentType.CRYPTO_LINEAR_PERPETUAL,
        }:
            step = Decimal(1).scaleb(-precision)
            return QuantityRules("decimal", step, step, precision, asset.market)
        return QuantityRules("integer", Decimal("1"), Decimal("1"), 0, asset.market)
