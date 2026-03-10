from typing import Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime

import asyncpg
from asyncpg.pool import Pool

from core.config import DATABASE_URL
from core.constants import LLM_MODELS, DEFAULT_LLM, MESSAGE_HISTORY_LIMIT
from utils.logging_utils import logger

pool: Pool
chat_settings_cache: Dict[int, str] = {}


@dataclass
class MessageRecord:
    """Запись сообщения в истории"""
    message_id: int
    user_id: int
    username: Optional[str]
    text: str
    timestamp: datetime


async def init_db() -> None:
    """
    Initialize database connection, create tables if they do not exist,
    seed reference data, and load chat settings into memory.
    Called once on bot startup.
    """
    global pool

    pool = await asyncpg.create_pool(  # type: ignore
        DATABASE_URL,
        min_size=2,
        max_size=10,
        command_timeout=60
    )

    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS llm_models (
                id SERIAL PRIMARY KEY,
                code TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL
            );
        """)

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS chat_settings (
                chat_id BIGINT PRIMARY KEY,
                llm_id INTEGER NOT NULL REFERENCES llm_models(id) ON DELETE RESTRICT
            );
        """)

        # Индекс для быстрого поиска по llm_id (если понадобится аналитика)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_chat_settings_llm_id
            ON chat_settings(llm_id);
        """)

    await init_message_history_table()
    await seed_llm_models()
    await load_chat_settings()

    logger.info(f"Database initialized. Loaded {len(chat_settings_cache)} chat settings into cache")


async def seed_llm_models() -> None:
    """
    Insert LLM models into the database.
    """
    async with pool.acquire() as conn:
        for code, data in LLM_MODELS.items():
            await conn.execute("""
                INSERT INTO llm_models (code, name)
                VALUES ($1, $2)
                ON CONFLICT (code) DO UPDATE
                SET name = EXCLUDED.name
            """, code, data["name"])


async def load_chat_settings() -> None:
    """
    Load all chat settings from the database into in-memory cache.
    Cache format: chat_id -> llm_code
    """
    chat_settings_cache.clear()

    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT cs.chat_id, lm.code
            FROM chat_settings cs
            JOIN llm_models lm ON cs.llm_id = lm.id
        """)

    for row in rows:
        chat_settings_cache[row["chat_id"]] = row["code"]


async def get_chat_llm(chat_id: int) -> str:
    """
    Get LLM code for a chat.
    1. Try in-memory cache
    2. If not found — assign default model and persist it
    """
    # Fast path: cache hit
    if chat_id in chat_settings_cache:
        return chat_settings_cache[chat_id]

    # Cache miss: fetch default model from DB
    async with pool.acquire() as conn:
        row = await conn.fetchrow("""
            SELECT id, code
            FROM llm_models
            WHERE code = $1
        """, DEFAULT_LLM)

        if row is None:
            row = await conn.fetchrow("""
                SELECT id, code
                FROM llm_models
                ORDER BY id LIMIT 1
            """)

            if row is None:
                raise RuntimeError("No LLM models available in database")

    llm_code = row["code"]
    await set_chat_llm(chat_id, llm_code)
    logger.info(f"New chat {chat_id} initialized with default LLM: {llm_code}")
    return llm_code


async def set_chat_llm(chat_id: int, llm_code: str) -> None:
    """
    Set or update LLM for a chat using llm_code.
    llm_id is resolved internally.

    Updates both database and cache for consistency.
    """
    async with pool.acquire() as conn:
        row = await conn.fetchrow("""
            SELECT id
            FROM llm_models
            WHERE code = $1
        """, llm_code)

        if row is None:
            raise ValueError(f"Unknown LLM code: {llm_code}")

        llm_id = row["id"]

        await conn.execute("""
            INSERT INTO chat_settings (chat_id, llm_id)
            VALUES ($1, $2)
            ON CONFLICT (chat_id) DO UPDATE
            SET llm_id = EXCLUDED.llm_id
        """, chat_id, llm_id)

    chat_settings_cache[chat_id] = llm_code


async def get_llm_id_by_code(code: str) -> Optional[int]:
    """
    Helper function.
    Returns llm_id for a given llm code.
    """
    async with pool.acquire() as conn:
        row = await conn.fetchrow("""
            SELECT id
            FROM llm_models
            WHERE code = $1
        """, code)

    return row["id"] if row else None


async def init_message_history_table() -> None:
    """Создать таблицу для истории сообщений"""
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS message_history (
                id SERIAL PRIMARY KEY,
                chat_id BIGINT NOT NULL,
                message_id BIGINT NOT NULL,
                user_id BIGINT NOT NULL,
                username TEXT,
                text TEXT NOT NULL,
                timestamp TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # UNIQUE индекс для защиты от дубликатов
        await conn.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS uq_message_history_chat_message
            ON message_history(chat_id, message_id);
        """)

        # Индекс для быстрого поиска по чату
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_message_history_chat_timestamp
            ON message_history(chat_id, timestamp DESC);
        """)


async def save_message(
    chat_id: int,
    message_id: int,
    user_id: int,
    username: Optional[str],
    text: str
) -> None:
    """Сохранить сообщение в БД (с защитой от дубликатов)"""
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO message_history (chat_id, message_id, user_id, username, text)
            VALUES ($1, $2, $3, $4, $5)
            ON CONFLICT (chat_id, message_id) DO NOTHING
        """, chat_id, message_id, user_id, username, text)


async def get_last_messages(
    chat_id: int,
    limit: int = MESSAGE_HISTORY_LIMIT
) -> List[MessageRecord]:
    """Получить последние N сообщений из чата"""
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT message_id, user_id, username, text, timestamp
            FROM message_history
            WHERE chat_id = $1
            ORDER BY timestamp DESC, id DESC
            LIMIT $2
        """, chat_id, limit)

        # Возвращаем в хронологическом порядке
        return [
            MessageRecord(
                message_id=row["message_id"],
                user_id=row["user_id"],
                username=row["username"],
                text=row["text"],
                timestamp=row["timestamp"]
            )
            for row in reversed(rows)
        ]


async def cleanup_old_messages(
    chat_id: int,
    keep_last: int = MESSAGE_HISTORY_LIMIT
) -> int:
    """Удалить старые сообщения, оставив только последние N"""
    async with pool.acquire() as conn:
        result = await conn.execute("""
            DELETE FROM message_history
            WHERE chat_id = $1
            AND id NOT IN (
                SELECT id FROM message_history
                WHERE chat_id = $1
                ORDER BY timestamp DESC, id DESC
                LIMIT $2
            )
        """, chat_id, keep_last)

        deleted = int(result.split()[-1]) if result else 0
        return deleted


async def cleanup_all_chats(keep_last: int = MESSAGE_HISTORY_LIMIT) -> dict:
    """Очистить все чаты, оставив последние N сообщений в каждом"""
    async with pool.acquire() as conn:
        chat_ids = await conn.fetch("SELECT DISTINCT chat_id FROM message_history")

        results = {}
        for row in chat_ids:
            chat_id = row["chat_id"]
            deleted = await cleanup_old_messages(chat_id, keep_last)
            results[chat_id] = deleted

        return results


async def close_db() -> None:
    """
    Закрыть пул соединений при остановке бота
    """
    global pool
    if pool:
        await pool.close()
        logger.info("Database pool closed")
