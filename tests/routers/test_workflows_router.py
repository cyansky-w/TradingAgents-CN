"""Tests for the Workflow management router."""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers import workflows as workflows_module


class _FakeWorkflowService:
    def __init__(self):
        self._toggle_record = None

    async def list_workflows(self, **kwargs):
        return ([{"id": "wf-1", "code": "daily_review", "name": "每日复盘工作流"}], 1)

    async def get_workflow(self, workflow_id):
        if workflow_id == "missing":
            return None
        return {"id": workflow_id, "code": "daily_review", "name": "每日复盘工作流", "nodes": [], "edges": []}

    async def create_workflow(self, data):
        return {"id": "wf-new", **data}

    async def update_workflow(self, workflow_id, data):
        return {"id": workflow_id, "code": "daily_review", **data}

    async def delete_workflow(self, workflow_id):
        if workflow_id == "missing":
            return False
        return True

    async def toggle_workflow(self, workflow_id, enabled):
        self._toggle_record = (workflow_id, enabled)
        return workflow_id != "missing"

    async def get_all_tags(self):
        return ["复盘"]

    async def validate_dag(self, workflow_id):
        if workflow_id == "missing":
            raise ValueError("工作流不存在")
        return {"valid": True, "errors": [], "warnings": []}


@pytest.fixture
def fake_service(monkeypatch):
    service = _FakeWorkflowService()
    monkeypatch.setattr(workflows_module, "workflow_service", service)
    return service


@pytest.fixture
def client(fake_service):
    app = FastAPI()
    app.include_router(workflows_module.router, prefix="/api")
    app.dependency_overrides[workflows_module.get_current_user] = lambda: {"id": "user-1"}
    return TestClient(app)


def test_list_workflows(client):
    response = client.get("/api/workflows/")

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"]["total"] == 1
    assert body["data"]["items"][0]["code"] == "daily_review"


def test_get_workflow_missing_returns_404(client):
    response = client.get("/api/workflows/missing")

    assert response.status_code == 404


def test_create_workflow(client):
    response = client.post("/api/workflows/", json={
        "code": "test_wf",
        "name": "测试工作流",
        "message_template": "请分析 {{ticker}}",
    })

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"]["code"] == "test_wf"


def test_update_workflow(client):
    response = client.put("/api/workflows/wf-1", json={
        "name": "新名称",
    })

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"]["name"] == "新名称"


def test_update_workflow_no_fields(client):
    response = client.put("/api/workflows/wf-1", json={})

    assert response.status_code == 400


def test_delete_workflow(client):
    response = client.delete("/api/workflows/wf-1")

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True


def test_delete_workflow_missing(client):
    response = client.delete("/api/workflows/missing")

    assert response.status_code == 404


def test_toggle_workflow_requires_enabled(client):
    response = client.put("/api/workflows/wf-1/toggle", json={})

    assert response.status_code == 400


def test_toggle_workflow_success(client, fake_service):
    response = client.put("/api/workflows/wf-1/toggle", json={"enabled": False})

    assert response.status_code == 200
    assert fake_service._toggle_record == ("wf-1", False)


def test_toggle_workflow_missing(client):
    response = client.put("/api/workflows/missing/toggle", json={"enabled": True})

    assert response.status_code == 404


def test_get_tags(client):
    response = client.get("/api/workflows/tags")

    assert response.status_code == 200
    assert response.json()["data"] == ["复盘"]


def test_validate_workflow(client):
    response = client.post("/api/workflows/wf-1/validate")

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"]["valid"] is True


def test_validate_workflow_missing(client):
    response = client.post("/api/workflows/missing/validate")

    assert response.status_code == 404


def test_create_workflow_with_full_dag(client):
    response = client.post("/api/workflows/", json={
        "code": "full_wf",
        "name": "完整工作流",
        "message_template": "请分析 {{date}}",
        "nodes": [
            {"id": "start", "type": "io", "label": "开始", "config": {"io_direction": "input"}},
            {"id": "agent1", "type": "agent", "label": "分析师", "config": {"agent_id": "507f1f77bcf86cd799439011"}},
            {"id": "end", "type": "io", "label": "结束", "config": {"io_direction": "output"}},
        ],
        "edges": [
            {"id": "e1", "source": "start", "target": "agent1"},
            {"id": "e2", "source": "agent1", "target": "end"},
        ],
        "settings": {"timeout": 1800, "on_failure": "stop", "retry_count": 1},
        "tags": ["测试"],
    })

    assert response.status_code == 200
    body = response.json()
    assert body["data"]["code"] == "full_wf"
    assert len(body["data"]["nodes"]) == 3
    assert len(body["data"]["edges"]) == 2
