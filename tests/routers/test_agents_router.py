"""Tests for the Agent management router."""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers import agents as agents_module


class _FakeProvider:
    def __init__(self, name="deepseek", display_name="DeepSeek", api_key="key"):
        self.name = name
        self.display_name = display_name
        self.default_base_url = "https://api.deepseek.com"
        self.default_models = ["deepseek-chat"]
        self.api_key = api_key


class _FakeAgentService:
    def __init__(self):
        self._created_payload = None
        self._updated_payload = None
        self._toggle_record = None

    def _public_payload(self, data):
        payload = dict(data)
        if "model_config_agent" in payload:
            payload["model_config"] = payload.pop("model_config_agent")
        return payload

    async def list_agents(self, **kwargs):
        return ([{"id": "agent-1", "code": "market_analyst", "name": "市场分析师"}], 1)

    async def get_agent(self, agent_id):
        if agent_id == "missing":
            return None
        return {"id": agent_id, "code": "market_analyst", "name": "市场分析师"}

    async def get_agent_by_code(self, code):
        return None

    async def create_agent(self, data):
        self._created_payload = data
        return {"id": "agent-1", **self._public_payload(data)}

    async def update_agent(self, agent_id, data):
        self._updated_payload = data
        return {"id": agent_id, "code": "market_analyst", **self._public_payload(data)}

    async def delete_agent(self, agent_id):
        if agent_id == "missing":
            return False
        return True

    async def toggle_agent(self, agent_id, enabled):
        self._toggle_record = (agent_id, enabled)
        return agent_id != "missing"

    async def get_all_tags(self):
        return ["分析"]

    async def record_usage(self, agent_id):
        return None


@pytest.fixture
def fake_service(monkeypatch):
    service = _FakeAgentService()
    monkeypatch.setattr(agents_module, "agent_service", service)
    return service


@pytest.fixture
def client(fake_service):
    app = FastAPI()
    app.include_router(agents_module.router, prefix="/api")
    app.dependency_overrides[agents_module.get_current_user] = lambda: {"id": "user-1"}
    return TestClient(app)


def test_list_agents(client):
    response = client.get("/api/agents/")

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"]["total"] == 1
    assert body["data"]["items"][0]["code"] == "market_analyst"


def test_get_agent_missing_returns_404(client):
    response = client.get("/api/agents/missing")

    assert response.status_code == 404


def test_create_agent_uses_public_model_config_contract(client, fake_service):
    response = client.post("/api/agents/", json={
        "code": "market_analyst",
        "name": "市场分析师",
        "prompt_id": "507f1f77bcf86cd799439011",
        "model_config": {
            "provider": "deepseek",
            "model": "deepseek-chat",
        },
    })

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"]["code"] == "market_analyst"
    assert body["data"]["model_config"] == {
        "provider": "deepseek",
        "model": "deepseek-chat",
        "temperature": 0.7,
        "max_tokens": 4096,
    }
    assert "model_config_agent" not in body["data"]
    assert fake_service._created_payload["model_config_agent"] == {
        "provider": "deepseek",
        "model": "deepseek-chat",
        "temperature": 0.7,
        "max_tokens": 4096,
    }


def test_create_agent(client):
    response = client.post("/api/agents/", json={
        "code": "market_analyst",
        "name": "市场分析师",
        "prompt_id": "507f1f77bcf86cd799439011",
    })

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"]["code"] == "market_analyst"


def test_update_agent_uses_public_model_config_contract(client):
    response = client.put("/api/agents/agent-1", json={
        "model_config": {
            "provider": "openai",
            "model": "gpt-4.1",
        },
    })

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"]["model_config"] == {
        "provider": "openai",
        "model": "gpt-4.1",
    }
    assert "model_config_agent" not in body["data"]


def test_update_agent_accepts_public_null_model_config(client, fake_service):
    response = client.put("/api/agents/agent-1", json={"model_config": None})

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"]["model_config"] is None
    assert "model_config_agent" not in body["data"]
    assert fake_service._updated_payload["model_config_agent"] is None


def test_toggle_agent_requires_enabled(client):
    response = client.put("/api/agents/agent-1/toggle", json={})

    assert response.status_code == 400


def test_toggle_agent_success(client, fake_service):
    response = client.put("/api/agents/agent-1/toggle", json={"enabled": False})

    assert response.status_code == 200
    assert fake_service._toggle_record == ("agent-1", False)


def test_get_tags(client):
    response = client.get("/api/agents/tags")

    assert response.status_code == 200
    assert response.json()["data"] == ["分析"]


def test_get_models_returns_provider_summary(client, monkeypatch):
    class _FakeConfigService:
        async def get_llm_providers(self):
            return [_FakeProvider()]

    monkeypatch.setattr(
        "app.services.config_service.ConfigService",
        lambda: _FakeConfigService(),
    )

    response = client.get("/api/agents/models")

    assert response.status_code == 200
    items = response.json()["data"]
    assert items[0]["name"] == "deepseek"
    assert items[0]["has_api_key"] is True


def test_test_run_agent_streams_tokens(client, monkeypatch, fake_service):
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
                    content = "测试输出"

                yield _Chunk()

        llm = _Llm()

    async def fake_build_agent(agent_id, variables=None):
        return _Spec()

    monkeypatch.setattr(fake_service, "build_agent", fake_build_agent, raising=False)

    response = client.post(
        "/api/agents/agent-1/test-run",
        json={"message": "分析 000001", "variables": {}},
    )

    assert response.status_code == 200
    assert "text/event-stream" in response.headers["content-type"]
    body = response.text
    assert "event: token" in body
    assert "测试输出" in body
    assert "event: done" in body


def test_test_run_passes_recursion_limit_for_tool_agents(client, monkeypatch, fake_service):
    captured = {}

    class _Spec:
        agent_id = "agent-1"
        agent_code = "market_analyst"
        agent_name = "市场分析师"
        system_prompt = "你是市场分析师。"
        messages_placeholder = "对话历史"
        tools = [object()]

        class _Params:
            timeout = 300
            max_tool_calls = 3
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

    async def fake_build_agent(agent_id, variables=None):
        return _Spec()

    monkeypatch.setattr(fake_service, "build_agent", fake_build_agent, raising=False)
    monkeypatch.setattr("langgraph.prebuilt.create_react_agent", lambda llm, tools: _FakeAgent())

    response = client.post(
        "/api/agents/agent-1/test-run",
        json={"message": "分析 000001", "variables": {}},
    )

    assert response.status_code == 200
    assert captured["stream_mode"] == "messages"
    assert captured["config"] == {"recursion_limit": 3}


def test_test_run_requires_message(client):
    response = client.post("/api/agents/agent-1/test-run", json={})

    assert response.status_code == 400
