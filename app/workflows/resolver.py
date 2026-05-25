"""
DAG 拓扑排序与校验
"""
from typing import Any, Dict, List, Tuple


class DAGResolver:
    """解析 nodes+edges，校验合法性，输出拓扑执行层级。"""

    @staticmethod
    def validate(nodes: List[Dict[str, Any]], edges: List[Dict[str, Any]]) -> List[str]:
        """校验 DAG 合法性，返回错误列表。"""
        errors: List[str] = []
        node_ids = {n["id"] for n in nodes}

        # 边引用检查
        for edge in edges:
            if edge["source"] not in node_ids:
                errors.append(f"边的 source '{edge['source']}' 不存在")
            if edge["target"] not in node_ids:
                errors.append(f"边的 target '{edge['target']}' 不存在")

        # IO 节点检查
        io_nodes = [n for n in nodes if n["type"] == "io"]
        input_nodes = [n for n in io_nodes if n.get("config", {}).get("io_direction") == "input"]
        output_nodes = [n for n in io_nodes if n.get("config", {}).get("io_direction") == "output"]
        if len(input_nodes) == 0:
            errors.append("缺少输入 IO 节点")
        elif len(input_nodes) > 1:
            errors.append("只能有一个输入 IO 节点")
        if len(output_nodes) == 0:
            errors.append("缺少输出 IO 节点")
        elif len(output_nodes) > 1:
            errors.append("只能有一个输出 IO 节点")

        # 环检测 (DFS)
        adj: Dict[str, List[str]] = {n["id"]: [] for n in nodes}
        valid_edges = [
            e for e in edges
            if e["source"] in node_ids and e["target"] in node_ids
        ]
        for edge in valid_edges:
            adj[edge["source"]].append(edge["target"])

        WHITE, GRAY, BLACK = 0, 1, 2
        color = {nid: WHITE for nid in node_ids}
        cycle_path: List[str] = []

        def dfs(u: str, path: List[str]) -> bool:
            color[u] = GRAY
            path.append(u)
            for v in adj[u]:
                if color[v] == GRAY:
                    cycle_start = path.index(v)
                    cycle_path.extend(path[cycle_start:] + [v])
                    return True
                if color[v] == WHITE and dfs(v, path):
                    return True
            path.pop()
            color[u] = BLACK
            return False

        for nid in node_ids:
            if color[nid] == WHITE:
                if dfs(nid, []):
                    errors.append(f"检测到环: {' -> '.join(cycle_path)}")
                    break

        # 孤立节点
        sources = {e["source"] for e in valid_edges}
        targets = {e["target"] for e in valid_edges}
        connected = sources | targets
        for n in nodes:
            if n["id"] not in connected and n["type"] != "io":
                errors.append(f"孤立节点 '{n.get('label', n['id'])}' 未连接")

        return errors

    @staticmethod
    def topological_sort(
        nodes: List[Dict[str, Any]], edges: List[Dict[str, Any]]
    ) -> List[List[str]]:
        """返回分层执行计划（同一层内可并行）。"""
        node_ids = {n["id"] for n in nodes}
        in_degree: Dict[str, int] = {nid: 0 for nid in node_ids}
        adj: Dict[str, List[str]] = {nid: [] for nid in node_ids}

        for edge in edges:
            if edge["source"] in node_ids and edge["target"] in node_ids:
                adj[edge["source"]].append(edge["target"])
                in_degree[edge["target"]] += 1

        layers: List[List[str]] = []
        remaining = set(node_ids)

        while remaining:
            layer = [nid for nid in remaining if in_degree[nid] == 0]
            if not layer:
                break
            layers.append(sorted(layer))
            for nid in layer:
                remaining.remove(nid)
                for neighbor in adj[nid]:
                    in_degree[neighbor] -= 1

        return layers

    @staticmethod
    def find_entry_node(nodes: List[Dict[str, Any]]) -> str:
        """找到 io_direction=input 的节点。"""
        for n in nodes:
            if n["type"] == "io" and n.get("config", {}).get("io_direction") == "input":
                return n["id"]
        raise ValueError("未找到输入 IO 节点")

    @staticmethod
    def find_exit_node(nodes: List[Dict[str, Any]]) -> str:
        """找到 io_direction=output 的节点。"""
        for n in nodes:
            if n["type"] == "io" and n.get("config", {}).get("io_direction") == "output":
                return n["id"]
        raise ValueError("未找到输出 IO 节点")
