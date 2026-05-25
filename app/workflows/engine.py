"""
WorkflowEngine — 工作流执行引擎入口
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from bson import ObjectId

from app.core.database import get_mongo_db
from app.services.workflow_service import workflow_service
from app.workflows.graph_builder import GraphBuilder
from app.workflows.resolver import DAGResolver

logger = logging.getLogger(__name__)


class WorkflowEngine:
    """工作流执行引擎。"""

    async def run(
        self,
        workflow_id: str,
        input_data: Dict[str, Any],
        trigger_type: str = "manual",
        parent_run_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        执行工作流。

        Returns:
            包含 output 的结果字典
        """
        # 1. 加载工作流定义
        workflow = await workflow_service.get_workflow(workflow_id)
        if not workflow:
            raise ValueError("工作流不存在")
        if not workflow.get("enabled", True):
            raise ValueError("工作流未启用")

        # 2. 校验 DAG
        errors = DAGResolver.validate(workflow.get("nodes", []), workflow.get("edges", []))
        if errors:
            raise ValueError(f"工作流校验失败: {'; '.join(errors)}")

        # 3. 创建运行记录
        run_doc = await self._create_run(
            workflow_id=workflow_id,
            workflow_name=workflow.get("name", ""),
            input_data=input_data,
            trigger_type=trigger_type,
            parent_run_id=parent_run_id,
        )
        run_id = str(run_doc["_id"])

        # 4. 动态构建 StateGraph
        builder = GraphBuilder(workflow, run_id, on_node_complete=self._record_node)

        try:
            graph = await builder.build()
        except Exception as exc:
            await self._fail_run(run_id, str(exc))
            raise

        # Mark run as running
        db = await self._get_db()
        await db.workflow_runs.update_one(
            {"_id": ObjectId(run_id)},
            {"$set": {"status": "running", "started_at": datetime.utcnow()}},
        )

        # 5. 执行（带超时）
        timeout = workflow.get("settings", {}).get("timeout", 3600)
        try:
            result = await asyncio.wait_for(
                graph.ainvoke({
                    "messages": [],
                    "params": input_data,
                    "node_outputs": {},
                    "errors": [],
                    "iterations": 0,
                    "sender": "",
                }),
                timeout=timeout,
            )
            output = self._extract_final_output(result, workflow)
            await self._complete_run(run_id, output, result.get("node_outputs", {}))
            await workflow_service.record_usage(workflow_id)
            return {"output": output, "run_id": run_id}

        except asyncio.TimeoutError:
            await self._fail_run(run_id, f"执行超时 ({timeout}s)")
            raise
        except Exception as exc:
            logger.exception(f"Workflow {workflow.get('code')} execution failed")
            await self._fail_run(run_id, str(exc))
            raise

    def _extract_final_output(self, result: dict, workflow: dict) -> Any:
        """从 LangGraph 执行结果的 state 中提取最终输出。"""
        try:
            exit_id = DAGResolver.find_exit_node(workflow.get("nodes", []))
            exit_output = result.get("node_outputs", {}).get(exit_id)
            if exit_output:
                return exit_output.get("output", exit_output)
        except ValueError:
            pass
        return result.get("node_outputs", {})

    # ── Run Record Management ─────────────────────────────

    async def _create_run(
        self,
        workflow_id: str,
        workflow_name: str,
        input_data: Dict[str, Any],
        trigger_type: str,
        parent_run_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        db = await self._get_db()
        now = datetime.utcnow()
        doc = {
            "workflow_id": ObjectId(workflow_id),
            "workflow_name": workflow_name,
            "status": "pending",
            "trigger_type": trigger_type,
            "input": input_data,
            "output": None,
            "node_executions": [],
            "parent_run_id": ObjectId(parent_run_id) if parent_run_id else None,
            "started_at": now,
            "completed_at": None,
            "error": None,
            "created_at": now,
        }
        result = await db.workflow_runs.insert_one(doc)
        doc["_id"] = result.inserted_id
        return doc

    async def _complete_run(
        self,
        run_id: str,
        output: Any,
        node_outputs: Dict[str, Any],
    ) -> None:
        db = await self._get_db()
        now = datetime.utcnow()
        await db.workflow_runs.update_one(
            {"_id": ObjectId(run_id)},
            {
                "$set": {
                    "status": "completed",
                    "output": output,
                    "completed_at": now,
                    "node_executions": [
                        {"node_id": nid, "status": "completed", "output": out}
                        for nid, out in node_outputs.items()
                    ],
                }
            },
        )

    async def _fail_run(self, run_id: str, error: str) -> None:
        db = await self._get_db()
        now = datetime.utcnow()
        await db.workflow_runs.update_one(
            {"_id": ObjectId(run_id)},
            {"$set": {"status": "failed", "error": error, "completed_at": now}},
        )

    async def get_run(self, run_id: str) -> Optional[Dict[str, Any]]:
        db = await self._get_db()
        doc = await db.workflow_runs.find_one({"_id": ObjectId(run_id)})
        return self._format_run(doc) if doc else None

    async def list_runs(
        self,
        workflow_id: str,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple:
        db = await self._get_db()
        query = {"workflow_id": ObjectId(workflow_id)}
        total = await db.workflow_runs.count_documents(query)
        skip = (page - 1) * page_size
        cursor = (
            db.workflow_runs.find(query)
            .sort("created_at", -1)
            .skip(skip)
            .limit(page_size)
        )
        docs = await cursor.to_list(length=page_size)
        return [self._format_run(d) for d in docs], total

    async def cancel_run(self, run_id: str) -> bool:
        db = await self._get_db()
        result = await db.workflow_runs.update_one(
            {"_id": ObjectId(run_id), "status": "running"},
            {"$set": {"status": "cancelled", "completed_at": datetime.utcnow()}},
        )
        return result.modified_count > 0

    def _format_run(self, doc: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if not doc:
            return None
        return {
            "id": str(doc["_id"]),
            "workflow_id": str(doc["workflow_id"]),
            "workflow_name": doc.get("workflow_name", ""),
            "status": doc.get("status", "pending"),
            "trigger_type": doc.get("trigger_type", "manual"),
            "input": doc.get("input", {}),
            "output": doc.get("output"),
            "node_executions": doc.get("node_executions", []),
            "parent_run_id": str(doc["parent_run_id"]) if doc.get("parent_run_id") else None,
            "started_at": doc.get("started_at", "").isoformat() if isinstance(doc.get("started_at"), datetime) else "",
            "completed_at": doc.get("completed_at", "").isoformat() if isinstance(doc.get("completed_at"), datetime) else "",
            "error": doc.get("error"),
            "created_at": doc.get("created_at", "").isoformat() if isinstance(doc.get("created_at"), datetime) else "",
        }

    async def _get_db(self):
        return get_mongo_db()

    async def _record_node(
        self,
        run_id: str,
        node_id: str,
        status: str,
        output: Any = None,
        error: str | None = None,
    ) -> None:
        """Append a node execution record to the run document (incremental)."""
        db = await self._get_db()
        now = datetime.utcnow()
        entry: Dict[str, Any] = {
            "node_id": node_id,
            "status": status,
            "completed_at": now,
            "output": output,
            "error": error,
        }
        await db.workflow_runs.update_one(
            {"_id": ObjectId(run_id)},
            {"$push": {"node_executions": entry}},
        )


workflow_engine = WorkflowEngine()
