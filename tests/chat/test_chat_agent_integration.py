"""Chat conversation + agent integration tests."""
from __future__ import annotations

import asyncio

import pytest

import app.chat.service as chat_service_module
from app.chat.models import Conversation
from app.chat.schemas import ConversationCreate
from app.chat.service import ChatService


class _FakeMemory:
    async def add_to_buffer(self, *args, **kwargs):
        return None

    async def get_buffer(self, *args, **kwargs):
        return []

    async def recall_long_term(self, *args, **kwargs):
        return []

    async def persist_to_long_term(self, *args, **kwargs):
        return None


class _UpdateResult:
    def __init__(self, matched_count=1, modified_count=1):
        self.matched_count = matched_count
        self.modified_count = modified_count


class _FakeConversations:
    def __init__(self):
        self.docs = []

    async def insert_one(self, doc):
        self.docs.append(dict(doc))
        return None

    async def find_one(self, query):
        for doc in self.docs:
            if all(doc.get(key) == value for key, value in query.items()):
                return doc
        return None

    async def update_one(self, query, update):
        doc = await self.find_one(query)
        if not doc:
            return _UpdateResult(matched_count=0, modified_count=0)
        for key, value in update.get("$set", {}).items():
            doc[key] = value
        for key, value in update.get("$inc", {}).items():
            doc[key] = doc.get(key, 0) + value
        return _UpdateResult()

    def find(self, query):
        class _Cursor:
            def __init__(self, docs):
                self._docs = docs

            def sort(self, *args, **kwargs):
                return self

            def limit(self, *args, **kwargs):
                return self

            def __aiter__(self):
                self._iter = iter(self._docs)
                return self

            async def __anext__(self):
                try:
                    return next(self._iter)
                except StopIteration:
                    raise StopAsyncIteration

        return _Cursor([doc for doc in self.docs if all(doc.get(k) == v for k, v in query.items())])


class _FakeMessages:
    def __init__(self):
        self.docs = []

    async def insert_one(self, doc):
        self.docs.append(dict(doc))
        return None

    def find(self, query):
        return _FakeConversations().find(query)


class _ChatServiceForTest(ChatService):
    def __init__(self):
        super().__init__(_FakeMemory())
        self._conversations = _FakeConversations()
        self._messages = _FakeMessages()

    @property
    def conversations_col(self):
        return self._conversations

    @property
    def messages_col(self):
        return self._messages


@pytest.mark.asyncio
async def test_create_conversation_stores_agent_id_in_metadata():
    service = _ChatServiceForTest()

    conv = await service.create_conversation(
        "user-1",
        ConversationCreate(title="Agent Chat", agent_id="agent-1"),
    )

    assert conv.metadata == {"agent_id": "agent-1"}
    assert service._conversations.docs[0]["metadata"] == {"agent_id": "agent-1"}


@pytest.mark.asyncio
async def test_create_conversation_without_agent_id_keeps_metadata_empty():
    service = _ChatServiceForTest()

    conv = await service.create_conversation(
        "user-1",
        ConversationCreate(title="Plain Chat"),
    )

    assert conv.metadata == {}


