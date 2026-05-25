"""Tests for the Workflow management service."""
import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from bson import ObjectId

from app.services.workflow_service import WorkflowService


VALID_OID = str(ObjectId())


def _make_service():
    svc = WorkflowService()
    svc._indexes_ensured = True
    return svc


def _make_doc(**overrides):
    doc = {
        "_id": VALID_OID,
        "code": "daily_review",
        "name": "每日复盘工作流",
        "description": "盘后自动执行全链路复盘分析",
        "version": 1,
        "trigger": {"type": "manual"},
        "message_template": "请分析 {{date}}",
        "output_template": None,
        "nodes": [],
        "edges": [],
        "settings": {"timeout": 3600, "on_failure": "notify", "retry_count": 0},
        "tags": ["复盘"],
        "enabled": True,
        "is_system": False,
        "usage_count": 0,
        "last_used_at": None,
        "created_at": datetime(2026, 1, 1),
        "updated_at": datetime(2026, 1, 1),
    }
    doc.update(overrides)
    return doc


class TestFormatDoc:
    def test_formats_all_fields(self):
        service = _make_service()
        doc = _make_doc()
        result = service._format_doc(doc)
        assert result["id"] == VALID_OID
        assert result["code"] == "daily_review"
        assert result["name"] == "每日复盘工作流"
        assert result["tags"] == ["复盘"]
        assert result["enabled"] is True

    def test_returns_none_for_none(self):
        service = _make_service()
        assert service._format_doc(None) is None


class TestCreateWorkflow:
    def test_create_success(self):
        async def _test():
            service = _make_service()
            mock_db = AsyncMock()
            mock_db.workflows.find_one = AsyncMock(return_value=None)
            mock_db.workflows.insert_one = AsyncMock(
                return_value=MagicMock(inserted_id=ObjectId())
            )
            service.db = mock_db

            data = {
                "code": "test_wf",
                "name": "测试工作流",
                "message_template": "请分析 {{ticker}}",
            }
            result = await service.create_workflow(data)
            assert result["code"] == "test_wf"
            assert result["name"] == "测试工作流"
            mock_db.workflows.insert_one.assert_called_once()

        asyncio.run(_test())

    def test_create_duplicate_code(self):
        async def _test():
            service = _make_service()
            mock_db = AsyncMock()
            mock_db.workflows.find_one = AsyncMock(return_value={"code": "test_wf"})
            service.db = mock_db

            with pytest.raises(ValueError, match="已存在"):
                await service.create_workflow({"code": "test_wf", "name": "dup"})

        asyncio.run(_test())

    def test_create_empty_name(self):
        async def _test():
            service = _make_service()
            mock_db = AsyncMock()
            mock_db.workflows.find_one = AsyncMock(return_value=None)
            service.db = mock_db

            with pytest.raises(ValueError, match="名称不能为空"):
                await service.create_workflow({"code": "test_wf", "name": ""})

        asyncio.run(_test())


class TestUpdateWorkflow:
    def test_update_success(self):
        async def _test():
            service = _make_service()
            mock_db = AsyncMock()
            existing = _make_doc()
            updated = _make_doc(name="新名称")
            # find_one called: 1) load current, 2) _check_name_unique (return None=not taken), 3) reload after update
            mock_db.workflows.find_one = AsyncMock(side_effect=[existing, None, updated])
            mock_db.workflows.update_one = AsyncMock()
            service.db = mock_db

            result = await service.update_workflow(VALID_OID, {"name": "新名称"})
            assert result["name"] == "新名称"

        asyncio.run(_test())

    def test_update_not_found(self):
        async def _test():
            service = _make_service()
            mock_db = AsyncMock()
            mock_db.workflows.find_one = AsyncMock(return_value=None)
            service.db = mock_db

            with pytest.raises(ValueError, match="不存在"):
                await service.update_workflow(VALID_OID, {"name": "x"})

        asyncio.run(_test())

    def test_update_no_fields_returns_current(self):
        async def _test():
            service = _make_service()
            mock_db = AsyncMock()
            existing = _make_doc()
            mock_db.workflows.find_one = AsyncMock(return_value=existing)
            service.db = mock_db

            result = await service.update_workflow(VALID_OID, {})
            assert result["name"] == "每日复盘工作流"
            mock_db.workflows.update_one.assert_not_called()

        asyncio.run(_test())


