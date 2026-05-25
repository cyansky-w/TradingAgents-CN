"""
工作流管理服务

负责 workflows 集合 CRUD、标签管理、基础 DAG 校验。
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from bson import ObjectId
from bson.errors import InvalidId

from app.core.database import get_mongo_db
from app.workflows.resolver import DAGResolver

logger = logging.getLogger(__name__)


def _iso(dt: Any) -> str:
    if dt is None:
        return ""
    if isinstance(dt, str):
        return dt
    return dt.isoformat()


class WorkflowService:
    def __init__(self) -> None:
        self.db = None
        self._indexes_ensured = False

    async def _get_db(self):
        if self.db is None:
            self.db = get_mongo_db()
        return self.db

    async def ensure_indexes(self) -> None:
        if self._indexes_ensured:
            return
        db = await self._get_db()
        await db.workflows.create_index("code", unique=True, name="uniq_workflow_code")
        await db.workflows.create_index("name", name="idx_workflow_name")
        await db.workflows.create_index("tags", name="idx_workflow_tags")
        await db.workflows.create_index("enabled", name="idx_workflow_enabled")
        self._indexes_ensured = True
        logger.info("Workflow collection indexes ensured")

    # ── Helpers ───────────────────────────────────────────

    def _object_id(self, value: str) -> ObjectId:
        try:
            return ObjectId(value)
        except (InvalidId, TypeError):
            raise ValueError("无效的工作流 ID")

    def _format_doc(self, doc: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if doc is None:
            return None
        return {
            "id": str(doc.get("_id")),
            "code": doc.get("code", ""),
            "name": doc.get("name", ""),
            "description": doc.get("description", ""),
            "version": doc.get("version", 1),
            "trigger": doc.get("trigger", {"type": "manual"}),
            "message_template": doc.get("message_template", ""),
            "output_template": doc.get("output_template"),
            "nodes": doc.get("nodes", []),
            "edges": doc.get("edges", []),
            "settings": doc.get(
                "settings",
                {"timeout": 3600, "on_failure": "notify", "retry_count": 0},
            ),
            "tags": doc.get("tags", []),
            "enabled": doc.get("enabled", True),
            "is_system": doc.get("is_system", False),
            "usage_count": doc.get("usage_count", 0),
            "last_used_at": _iso(doc.get("last_used_at")),
            "created_at": _iso(doc.get("created_at")),
            "updated_at": _iso(doc.get("updated_at")),
        }

    async def _check_code_unique(self, code: str) -> bool:
        db = await self._get_db()
        return await db.workflows.find_one({"code": code}) is None

    async def _check_name_unique(self, name: str, exclude_id: Optional[str] = None) -> bool:
        db = await self._get_db()
        query: Dict[str, Any] = {"name": name}
        if exclude_id:
            query["_id"] = {"$ne": self._object_id(exclude_id)}
        return await db.workflows.find_one(query) is None

    # ── CRUD ──────────────────────────────────────────────

    async def list_workflows(
        self,
        *,
        search: Optional[str] = None,
        tag: Optional[str] = None,
        enabled: Optional[bool] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[Dict[str, Any]], int]:
        db = await self._get_db()
        await self.ensure_indexes()
        query: Dict[str, Any] = {}
        if tag:
            query["tags"] = tag
        if enabled is not None:
            query["enabled"] = enabled
        if search:
            query["$or"] = [
                {"name": {"$regex": search, "$options": "i"}},
                {"code": {"$regex": search, "$options": "i"}},
                {"description": {"$regex": search, "$options": "i"}},
            ]
        total = await db.workflows.count_documents(query)
        skip = (page - 1) * page_size
        cursor = db.workflows.find(query).sort("name", 1).skip(skip).limit(page_size)
        docs = await cursor.to_list(length=page_size)
        return [self._format_doc(doc) for doc in docs], total

    async def get_workflow(self, workflow_id: str) -> Optional[Dict[str, Any]]:
        db = await self._get_db()
        await self.ensure_indexes()
        doc = await db.workflows.find_one({"_id": self._object_id(workflow_id)})
        return self._format_doc(doc)

    async def get_workflow_by_code(self, code: str) -> Optional[Dict[str, Any]]:
        db = await self._get_db()
        await self.ensure_indexes()
        doc = await db.workflows.find_one({"code": code})
        return self._format_doc(doc)

    async def create_workflow(self, data: Dict[str, Any]) -> Dict[str, Any]:
        db = await self._get_db()
        await self.ensure_indexes()
        code = data.get("code", "")
        name = data.get("name", "")
        if not await self._check_code_unique(code):
            raise ValueError(f"编码 '{code}' 已存在")
        if not name:
            raise ValueError("名称不能为空")

        now = datetime.utcnow()
        doc = {
            "code": code,
            "name": name,
            "description": data.get("description", ""),
            "version": data.get("version", 1),
            "trigger": data.get("trigger", {"type": "manual"}),
            "message_template": data.get("message_template", ""),
            "output_template": data.get("output_template"),
            "nodes": data.get("nodes", []),
            "edges": data.get("edges", []),
            "settings": data.get(
                "settings",
                {"timeout": 3600, "on_failure": "notify", "retry_count": 0},
            ),
            "tags": data.get("tags", []),
            "enabled": data.get("enabled", True),
            "is_system": data.get("is_system", False),
            "usage_count": 0,
            "last_used_at": None,
            "created_at": now,
            "updated_at": now,
        }
        result = await db.workflows.insert_one(doc)
        doc["_id"] = result.inserted_id
        logger.info(f"Created workflow: {code}")
        return self._format_doc(doc)

    async def update_workflow(self, workflow_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        db = await self._get_db()
        await self.ensure_indexes()
        workflow_oid = self._object_id(workflow_id)
        current = await db.workflows.find_one({"_id": workflow_oid})
        if not current:
            raise ValueError("工作流不存在")

        update_fields: Dict[str, Any] = {}
        for key in (
            "name", "description", "version", "trigger", "message_template",
            "output_template", "nodes", "edges",
            "settings", "tags", "enabled",
        ):
            if key in data:
                update_fields[key] = data[key]

        new_name = update_fields.get("name")
        if new_name and new_name != current.get("name"):
            if not await self._check_name_unique(new_name, exclude_id=workflow_id):
                raise ValueError(f"名称 '{new_name}' 已存在")

        if not update_fields:
            return self._format_doc(current)

        update_fields["updated_at"] = datetime.utcnow()
        await db.workflows.update_one({"_id": workflow_oid}, {"$set": update_fields})
        logger.info(f"Updated workflow: {workflow_id}")
        return await self.get_workflow(workflow_id)

    async def delete_workflow(self, workflow_id: str) -> bool:
        db = await self._get_db()
        await self.ensure_indexes()
        workflow_oid = self._object_id(workflow_id)
        current = await db.workflows.find_one({"_id": workflow_oid})
        if not current:
            return False
        if current.get("is_system"):
            raise ValueError("系统工作流不能删除")
        result = await db.workflows.delete_one({"_id": workflow_oid})
        if result.deleted_count > 0:
            logger.info(f"Deleted workflow: {current.get('code')}")
            return True
        return False

    async def toggle_workflow(self, workflow_id: str, enabled: bool) -> bool:
        db = await self._get_db()
        await self.ensure_indexes()
        result = await db.workflows.update_one(
            {"_id": self._object_id(workflow_id)},
            {"$set": {"enabled": enabled, "updated_at": datetime.utcnow()}},
        )
        return result.matched_count > 0

    async def get_all_tags(self) -> List[str]:
        db = await self._get_db()
        await self.ensure_indexes()
        tags = await db.workflows.distinct("tags")
        return sorted([tag for tag in tags if tag])

    async def record_usage(self, workflow_id: str) -> None:
        db = await self._get_db()
        await self.ensure_indexes()
        await db.workflows.update_one(
            {"_id": self._object_id(workflow_id)},
            {"$inc": {"usage_count": 1}, "$set": {"last_used_at": datetime.utcnow()}},
        )

    # ── DAG Validation ────────────────────────────────────

    async def validate_dag(self, workflow_id: str) -> Dict[str, Any]:
        """校验工作流 DAG 合法性。"""
        workflow = await self.get_workflow(workflow_id)
        if not workflow:
            raise ValueError("工作流不存在")

        nodes = workflow.get("nodes", [])
        edges = workflow.get("edges", [])
        errors: List[Dict[str, Any]] = []
        warnings: List[Dict[str, Any]] = []

        node_map = {n["id"]: n for n in nodes}
        node_ids = set(node_map.keys())

        # 检查边引用
        for edge in edges:
            if edge["source"] not in node_ids:
                errors.append({
                    "level": "error",
                    "node_id": edge["source"],
                    "message": f"边的 source '{edge['source']}' 不存在",
                    "type": "edge_invalid",
                })
            if edge["target"] not in node_ids:
                errors.append({
                    "level": "error",
                    "node_id": edge["target"],
                    "message": f"边的 target '{edge['target']}' 不存在",
                    "type": "edge_invalid",
                })

        # 检查 IO 节点
        io_nodes = [n for n in nodes if n["type"] == "io"]
        input_nodes = [
            n for n in io_nodes
            if n.get("config", {}).get("io_direction") == "input"
        ]
        output_nodes = [
            n for n in io_nodes
            if n.get("config", {}).get("io_direction") == "output"
        ]
        if len(input_nodes) == 0:
            errors.append({
                "level": "error",
                "message": "缺少输入 IO 节点",
                "type": "io_missing",
            })
        elif len(input_nodes) > 1:
            errors.append({
                "level": "error",
                "message": "只能有一个输入 IO 节点",
                "type": "io_duplicate",
            })
        if len(output_nodes) == 0:
            errors.append({
                "level": "error",
                "message": "缺少输出 IO 节点",
                "type": "io_missing",
            })
        elif len(output_nodes) > 1:
            errors.append({
                "level": "error",
                "message": "只能有一个输出 IO 节点",
                "type": "io_duplicate",
            })

        # 检测环 (DFS)
        adj: Dict[str, List[str]] = {nid: [] for nid in node_ids}
        for edge in edges:
            if edge["source"] in node_ids and edge["target"] in node_ids:
                adj[edge["source"]].append(edge["target"])

        WHITE, GRAY, BLACK = 0, 1, 2
        color = {nid: WHITE for nid in node_ids}
        has_cycle = False

        def dfs(u: str) -> None:
            nonlocal has_cycle
            color[u] = GRAY
            for v in adj[u]:
                if color[v] == GRAY:
                    has_cycle = True
                elif color[v] == WHITE:
                    dfs(v)
            color[u] = BLACK

        for nid in node_ids:
            if color[nid] == WHITE:
                dfs(nid)
        if has_cycle:
            errors.append({
                "level": "error",
                "message": "检测到环",
                "type": "cycle_detected",
            })

        # 检查孤立节点（排除 IO 节点）
        sources = {e["source"] for e in edges if e["source"] in node_ids}
        targets = {e["target"] for e in edges if e["target"] in node_ids}
        connected = sources | targets
        for nid in node_ids:
            if nid not in connected and node_map[nid]["type"] != "io":
                warnings.append({
                    "level": "warning",
                    "node_id": nid,
                    "message": f"节点 '{nid}' 未连接",
                    "type": "orphan_node",
                })

        # 检查 Agent 节点是否绑定了 agent_id
        db = await self._get_db()
        for node in nodes:
            if node["type"] == "agent":
                agent_id = node.get("config", {}).get("agent_id")
                if not agent_id:
                    errors.append({
                        "level": "error",
                        "node_id": node["id"],
                        "message": f"节点 '{node.get('label', node['id'])}' 未绑定 Agent",
                        "type": "config_missing",
                    })
                else:
                    try:
                        agent_doc = await db.agents.find_one({"_id": ObjectId(agent_id)})
                        if not agent_doc:
                            errors.append({
                                "level": "error",
                                "node_id": node["id"],
                                "message": f"引用的 Agent '{agent_id}' 不存在",
                                "type": "ref_invalid",
                            })
                        elif not agent_doc.get("enabled", True):
                            warnings.append({
                                "level": "warning",
                                "node_id": node["id"],
                                "message": f"引用的 Agent '{agent_doc.get('name', agent_id)}' 未启用",
                                "type": "ref_disabled",
                            })
                    except InvalidId:
                        errors.append({
                            "level": "error",
                            "node_id": node["id"],
                            "message": f"无效的 Agent ID: {agent_id}",
                            "type": "ref_invalid",
                        })

            elif node["type"] == "subflow":
                wf_id = node.get("config", {}).get("workflow_id")
                if not wf_id:
                    errors.append({
                        "level": "error",
                        "node_id": node["id"],
                        "message": f"节点 '{node.get('label', node['id'])}' 未绑定工作流",
                        "type": "config_missing",
                    })
                elif wf_id == workflow_id:
                    errors.append({
                        "level": "error",
                        "node_id": node["id"],
                        "message": "子工作流不能引用自身",
                        "type": "self_reference",
                    })

        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "topology": DAGResolver.topological_sort(nodes, edges),
        }


workflow_service = WorkflowService()
