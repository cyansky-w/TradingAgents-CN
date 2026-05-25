"""Tests for workflow seed data."""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.workflows.seed_workflows import WORKFLOW_SEEDS


def test_workflow_seeds_structure():
    """Every seed must have required fields and valid DAG structure."""
    for seed in WORKFLOW_SEEDS:
        code = seed["code"]
        assert seed["name"], f"{code}: name is required"
        assert seed["message_template"], f"{code}: message_template is required"
        assert len(seed["nodes"]) >= 2, f"{code}: must have at least start/end nodes"
        assert len(seed["edges"]) >= 1, f"{code}: must have at least one edge"

        # Check IO nodes
        io_nodes = [n for n in seed["nodes"] if n["type"] == "io"]
        input_nodes = [n for n in io_nodes if n["config"].get("io_direction") == "input"]
        output_nodes = [n for n in io_nodes if n["config"].get("io_direction") == "output"]
        assert len(input_nodes) == 1, f"{code}: must have exactly one input IO node"
        assert len(output_nodes) == 1, f"{code}: must have exactly one output IO node"

        # Check agent nodes reference agent_code (not agent_id)
        agent_nodes = [n for n in seed["nodes"] if n["type"] == "agent"]
        for node in agent_nodes:
            assert "agent_code" in node["config"], (
                f"{code}/{node['id']}: must use agent_code (resolved at seed time)"
            )

        # Check edge references are valid
        node_ids = {n["id"] for n in seed["nodes"]}
        for edge in seed["edges"]:
            assert edge["source"] in node_ids, f"{code}: edge source {edge['source']} not in nodes"
            assert edge["target"] in node_ids, f"{code}: edge target {edge['target']} not in nodes"

        # Check is_system flag is set
        assert seed.get("is_system", True) is True, f"{code}: system workflows must be is_system=True"


def test_workflow_seeds_unique_codes():
    codes = [s["code"] for s in WORKFLOW_SEEDS]
    assert len(codes) == len(set(codes)), "Workflow seed codes must be unique"


def test_seed_skips_existing():
    """If workflow already exists by code, it should be skipped."""
    async def _run():
        with patch("app.workflows.seed_workflows.workflow_service") as mock_svc:
            mock_svc.get_workflow_by_code = AsyncMock(return_value={"id": "existing"})
            mock_svc.create_workflow = AsyncMock()

            with patch("app.services.agent_service.agent_service"):
                from app.workflows.seed_workflows import seed_workflows_to_db
                result = await seed_workflows_to_db()

            assert result["created"] == 0
            assert result["skipped"] == len(WORKFLOW_SEEDS)
            mock_svc.create_workflow.assert_not_called()

    asyncio.run(_run())


def test_seed_resolves_agent_code():
    """agent_code in config must be resolved to agent_id."""
    async def _run():
        mock_agent_svc = MagicMock()
        mock_agent_svc.get_agent_by_code = AsyncMock(return_value={"id": "agent_123"})

        with patch("app.workflows.seed_workflows.workflow_service") as mock_svc, \
             patch("app.services.agent_service.agent_service", mock_agent_svc):
            mock_svc.get_workflow_by_code = AsyncMock(return_value=None)
            mock_svc.create_workflow = AsyncMock()

            from app.workflows.seed_workflows import seed_workflows_to_db
            result = await seed_workflows_to_db()

            assert result["created"] == len(WORKFLOW_SEEDS)
            assert result["failed"] == []

            # Verify no agent_code leaked into created docs
            for call in mock_svc.create_workflow.call_args_list:
                data = call[0][0]
                for node in data["nodes"]:
                    if node["type"] == "agent":
                        assert "agent_code" not in node["config"]
                        assert node["config"].get("agent_id") == "agent_123"

    asyncio.run(_run())


def test_seed_fails_if_agent_missing():
    """If an agent_code doesn't exist, that workflow should fail."""
    async def _run():
        mock_agent_svc = MagicMock()
        mock_agent_svc.get_agent_by_code = AsyncMock(return_value=None)

        with patch("app.workflows.seed_workflows.workflow_service") as mock_svc, \
             patch("app.services.agent_service.agent_service", mock_agent_svc):
            mock_svc.get_workflow_by_code = AsyncMock(return_value=None)
            mock_svc.create_workflow = AsyncMock()

            from app.workflows.seed_workflows import seed_workflows_to_db
            result = await seed_workflows_to_db()

            assert result["created"] == 0
            assert len(result["failed"]) == len(WORKFLOW_SEEDS)

    asyncio.run(_run())