class TestDeleteWorkflow:
    def test_delete_success(self):
        async def _test():
            service = _make_service()
            mock_db = AsyncMock()
            mock_db.workflows.find_one = AsyncMock(return_value=_make_doc())
            mock_db.workflows.delete_one = AsyncMock(
                return_value=MagicMock(deleted_count=1)
            )
            service.db = mock_db

            assert await service.delete_workflow(VALID_OID) is True

        asyncio.run(_test())

    def test_delete_not_found(self):
        async def _test():
            service = _make_service()
            mock_db = AsyncMock()
            mock_db.workflows.find_one = AsyncMock(return_value=None)
            service.db = mock_db

            assert await service.delete_workflow(VALID_OID) is False

        asyncio.run(_test())

    def test_delete_system_workflow(self):
        async def _test():
            service = _make_service()
            mock_db = AsyncMock()
            mock_db.workflows.find_one = AsyncMock(
                return_value=_make_doc(is_system=True)
            )
            service.db = mock_db

            with pytest.raises(ValueError, match="不能删除"):
                await service.delete_workflow(VALID_OID)

        asyncio.run(_test())


class TestToggleWorkflow:
    def test_toggle_success(self):
        async def _test():
            service = _make_service()
            mock_db = AsyncMock()
            mock_db.workflows.update_one = AsyncMock(
                return_value=MagicMock(matched_count=1)
            )
            service.db = mock_db

            assert await service.toggle_workflow(VALID_OID, False) is True

        asyncio.run(_test())

    def test_toggle_not_found(self):
        async def _test():
            service = _make_service()
            mock_db = AsyncMock()
            mock_db.workflows.update_one = AsyncMock(
                return_value=MagicMock(matched_count=0)
            )
            service.db = mock_db

            assert await service.toggle_workflow(VALID_OID, True) is False

        asyncio.run(_test())


class TestListWorkflows:
    def test_list_builds_search_query(self):
        """Verify list_workflows constructs the right MongoDB query for search."""
        async def _test():
            service = _make_service()
            captured_query = {}

            mock_collection = MagicMock()
            mock_collection.count_documents = AsyncMock(return_value=0)

            cursor = MagicMock()
            cursor.to_list = AsyncMock(return_value=[])
            mock_collection.find = MagicMock(
                return_value=MagicMock(
                    sort=MagicMock(
                        return_value=MagicMock(
                            skip=MagicMock(
                                return_value=MagicMock(
                                    return_value=cursor,
                                    limit=MagicMock(return_value=cursor),
                                )
                            )
                        )
                    )
                )
            )

            mock_db = MagicMock()
            mock_db.workflows = mock_collection
            service.db = mock_db

            items, total = await service.list_workflows(search="复盘", tag="分析", enabled=True)
            assert total == 0
            assert items == []

            # Verify count_documents was called with correct query
            call_args = mock_collection.count_documents.call_args[0][0]
            assert call_args["tags"] == "分析"
            assert call_args["enabled"] is True
            assert "$or" in call_args

        asyncio.run(_test())


class TestGetAllTags:
    def test_returns_sorted_tags(self):
        async def _test():
            service = _make_service()
            mock_db = AsyncMock()
            mock_db.workflows.distinct = AsyncMock(return_value=["分析", "复盘", ""])
            service.db = mock_db

            tags = await service.get_all_tags()
            assert tags == ["分析", "复盘"]

        asyncio.run(_test())


