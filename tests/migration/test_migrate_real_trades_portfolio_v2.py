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


def test_second_migration_run_skips_v2_records():
    report = migrate_documents([{"_id": "v2-1", "user_id": "u1", "schema_version": 2}])
    assert report.converted == []
    assert report.skipped == ["v2-1"]
