"""Web search tool — DuckDuckGo (free, no API key)."""

from __future__ import annotations

import asyncio

from ddgs import DDGS

from utils.logging_utils import logger

from .base import Tool

_MAX_RESULTS = 5


async def web_search(query: str) -> str:
    """Search the web and return formatted results."""
    try:
        # DDGS is synchronous — run in thread to avoid blocking the event loop
        results = await asyncio.to_thread(
            _sync_search, query, _MAX_RESULTS
        )

        if not results:
            return f"По запросу «{query}» ничего не найдено."

        lines = [f"🔍 Результаты поиска: **{query}**\n"]
        for i, r in enumerate(results, 1):
            title = r.get("title", "Без названия")
            href = r.get("href", "")
            body = r.get("body", "")[:200]
            lines.append(f"{i}. **{title}**\n   {body}\n   {href}\n")

        return "\n".join(lines)

    except Exception as e:
        logger.warning("Web search failed for '%s': %s", query, e)
        return f"❌ Не удалось выполнить поиск: {e}"


def _sync_search(query: str, max_results: int) -> list[dict]:
    """Synchronous DuckDuckGo search — runs in a thread."""
    with DDGS() as ddgs:
        return list(ddgs.text(query, max_results=max_results))


search_tool = Tool(
    name="web_search",
    description=(
        "Search the web for current information. "
        "Call this when the user asks about prices, news, facts, events, "
        "or anything that requires up-to-date or real-world data."
    ),
    parameters={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search query (e.g. 'iPhone Air price Russia 2026')",
            },
        },
        "required": ["query"],
    },
    execute=web_search,
)