class TestValidateDag:
    def test_valid_simple_dag(self):
        async def _test():
            service = _make_service()
            agent_oid = str(ObjectId())
            nodes = [
                {"id": "start", "type": "io", "label": "开始", "config": {"io_direction": "input"}},
                {"id": "agent1", "type": "agent", "label": "分析师", "config": {"agent_id": agent_oid}},
                {"id": "end", "type": "io", "label": "结束", "config": {"io_direction": "output"}},
            ]
            edges = [
                {"id": "e1", "source": "start", "target": "agent1"},
                {"id": "e2", "source": "agent1", "target": "end"},
            ]

            mock_db = AsyncMock()
            mock_db.agents.find_one = AsyncMock(
                return_value={"name": "分析师", "enabled": True}
            )
            service.db = mock_db

            with patch.object(service, "get_workflow", new_callable=AsyncMock) as mock_get:
                mock_get.return_value = {"id": VALID_OID, "nodes": nodes, "edges": edges}
                result = await service.validate_dag(VALID_OID)

            assert result["valid"] is True
            assert len(result["errors"]) == 0

        asyncio.run(_test())

    def test_detects_cycle(self):
        async def _test():
            service = _make_service()
            nodes = [
                {"id": "start", "type": "io", "label": "开始", "config": {"io_direction": "input"}},
                {"id": "a", "type": "agent", "label": "A", "config": {"agent_id": str(ObjectId())}},
                {"id": "b", "type": "agent", "label": "B", "config": {"agent_id": str(ObjectId())}},
                {"id": "end", "type": "io", "label": "结束", "config": {"io_direction": "output"}},
            ]
            edges = [
                {"id": "e1", "source": "start", "target": "a"},
                {"id": "e2", "source": "a", "target": "b"},
                {"id": "e3", "source": "b", "target": "a"},
                {"id": "e4", "source": "b", "target": "end"},
            ]

            service.db = AsyncMock()

            with patch.object(service, "get_workflow", new_callable=AsyncMock) as mock_get:
                mock_get.return_value = {"id": VALID_OID, "nodes": nodes, "edges": edges}
                result = await service.validate_dag(VALID_OID)

            assert result["valid"] is False
            assert any(e["type"] == "cycle_detected" for e in result["errors"])

        asyncio.run(_test())

    def test_missing_io_nodes(self):
        async def _test():
            service = _make_service()
            nodes = [
                {"id": "a", "type": "agent", "label": "A", "config": {"agent_id": str(ObjectId())}},
            ]
            edges = []

            service.db = AsyncMock()

            with patch.object(service, "get_workflow", new_callable=AsyncMock) as mock_get:
                mock_get.return_value = {"id": VALID_OID, "nodes": nodes, "edges": edges}
                result = await service.validate_dag(VALID_OID)

            assert result["valid"] is False
            error_types = [e["type"] for e in result["errors"]]
            assert "io_missing" in error_types

        asyncio.run(_test())

    def test_agent_node_missing_binding(self):
        async def _test():
            service = _make_service()
            nodes = [
                {"id": "start", "type": "io", "label": "开始", "config": {"io_direction": "input"}},
                {"id": "a", "type": "agent", "label": "A", "config": {}},
                {"id": "end", "type": "io", "label": "结束", "config": {"io_direction": "output"}},
            ]
            edges = [
                {"id": "e1", "source": "start", "target": "a"},
                {"id": "e2", "source": "a", "target": "end"},
            ]

            service.db = AsyncMock()

            with patch.object(service, "get_workflow", new_callable=AsyncMock) as mock_get:
                mock_get.return_value = {"id": VALID_OID, "nodes": nodes, "edges": edges}
                result = await service.validate_dag(VALID_OID)

            assert result["valid"] is False
            assert any(e["type"] == "config_missing" for e in result["errors"])

        asyncio.run(_test())

    def test_subflow_self_reference(self):
        async def _test():
            service = _make_service()
            nodes = [
                {"id": "start", "type": "io", "label": "开始", "config": {"io_direction": "input"}},
                {"id": "sub", "type": "subflow", "label": "子流程", "config": {"workflow_id": VALID_OID}},
                {"id": "end", "type": "io", "label": "结束", "config": {"io_direction": "output"}},
            ]
            edges = [
                {"id": "e1", "source": "start", "target": "sub"},
                {"id": "e2", "source": "sub", "target": "end"},
            ]

            service.db = AsyncMock()

            with patch.object(service, "get_workflow", new_callable=AsyncMock) as mock_get:
                mock_get.return_value = {"id": VALID_OID, "nodes": nodes, "edges": edges}
                result = await service.validate_dag(VALID_OID)

            assert result["valid"] is False
            assert any(e["type"] == "self_reference" for e in result["errors"])

        asyncio.run(_test())

    def test_agent_not_found_in_db(self):
        async def _test():
            service = _make_service()
            agent_oid = str(ObjectId())
            nodes = [
                {"id": "start", "type": "io", "label": "开始", "config": {"io_direction": "input"}},
                {"id": "a", "type": "agent", "label": "A", "config": {"agent_id": agent_oid}},
                {"id": "end", "type": "io", "label": "结束", "config": {"io_direction": "output"}},
            ]
            edges = [
                {"id": "e1", "source": "start", "target": "a"},
                {"id": "e2", "source": "a", "target": "end"},
            ]

            mock_db = AsyncMock()
            mock_db.agents.find_one = AsyncMock(return_value=None)
            service.db = mock_db

            with patch.object(service, "get_workflow", new_callable=AsyncMock) as mock_get:
                mock_get.return_value = {"id": VALID_OID, "nodes": nodes, "edges": edges}
                result = await service.validate_dag(VALID_OID)

            assert result["valid"] is False
            assert any(e["type"] == "ref_invalid" for e in result["errors"])

        asyncio.run(_test())

    def test_orphan_node_warning(self):
        async def _test():
            service = _make_service()
            nodes = [
                {"id": "start", "type": "io", "label": "开始", "config": {"io_direction": "input"}},
                {"id": "end", "type": "io", "label": "结束", "config": {"io_direction": "output"}},
                {"id": "lonely", "type": "agent", "label": "孤立节点", "config": {"agent_id": str(ObjectId())}},
            ]
            edges = [
                {"id": "e1", "source": "start", "target": "end"},
            ]

            service.db = AsyncMock()

            with patch.object(service, "get_workflow", new_callable=AsyncMock) as mock_get:
                mock_get.return_value = {"id": VALID_OID, "nodes": nodes, "edges": edges}
                result = await service.validate_dag(VALID_OID)

            assert any(w["type"] == "orphan_node" for w in result["warnings"])

        asyncio.run(_test())
