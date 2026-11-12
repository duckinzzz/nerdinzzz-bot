"""Web search tool — DeepSeek Search API."""

from __future__ import annotations

import aiohttp

from core.config import LLM_TOKEN
from utils.logging_utils import logger

from .base import Tool

_SEARCH_URL = "https://api.deepseek.com/v1/tools/search"
_MAX_RESULTS = 5
# The API rejects queries longer than this
_QUERY_LIMIT = 128
# `summary` comes back as whole page text, not the short blurb the docs promise.
# Trim it so five results cannot flood the model's context.
_SUMMARY_LIMIT = 300
_TIMEOUT = aiohttp.ClientTimeout(total=20)

# Phrased so the model stops retrying instead of re-running the search forever
_NO_RESULTS = (
    "По запросу «{query}» ничего не найдено. "
    "Не повторяй поиск с другой формулировкой — сообщи пользователю, что данных нет."
)


def _squash(text: str) -> str:
    """Collapse page markup/newlines into one short line for the model."""
    text = " ".join(text.split())
    if len(text) > _SUMMARY_LIMIT:
        text = text[:_SUMMARY_LIMIT].rstrip() + "…"
    return text


async def web_search(query: str) -> str:
    """Search the web through the DeepSeek Search API and format the results."""
    query = query.strip()[:_QUERY_LIMIT]
    if not query:
        return _NO_RESULTS.format(query=query)

    payload = {"query": query, "count": _MAX_RESULTS}
    headers = {"Authorization": f"Bearer {LLM_TOKEN}"}

    try:
        async with aiohttp.ClientSession(timeout=_TIMEOUT) as session:
            async with session.post(_SEARCH_URL, json=payload, headers=headers) as resp:
                if resp.status != 200:
                    body = (await resp.text())[:300]
                    logger.warning(
                        "Web search failed for '%s': HTTP %s %s", query, resp.status, body
                    )
                    return f"❌ Не удалось выполнить поиск: HTTP {resp.status}"
                data: dict = await resp.json()
    except Exception as e:
        logger.warning("Web search failed for '%s': %s", query, e)
        return f"❌ Не удалось выполнить поиск: {e}"

    results = data.get("results") or []
    if not results:
        return _NO_RESULTS.format(query=query)

    lines = [f"🔍 Результаты поиска: **{query}**\n"]
    for i, r in enumerate(results[:_MAX_RESULTS], 1):
        title = r.get("title") or "Без названия"
        text = _squash(r.get("summary") or r.get("snippet") or "")
        url = r.get("url") or ""
        lines.append(f"{i}. **{title}**\n   {text}\n   {url}\n")

    return "\n".join(lines)


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
