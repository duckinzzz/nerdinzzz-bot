"""Web search tool — DuckDuckGo (free, no API key)."""

from __future__ import annotations

import asyncio
import re

from ddgs import DDGS

from utils.logging_utils import logger

from .base import Tool

_MAX_RESULTS = 5
# Shorter query words carry too little signal to judge relevance by
_MIN_TOKEN_LENGTH = 4

# Phrased so the model stops retrying instead of re-running the search forever
_NO_RESULTS = (
    "По запросу «{query}» ничего не найдено. "
    "Не повторяй поиск с другой формулировкой — сообщи пользователю, что данных нет."
)


async def web_search(query: str) -> str:
    """Search the web and return formatted results."""
    try:
        # DDGS is synchronous — run in thread to avoid blocking the event loop
        results = await asyncio.to_thread(
            _sync_search, query, _MAX_RESULTS
        )

        if not results:
            return _NO_RESULTS.format(query=query)

        relevant = [r for r in results if _is_relevant(query, r)]
        if not relevant:
            # ddgs falls back to other engines when DuckDuckGo throttles, and
            # those sometimes answer with unrelated pages. Handing that to the
            # model makes it retry the search instead of answering.
            logger.warning("Web search returned only irrelevant results for '%s'", query)
            return _NO_RESULTS.format(query=query)

        lines = [f"🔍 Результаты поиска: **{query}**\n"]
        for i, r in enumerate(relevant, 1):
            title = r.get("title", "Без названия")
            href = r.get("href", "")
            body = r.get("body", "")[:200]
            lines.append(f"{i}. **{title}**\n   {body}\n   {href}\n")

        return "\n".join(lines)

    except Exception as e:
        logger.warning("Web search failed for '%s': %s", query, e)
        return f"❌ Не удалось выполнить поиск: {e}"


def _query_tokens(query: str) -> list[str]:
    """Meaningful words of a query — used to judge result relevance."""
    return [
        word for word in re.findall(r"\w+", query.lower())
        if len(word) >= _MIN_TOKEN_LENGTH
    ]


def _is_relevant(query: str, result: dict) -> bool:
    """Whether a result shares at least one meaningful word with the query.

    Deliberately lenient: the goal is to drop pages that are obviously about
    something else, not to rank what is left.
    """
    tokens = _query_tokens(query)
    if not tokens:
        return True

    haystack = f"{result.get('title', '')} {result.get('body', '')}".lower()
    return any(token in haystack for token in tokens)


def _sync_search(query: str, max_results: int) -> list[dict]:
    """Synchronous DuckDuckGo search — runs in a thread."""
    with DDGS() as ddgs:
        return list(ddgs.text(query, max_results=max_results))


search_tool = Tool(
    name="web_search",
    description=(
        "Search the web for current information. "
        "Call this when the user asks about prices, news, facts, events, "
        "or anything that requires up-to-date or real-world data. "
        "If it reports that nothing was found, do not call it again with a "
        "reworded query — answer the user with what you have."
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
