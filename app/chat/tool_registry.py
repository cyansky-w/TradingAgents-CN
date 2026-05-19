"""
Extensible tool registry for AI chat.

Tools follow the LangChain BaseTool pattern (reference: chatbot project agent/tools/).
The registry is initially empty — project functions (stock analysis, screening, etc.)
will be wrapped as tools and registered here in future sprints.

Future tool wrapping pattern:
    from langchain.tools import BaseTool
    from pydantic import BaseModel, Field

    class MyArgs(BaseModel):
        param: str = Field(description="Parameter description")

    class MyTool(BaseTool):
        name = "my_tool"
        description = "What this tool does"
        args_schema = MyArgs

        def _run(self, param: str) -> str: ...
        async def _arun(self, param: str) -> str: ...

    tool_registry.register(MyTool(), category="stock_analysis")
"""

from typing import Dict, List, Optional

from langchain_core.tools import BaseTool


class ToolRegistry:
    """Central registry for chat tools. Thread-safe, singleton."""

    def __init__(self):
        self._tools: Dict[str, BaseTool] = {}
        self._categories: Dict[str, List[str]] = {}

    def register(self, tool: BaseTool, category: str = "general") -> None:
        """Register a LangChain BaseTool."""
        self._tools[tool.name] = tool
        if category not in self._categories:
            self._categories[category] = []
        if tool.name not in self._categories[category]:
            self._categories[category].append(tool.name)

    def unregister(self, name: str) -> None:
        """Remove a tool by name."""
        self._tools.pop(name, None)
        for cat_tools in self._categories.values():
            if name in cat_tools:
                cat_tools.remove(name)

    def get(self, name: str) -> Optional[BaseTool]:
        return self._tools.get(name)

    def get_all(self) -> List[BaseTool]:
        return list(self._tools.values())

    def get_by_category(self, category: str) -> List[BaseTool]:
        names = self._categories.get(category, [])
        return [self._tools[n] for n in names if n in self._tools]

    def list_tools(self) -> List[dict]:
        """Return tool metadata for API responses."""
        return [
            {
                "name": t.name,
                "description": t.description,
                "category": next(
                    (c for c, names in self._categories.items() if t.name in names),
                    "general",
                ),
            }
            for t in self._tools.values()
        ]

    @property
    def empty(self) -> bool:
        return len(self._tools) == 0


# Module-level singleton
tool_registry = ToolRegistry()
