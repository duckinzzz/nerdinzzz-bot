"""Tool registry — register tools once, get OpenAI-compatible definitions automatically.

Usage:
    from utils.tools import registry
    from utils.tools.weather import weather_tool

    registry.register(weather_tool)

    # In LLM call:
    tools = registry.get_openai_definitions()
    completion = await client.chat.completions.create(
        model=...,
        messages=...,
        tools=tools,
    )
    # If tool_calls in response:
    results = await registry.execute(response)
    # Feed results back to LLM as tool messages...
"""

from __future__ import annotations

import json
from typing import Any

from openai.types.chat import (
    ChatCompletionMessage,
    ChatCompletionMessageToolCall,
)

from utils.logging_utils import logger

from .base import Tool


class ToolRegistry:
    """Holds registered tools and provides OpenAI-compatible definitions."""

    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    # ── Registration ────────────────────────────────────────────────

    def register(self, tool: Tool) -> None:
        if tool.name in self._tools:
            raise ValueError(f"Tool '{tool.name}' is already registered")
        self._tools[tool.name] = tool
        tool._registered = True
        logger.debug(f"Tool registered: {tool.name}")

    # ── OpenAI-compatible definitions ───────────────────────────────

    def get_openai_definitions(self) -> list[dict[str, Any]]:
        """Return tool definitions in OpenAI function-calling format."""
        return [
            {
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description,
                    "parameters": t.parameters,
                },
            }
            for t in self._tools.values()
        ]

    # ── Execution ───────────────────────────────────────────────────

    async def execute(self, tool_calls: list[ChatCompletionMessageToolCall]) -> list[dict[str, Any]]:
        """Execute tool calls from an LLM response.

        Returns a list of {"role": "tool", "tool_call_id": ..., "content": ...}
        ready to append to the messages list.
        """
        results: list[dict[str, Any]] = []

        for tc in tool_calls:
            tool = self._tools.get(tc.function.name)
            if tool is None:
                logger.warning(f"LLM requested unknown tool: {tc.function.name}")
                content = f"Error: unknown tool '{tc.function.name}'"
            else:
                try:
                    args = json.loads(tc.function.arguments)
                except json.JSONDecodeError:
                    args = {}
                try:
                    content = await tool.execute(**args)
                    logger.info(f"Tool '{tc.function.name}' executed successfully")
                except Exception as e:
                    logger.warning(f"Tool '{tc.function.name}' failed: {e}")
                    content = f"Error executing {tc.function.name}: {e}"

            results.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": content,
            })

        return results

    def has_tools(self) -> bool:
        return len(self._tools) > 0

    @property
    def count(self) -> int:
        return len(self._tools)


# ── Singleton ──────────────────────────────────────────────────────────
_registry: ToolRegistry | None = None


def get_tool_registry() -> ToolRegistry:
    """Return the global tool registry singleton, creating it if needed."""
    global _registry
    if _registry is None:
        _registry = ToolRegistry()
    return _registry


def init_tools() -> ToolRegistry:
    """Register all available tools and return the registry.

    Called once at bot startup. Add new tools here.
    """
    registry = get_tool_registry()

    # ── Import and register each tool ──────────────────────────────
    from utils.tools.search import search_tool  # noqa: E402
    from utils.tools.weather import weather_tool  # noqa: E402

    registry.register(search_tool)
    registry.register(weather_tool)

    logger.info(f"Tools initialized: {registry.count} registered")
    return registry
