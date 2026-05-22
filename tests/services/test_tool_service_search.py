import asyncio
import re

from app.services.tool_service import ToolService


class _FakeCursor:
    def __init__(self, docs):
        self.docs = docs
        self.skip_count = 0
        self.limit_count = len(docs)

    def sort(self, *args, **kwargs):
        return self

    def skip(self, value):
        self.skip_count = value
        return self

    def limit(self, value):
        self.limit_count = value
        return self

    async def to_list(self, length):
        end = self.skip_count + self.limit_count
        return self.docs[self.skip_count:end]


class _FakeToolsCollection:
    def __init__(self, docs):
        self.docs = docs

    async def count_documents(self, query):
        return len(self._filter(query))

    def find(self, query):
        return _FakeCursor(self._filter(query))

    def _filter(self, query):
        return [doc for doc in self.docs if self._matches(doc, query)]

    def _matches(self, doc, query):
        for key, expected in query.items():
            if key == "$or":
                if not any(self._matches(doc, condition) for condition in expected):
                    return False
                continue
            if isinstance(expected, dict) and "$regex" in expected:
                values = self._values(doc, key.split("."))
                flags = re.IGNORECASE if "i" in expected.get("$options", "") else 0
                if not any(re.search(expected["$regex"], str(value), flags) for value in values if value is not None):
                    return False
                continue
            values = self._values(doc, key.split("."))
            if expected not in values:
                return False
        return True

    def _values(self, value, path):
        if isinstance(value, list):
            values = []
            for item in value:
                values.extend(self._values(item, path))
            return values
        if not path:
            return [value]
        if not isinstance(value, dict):
            return []
        return self._values(value.get(path[0]), path[1:])


class _FakeDb:
    def __init__(self, docs):
        self.tools = _FakeToolsCollection(docs)


async def _list_tools(search):
    service = ToolService()
    service.db = _FakeDb([
        {
            "_id": "tool-1",
            "code": "get_stock_news_unified",
            "name": "get_stock_news_unified",
            "description": "Unified market news retrieval.",
            "type": "builtin",
            "handler": "get_stock_news_unified",
            "tags": ["news"],
            "parameters": [
                {"name": "ticker", "type": "string", "required": True, "description": "股票代码"},
            ],
        },
        {
            "_id": "tool-2",
            "code": "calculator",
            "name": "calculator",
            "description": "Evaluate a mathematical expression.",
            "type": "builtin",
            "handler": "calculator",
            "tags": ["utility"],
            "parameters": [],
        },
    ])
    service._indexes_ensured = True
    return await service.list_tools(search=search, page=1, page_size=20)


def test_list_tools_search_matches_parameter_description():
    tools, total = asyncio.run(_list_tools("股票代码"))

    assert total == 1
    assert [tool["code"] for tool in tools] == ["get_stock_news_unified"]


def test_list_tools_search_treats_regex_metacharacters_as_literal_text():
    tools, total = asyncio.run(_list_tools("["))

    assert total == 0
    assert tools == []


def test_format_doc_includes_calls_llm_metadata():
    service = ToolService()
    doc = {
        "_id": "tool-1",
        "code": "get_stock_news_openai",
        "name": "get_stock_news_openai",
        "description": "AI news",
        "type": "builtin",
        "calls_llm": True,
        "estimated_tokens": 2000,
    }

    formatted = service._format_doc(doc)

    assert formatted["calls_llm"] is True
    assert formatted["estimated_tokens"] == 2000


def test_format_doc_defaults_calls_llm_metadata_when_missing():
    service = ToolService()
    doc = {
        "_id": "tool-2",
        "code": "calculator",
        "name": "calculator",
        "description": "math",
        "type": "builtin",
    }

    formatted = service._format_doc(doc)

    assert formatted["calls_llm"] is False
    assert formatted["estimated_tokens"] == 0
