"""Text helpers shared across handlers."""

from __future__ import annotations

from typing import Any


def split_long_text(text: str, limit: int) -> list[str]:
    """Split text into chunks of at most `limit` characters.

    Prefers paragraph breaks, then line breaks, then spaces, so the result
    stays readable. Falls back to a hard cut when a single word is longer
    than the limit on its own.

    Args:
        text: Text to split.
        limit: Maximum length of a single chunk.

    Returns:
        Chunks in their original order. A text that already fits comes back
        as a single-element list. Whitespace at the split points is dropped.
    """
    return [text[start:end] for start, end in _split_spans(text, limit)]


def split_message_with_entities(
        text: str,
        entities: list[Any],
        limit: int,
) -> list[tuple[str, list[dict]]]:
    """Split an already-formatted message, keeping entities that fit.

    Telegram rejects messages longer than 4096 characters, so long replies
    are cut into several messages. Message entities (bold, links, ...) use
    UTF-16 offsets that are relative to the whole text, so they have to be
    dropped or rebased for every chunk.

    Args:
        text: Plain text of the message.
        entities: Objects with a ``to_dict()`` returning Telegram entity
            dicts (``offset``/``length`` in UTF-16 code units).
        limit: Maximum length of a single chunk.

    Returns:
        ``(chunk_text, chunk_entities)`` pairs. Entities that span a chunk
        boundary are dropped, since they cannot be represented in either
        chunk on their own.
    """
    spans = _split_spans(text, limit)
    if len(spans) == 1:
        return [(text, [e.to_dict() for e in entities])]

    entity_dicts = [e.to_dict() for e in entities]
    chunks: list[tuple[str, list[dict]]] = []

    for start, end in spans:
        chunk = text[start:end]
        chunk_start = _utf16_len(text[:start])
        chunk_end = chunk_start + _utf16_len(chunk)

        kept: list[dict] = []
        for entity in entity_dicts:
            entity_start = entity["offset"]
            entity_end = entity_start + entity["length"]
            if entity_start >= chunk_start and entity_end <= chunk_end:
                rebased = dict(entity)
                rebased["offset"] = entity_start - chunk_start
                kept.append(rebased)

        chunks.append((chunk, kept))

    return chunks


def _split_spans(text: str, limit: int) -> list[tuple[int, int]]:
    """Return (start, end) index pairs for chunks of at most `limit` chars.

    Indices refer to the original string and already exclude the whitespace
    consumed at the split points, so ``text[start:end]`` is the chunk itself.
    """
    if limit <= 0:
        raise ValueError("limit must be positive")
    if len(text) <= limit:
        return [(0, len(text))]

    spans: list[tuple[int, int]] = []
    position = 0

    while len(text) - position > limit:
        window = text[position:position + limit]
        cut = window.rfind("\n\n")
        if cut < limit // 2:
            cut = window.rfind("\n")
        if cut < limit // 2:
            cut = window.rfind(" ")
        if cut <= 0:
            cut = limit

        start, end = position, position + cut
        while start < end and text[start].isspace():
            start += 1
        while end > start and text[end - 1].isspace():
            end -= 1
        if start < end:
            spans.append((start, end))

        position += cut

    start, end = position, len(text)
    while start < end and text[start].isspace():
        start += 1
    while end > start and text[end - 1].isspace():
        end -= 1
    if start < end:
        spans.append((start, end))

    return spans


def _utf16_len(text: str) -> int:
    """Length of `text` in UTF-16 code units — what Telegram counts."""
    return sum(2 if ord(char) > 0xFFFF else 1 for char in text)
