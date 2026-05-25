"""
工作流状态工具函数 — 纯函数，无状态
替代原 ExecutionContext，所有操作基于 WorkflowState dict
"""
import re
from typing import Any, Dict, List

VAR_PATTERN = re.compile(r"\{\{(\w[\w.]*)\}\}")


def extract_template_vars(template: str) -> List[str]:
    """提取模板中的变量名列表，如 {{stock}} -> ["stock"]"""
    matches = VAR_PATTERN.findall(template)
    return list(dict.fromkeys(matches))


def resolve_value(state: Dict[str, Any], path: str) -> Any:
    """
    从 state 中解析变量路径。

    支持路径:
      {{input.stock}}    -> state["params"]["stock"]
      {{node_id.output}} -> state["node_outputs"]["node_id"]["output"]
      {{item.name}}      -> state["_loop_item"]["name"]  (循环内)
    """
    parts = path.split(".")
    if not parts:
        return None

    root = parts[0]

    if root == "input" and len(parts) > 1:
        return _navigate(state.get("params", {}), parts[1:])

    if root == "item" and "_loop_item" in state:
        return _navigate(state["_loop_item"], parts[1:])

    node_out = state.get("node_outputs", {}).get(root)
    if node_out is not None:
        if len(parts) == 1:
            return node_out
        return _navigate(node_out, parts[1:])

    return None


def resolve_mapping(state: Dict[str, Any], mapping: Dict[str, str]) -> Dict[str, Any]:
    """解析 input_mapping 配置。"""
    resolved: Dict[str, Any] = {}
    for key, template in mapping.items():
        match = VAR_PATTERN.fullmatch(template.strip())
        if match:
            resolved[key] = resolve_value(state, match.group(1))
        else:
            resolved[key] = render_template(state, template)
    return resolved


def render_template(state: Dict[str, Any], template: str) -> str:
    """渲染模板字符串，替换 {{...}} 为 state 中的实际值。"""
    def replacer(match: re.Match) -> str:
        value = resolve_value(state, match.group(1))
        return str(value) if value is not None else match.group(0)
    return VAR_PATTERN.sub(replacer, template)


def _navigate(obj: Any, parts: List[str]) -> Any:
    """在嵌套 dict/list 中按路径导航。"""
    current = obj
    for part in parts:
        if isinstance(current, dict):
            current = current.get(part)
        elif isinstance(current, (list, tuple)):
            try:
                current = current[int(part)]
            except (ValueError, IndexError):
                return None
        else:
            return None
        if current is None:
            return None
    return current
