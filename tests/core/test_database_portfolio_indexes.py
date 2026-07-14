import pytest

from app.core.database import create_database_indexes


class Collection:
    def __init__(self):
        self.calls = []

    async def create_index(self, keys, **kwargs):
        self.calls.append((keys, kwargs))


class Database(dict):
    def __missing__(self, key):
        self[key] = Collection()
        return self[key]


@pytest.mark.asyncio
async def test_portfolio_indexes_are_added_without_removing_legacy_indexes():
    db = Database()
    await create_database_indexes(db)
    real_calls = db["real_trades"].calls
    assert ([('user_id', 1), ('trade_date', -1)], {}) in real_calls
    assert ([('user_id', 1), ('trade_time', -1)], {}) in real_calls
    assert any(keys == [('user_id', 1), ('idempotency_key', 1)] and opts.get('unique') for keys, opts in real_calls)
    assert db["portfolio_preferences"].calls == [([('user_id', 1)], {'unique': True})]
