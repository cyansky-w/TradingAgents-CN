import asyncio
from types import SimpleNamespace

from pymongo.errors import DuplicateKeyError


def test_seed_tools_backfills_legacy_docs_before_unique_code_index(monkeypatch):
    from app.tools import handler_map

    tool_defs = [
        {
            "code": "calculator",
            "name": "calculator",
            "description": "Evaluate math",
            "type": "builtin",
            "handler": "calculator",
            "tags": ["utility"],
            "is_system": True,
            "parameters": [],
        },
        {
            "code": "get_current_time",
            "name": "get_current_time",
            "description": "Get time",
            "type": "builtin",
            "handler": "get_current_time",
            "tags": ["utility"],
            "is_system": True,
            "parameters": [],
        },
    ]

    class _FakeCollection:
        def __init__(self):
            self.docs = [
                {"_id": "1", "name": "calculator", "description": "old", "type": "builtin", "handler": "calculator"},
                {"_id": "2", "name": "get_current_time", "description": "old", "type": "builtin", "handler": "get_current_time"},
            ]
            self.indexes = []

        async def create_index(self, key, **kwargs):
            if key == "code" and kwargs.get("unique"):
                null_codes = [doc for doc in self.docs if doc.get("code") is None]
                if len(null_codes) > 1:
                    raise DuplicateKeyError("dup key: { code: null }")
            self.indexes.append((key, kwargs))

        async def find_one(self, query):
            for doc in self.docs:
                if all(doc.get(key) == value for key, value in query.items()):
                    return doc
            return None

        async def update_one(self, query, update):
            doc = await self.find_one(query)
            if not doc:
                return SimpleNamespace(modified_count=0, matched_count=0)
            before = dict(doc)
            doc.update(update.get("$set", {}))
            return SimpleNamespace(modified_count=int(doc != before), matched_count=1)

        async def insert_one(self, doc):
            self.docs.append(dict(doc))
            return SimpleNamespace(inserted_id=str(len(self.docs)))

    collection = _FakeCollection()

    class _FakeDb(dict):
        def __getitem__(self, name):
            assert name == "tools"
            return collection

    import app.core.database as database

    monkeypatch.setattr(handler_map, "TOOL_DEFINITIONS", tool_defs)
    monkeypatch.setattr(database, "get_mongo_db", lambda: _FakeDb())

    result = asyncio.run(handler_map.seed_tools_to_db())

    assert result == {"created": 0, "updated": 2, "skipped": 0, "total": 2}
    assert [doc["code"] for doc in collection.docs] == ["calculator", "get_current_time"]
    assert any(key == "code" and kwargs.get("name") == "uniq_tool_code" for key, kwargs in collection.indexes)
