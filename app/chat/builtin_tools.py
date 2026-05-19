"""
Built-in chat tools for the AI assistant.

These tools demonstrate the tool-calling capability and provide
basic utility functions. Platform-specific tools (stock analysis,
screening, etc.) will be added in future sprints.
"""

import math
import operator
from datetime import datetime, timezone

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from app.chat.tool_registry import ToolRegistry


class CalculatorInput(BaseModel):
    expression: str = Field(description="A math expression to evaluate, e.g. '2 + 3 * 4' or 'sqrt(16)'")


class TimezoneInput(BaseModel):
    timezone_offset: str = Field(
        default="UTC",
        description="Timezone offset or name, e.g. 'UTC', 'Asia/Shanghai', 'US/Eastern'",
    )


def register_builtin_tools(registry: ToolRegistry) -> None:
    """Register all built-in chat tools."""

    @tool(args_schema=CalculatorInput)
    async def calculator(expression: str) -> str:
        """Evaluate a mathematical expression.

        Supports: +, -, *, /, **, %, sqrt(), sin(), cos(), tan(), log(), abs(), pi, e

        Use this tool when the user asks a math question or needs a calculation.
        """
        allowed = {
            "sqrt": math.sqrt,
            "sin": math.sin,
            "cos": math.cos,
            "tan": math.tan,
            "log": math.log,
            "abs": abs,
            "pi": math.pi,
            "e": math.e,
            "pow": pow,
        }
        allowed.update({op: getattr(operator, op) for op in ("add", "sub", "mul", "truediv", "mod", "neg")})

        try:
            compiled = compile(expression.strip(), "<calculator>", "eval")
            for name in compiled.co_names:
                if name not in allowed and name not in ("__builtins__",):
                    return f"Error: '{name}' is not allowed in calculator expressions"
            result = eval(compiled, {"__builtins__": {}}, allowed)
            return f"Result: {result}"
        except Exception as e:
            return f"Calculation error: {e}"

    @tool(args_schema=TimezoneInput)
    async def get_current_time(timezone_offset: str = "UTC") -> str:
        """Get the current date and time.

        Use this tool when the user asks about the current time, date, or day.
        """
        now_utc = datetime.now(timezone.utc)
        tz_name = timezone_offset or "UTC"

        try:
            from zoneinfo import ZoneInfo
            tz = ZoneInfo(tz_name)
            local = now_utc.astimezone(tz)
            return f"Current time in {tz_name}: {local.strftime('%Y-%m-%d %H:%M:%S %Z')}"
        except Exception:
            return f"Current time (UTC): {now_utc.strftime('%Y-%m-%d %H:%M:%S UTC')}"

    registry.register(calculator, category="utility")
    registry.register(get_current_time, category="utility")