@pytest.mark.asyncio
async def test_send_message_uses_agent_prompt_and_llm_when_conversation_has_agent(monkeypatch):
    service = _ChatServiceForTest()
    conv = Conversation(user_id="user-1", title="Agent Chat", metadata={"agent_id": "agent-1"})
    await service.conversations_col.insert_one(conv.model_dump())

    class _Spec:
        agent_id = "agent-1"
        agent_code = "market_analyst"
        agent_name = "市场分析师"
        system_prompt = "你是市场分析师。"
        messages_placeholder = "对话历史"
        tools = []

        class _Params:
            timeout = 300
            max_tool_calls = 10
            retry_on_failure = False

        parameters = _Params()

        class _Llm:
            async def ainvoke(self, messages):
                from langchain_core.messages import AIMessage

                assert messages[0].content == "你是市场分析师。"
                return AIMessage(
                    content="agent-non-stream-output",
                    usage_metadata={"input_tokens": 11, "output_tokens": 7, "total_tokens": 18},
                )

        llm = _Llm()

    captured = {"build_called": False, "recorded": False}

    class _FakeAgentService:
        async def build_agent(self, agent_id, variables=None):
            assert agent_id == "agent-1"
            captured["build_called"] = True
            return _Spec()

        async def record_usage(self, agent_id):
            assert agent_id == "agent-1"
            captured["recorded"] = True

    import app.chat.service as chat_service_module
    import app.services.agent_service as agent_module
    monkeypatch.setattr(agent_module, "agent_service", _FakeAgentService())

    async def _fail_create_chat_llm(*args, **kwargs):
        raise AssertionError("default create_chat_llm path should not be used")

    monkeypatch.setattr(chat_service_module, "create_chat_llm", _fail_create_chat_llm)

    response = await service.send_message(
        "user-1",
        type("_Req", (), {"conversation_id": conv.id, "message": "hello"})(),
    )

    assert response.role == "assistant"
    assert response.content == "agent-non-stream-output"
    assert response.token_usage == {"prompt": 11, "completion": 7, "total": 18}
    assert captured["build_called"] is True
    assert captured["recorded"] is True
    assert service._messages.docs[-1]["content"] == "agent-non-stream-output"


@pytest.mark.asyncio
async def test_send_message_uses_react_agent_with_recursion_limit_when_agent_has_tools(monkeypatch):
    service = _ChatServiceForTest()
    conv = Conversation(user_id="user-1", title="Agent Chat", metadata={"agent_id": "agent-1"})
    await service.conversations_col.insert_one(conv.model_dump())

    captured = {"build_called": False, "recorded": False, "config": None}

    class _Spec:
        agent_id = "agent-1"
        agent_code = "market_analyst"
        agent_name = "市场分析师"
        system_prompt = "你是市场分析师。"
        messages_placeholder = "对话历史"
        tools = [object()]

        class _Params:
            timeout = 300
            max_tool_calls = 4
            retry_on_failure = False

        parameters = _Params()
        llm = object()

    class _FakeAgentService:
        async def build_agent(self, agent_id, variables=None):
            assert agent_id == "agent-1"
            captured["build_called"] = True
            return _Spec()

        async def record_usage(self, agent_id):
            assert agent_id == "agent-1"
            captured["recorded"] = True

    class _FakeAgent:
        async def ainvoke(self, payload, config=None):
            from langchain_core.messages import AIMessage

            captured["config"] = config
            assert payload["messages"][0].content == "你是市场分析师。"
            return {"messages": [AIMessage(content="tool-agent-output")]}

    import app.chat.service as chat_service_module
    import app.services.agent_service as agent_module
    monkeypatch.setattr(agent_module, "agent_service", _FakeAgentService())

    async def _fail_create_chat_llm(*args, **kwargs):
        raise AssertionError("default create_chat_llm path should not be used")

    monkeypatch.setattr(chat_service_module, "create_chat_llm", _fail_create_chat_llm)
    monkeypatch.setattr("langgraph.prebuilt.create_react_agent", lambda llm, tools: _FakeAgent())

    response = await service.send_message(
        "user-1",
        type("_Req", (), {"conversation_id": conv.id, "message": "hello"})(),
    )

    assert response.content == "tool-agent-output"
    assert captured["build_called"] is True
    assert captured["recorded"] is True
    assert captured["config"] == {"recursion_limit": 4}


@pytest.mark.asyncio
async def test_iterate_with_optional_timeout_uses_total_elapsed_deadline():
    async def _slow_events():
        yield 1
        await asyncio.sleep(0.04)
        yield 2
        await asyncio.sleep(0.04)
        yield 3

    events = []
    with pytest.raises(asyncio.TimeoutError):
        async for event in chat_service_module._iterate_with_optional_timeout(_slow_events(), 0.06):
            events.append(event)

    assert events == [1, 2]


