from types import SimpleNamespace

import scripts.migration.migrate_real_trades_portfolio_v2 as migration
from scripts.migration.migrate_real_trades_portfolio_v2 import migrate_documents


def test_convert_legacy_cn_buy_to_long_open_trade():
    report = migrate_documents([{
        "_id": "buy-1", "user_id": "u1", "code": "600519", "market": "CN",
        "currency": "CNY", "side": "buy", "price": 1500.5, "quantity": 100,
        "commission": 5.0, "trade_date": "2026-01-01T00:00:00+00:00",
    }])
    converted = report.converted[0]
    assert converted["symbol"] == "600519"
    assert converted["exchange"] == "SSE"
    assert converted["position_side"] == "long"
    assert converted["position_action"] == "open"
    assert converted["price"] == "1500.5"
    assert converted["fee_amount"] == "5.0"


def test_ambiguous_us_exchange_is_reported_not_guessed():
    report = migrate_documents([{
        "_id": "us-1", "user_id": "u1", "code": "AAPL", "market": "US",
        "currency": "USD", "side": "buy", "price": 200, "quantity": 2,
        "trade_date": "2026-01-01T00:00:00+00:00",
    }])
    assert report.converted == []
    assert report.errors[0].code == "ambiguous_exchange"


def test_legacy_crypto_spot_record_is_reported_not_guessed_as_perpetual():
    report = migrate_documents([{
        "_id": "crypto-1", "user_id": "u1", "code": "BTC/USDT",
        "market": "CRYPTO", "exchange": "binance", "currency": "USDT",
        "side": "buy", "price": 60000, "quantity": 0.01,
        "trade_date": "2026-01-01T00:00:00+00:00",
    }])

    assert report.converted == []
    assert report.errors[0].code == "unsupported_crypto_spot_migration"


def test_second_migration_run_skips_v2_records():
    report = migrate_documents([{"_id": "v2-1", "user_id": "u1", "schema_version": 2}])
    assert report.converted == []
    assert report.skipped == ["v2-1"]


def test_database_migration_uses_application_mongo_target(monkeypatch, tmp_path):
    calls = {}

    class FakeCollection:
        def find(self, query):
            return []

    class FakeDatabase:
        def __init__(self, name):
            self.name = name

        def __getitem__(self, name):
            return FakeCollection()

    class FakeClient:
        def __init__(self, uri):
            calls["uri"] = uri

        def get_default_database(self):
            calls["database"] = "legacy_db"
            return FakeDatabase("legacy_db")

        def __getitem__(self, name):
            calls["database"] = name
            return FakeDatabase(name)

        def close(self):
            pass

    monkeypatch.setattr(
        migration,
        "settings",
        SimpleNamespace(
            MONGO_URI="mongodb://current/app_db",
            MONGO_DB="app_db",
        ),
        raising=False,
    )
    monkeypatch.setattr(migration, "MongoClient", FakeClient)
    monkeypatch.setenv("TRADINGAGENTS_MONGODB_URL", "mongodb://legacy/legacy_db")
    monkeypatch.setenv("MONGODB_URL", "mongodb://other/other_db")
    monkeypatch.setattr(
        "sys.argv",
        [
            "migrate_real_trades_portfolio_v2.py",
            "--dry-run",
            "--report",
            str(tmp_path / "report.json"),
        ],
    )

    assert migration.main() == 0
    assert calls == {"uri": "mongodb://current/app_db", "database": "app_db"}
