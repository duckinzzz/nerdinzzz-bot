from typing import Dict, Optional

import asyncpg
from asyncpg.pool import Pool

from core.config import DATABASE_URL
from core.constants import LLM_MODELS, DEFAULT_LLM

pool: Pool
chat_settings_cache: Dict[int, str] = {}


async def init_db() -> None:
    """
    Initialize database connection, create tables if they do not exist,
    seed reference data, and load chat settings into memory.
    Called once on bot startup.
    """
    global pool

    pool = await asyncpg.create_pool(DATABASE_URL)  # type: ignore

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

    await seed_llm_models()
    await load_chat_settings()


async def seed_llm_models() -> None:
    """
    Insert LLM models into the database.
    """
    async with pool.acquire() as conn:
        for code, data in LLM_MODELS.items():
            await conn.execute("""
                INSERT INTO llm_models (code, name)
                VALUES ($1, $2)
                ON CONFLICT (code) DO NOTHING
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

    llm_code = row["code"]
    await set_chat_llm(chat_id, llm_code)
    return llm_code


async def set_chat_llm(chat_id: int, llm_code: str) -> None:
    """
    Set or update LLM for a chat using llm_code.
    llm_id is resolved internally.
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