@pytest.mark.asyncio
async def test_stream_response_fallback_does_not_record_usage_when_agent_build_fails(monkeypatch):
    service = _ChatServiceForTest()
    conv = Conversation(user_id="user-1", title="Agent Chat", metadata={"agent_id": "agent-1"})
    await service.conversations_col.insert_one(conv.model_dump())

    captured = {"record_usage_called": False}

    class _FakeAgentService:
        async def build_agent(self, agent_id, variables=None):
            raise RuntimeError("boom")

        async def record_usage(self, agent_id):
            captured["record_usage_called"] = True

    class _FallbackLlm:
        async def astream(self, messages):
            class _Chunk:
                content = "fallback-output"

            yield _Chunk()

    import app.services.agent_service as agent_module
    monkeypatch.setattr(agent_module, "agent_service", _FakeAgentService())

    async def _fake_create_chat_llm(*args, **kwargs):
        return _FallbackLlm()

    monkeypatch.setattr(chat_service_module, "create_chat_llm", _fake_create_chat_llm)

    events = []
    async for event in service.stream_response("user-1", conv.id, "hello"):
        events.append(event)
        if event["event"] == "done":
            break

    assert any(
        event["event"] == "token" and event["data"].get("content") == "fallback-output"
        for event in events
    )
    assert captured["record_usage_called"] is False


@pytest.mark.asyncio
async def test_stream_response_uses_agent_service_when_conversation_has_agent(monkeypatch):
    service = _ChatServiceForTest()
    conv = Conversation(user_id="user-1", title="Agent Chat", metadata={"agent_id": "agent-1"})
    await service.conversations_col.insert_one(conv.model_dump())

    class _Spec:
        agent_id = "agent-1"
        agent_code = "market_analyst"
        agent_name = "市场分析师"
        system_prompt = "你是市场分析师。"
        messages_placeholder = "对话历史"
        tools = []

        class _Params:
            timeout = 300
            max_tool_calls = 10
            retry_on_failure = False

        parameters = _Params()

        class _Llm:
            async def astream(self, messages):
                class _Chunk:
                    content = "agent-output"

                yield _Chunk()

        llm = _Llm()

    captured = {"recorded": False}

    class _FakeAgentService:
        async def build_agent(self, agent_id, variables=None):
            assert agent_id == "agent-1"
            return _Spec()

        async def record_usage(self, agent_id):
            assert agent_id == "agent-1"
            captured["recorded"] = True

    fake_service = _FakeAgentService()

    import app.services.agent_service as agent_module
    monkeypatch.setattr(agent_module, "agent_service", fake_service)

    events = []
    async for event in service.stream_response("user-1", conv.id, "hello"):
        events.append(event)
        if event["event"] == "done":
            break

    assert any(
        event["event"] == "token" and event["data"].get("content") == "agent-output"
        for event in events
    )
    assert captured["recorded"] is True


@pytest.mark.asyncio
async def test_stream_response_passes_recursion_limit_for_agent_tools(monkeypatch):
    service = _ChatServiceForTest()
    conv = Conversation(user_id="user-1", title="Agent Chat", metadata={"agent_id": "agent-1"})
    await service.conversations_col.insert_one(conv.model_dump())

    captured = {"recorded": False}

    class _Spec:
        agent_id = "agent-1"
        agent_code = "market_analyst"
        agent_name = "市场分析师"
        system_prompt = "你是市场分析师。"
        messages_placeholder = "对话历史"
        tools = [object()]

        class _Params:
            timeout = 300
            max_tool_calls = 4
            retry_on_failure = False

        parameters = _Params()
        llm = object()

    class _FakeAgent:
        async def astream(self, payload, stream_mode=None, config=None):
            captured["payload"] = payload
            captured["stream_mode"] = stream_mode
            captured["config"] = config
            if False:
                yield None

    class _FakeAgentService:
        async def build_agent(self, agent_id, variables=None):
            assert agent_id == "agent-1"
            return _Spec()

        async def record_usage(self, agent_id):
            assert agent_id == "agent-1"
            captured["recorded"] = True

    import app.services.agent_service as agent_module
    monkeypatch.setattr(agent_module, "agent_service", _FakeAgentService())
    monkeypatch.setattr("langgraph.prebuilt.create_react_agent", lambda llm, tools: _FakeAgent())

    events = []
    async for event in service.stream_response("user-1", conv.id, "hello"):
        events.append(event)
        if event["event"] == "done":
            break

    assert captured["stream_mode"] == "messages"
    assert captured["config"] == {"recursion_limit": 4}
    assert captured["recorded"] is True
    assert events[-1]["event"] == "done"
