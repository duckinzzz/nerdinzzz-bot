from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional

import asyncpg
from asyncpg.pool import Pool

from core.config import DATABASE_URL
from core.constants import MESSAGE_HISTORY_LIMIT
from utils.logging_utils import logger

pool: Pool


@dataclass
class MessageRecord:
    """Запись сообщения в истории"""
    message_id: int
    user_id: int
    username: Optional[str]
    first_name: Optional[str]
    text: str
    timestamp: datetime


async def init_db() -> None:
    """
    Initialize database connection, create tables if they do not exist.
    Called once on bot startup.
    """
    global pool

    pool = await asyncpg.create_pool(  # type: ignore
        DATABASE_URL,
        min_size=2,
        max_size=10,
        command_timeout=60
    )

    await init_message_history_table()
    await init_chat_context_table()

    logger.info("Database initialized")


async def init_message_history_table() -> None:
    """Создать таблицу для истории сообщений"""
    async with pool.acquire() as conn:
        await conn.execute("""
                           CREATE TABLE IF NOT EXISTS message_history
                           (
                               id
                               SERIAL
                               PRIMARY
                               KEY,
                               chat_id
                               BIGINT
                               NOT
                               NULL,
                               message_id
                               BIGINT
                               NOT
                               NULL,
                               user_id
                               BIGINT
                               NOT
                               NULL,
                               username
                               TEXT,
                               first_name
                               TEXT,
                               text
                               TEXT
                               NOT
                               NULL,
                               timestamp
                               TIMESTAMPTZ
                               DEFAULT
                               CURRENT_TIMESTAMP
                           );
                           """)

        # Миграция для уже существующих БД
        await conn.execute("""
                           ALTER TABLE message_history
                               ADD COLUMN IF NOT EXISTS first_name TEXT;
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


async def init_chat_context_table() -> None:
    """Создать таблицу для контекста LLM-диалога"""
    async with pool.acquire() as conn:
        await conn.execute("""
                           CREATE TABLE IF NOT EXISTS chat_context
                           (
                               id
                               SERIAL
                               PRIMARY
                               KEY,
                               chat_id
                               BIGINT
                               NOT
                               NULL,
                               role
                               TEXT
                               NOT
                               NULL,
                               content
                               TEXT
                               NOT
                               NULL,
                               ts
                               TIMESTAMPTZ
                               DEFAULT
                               CURRENT_TIMESTAMP
                           );
                           """)

        await conn.execute("""
                           CREATE INDEX IF NOT EXISTS idx_chat_context_chat_ts
                               ON chat_context(chat_id, ts);
                           """)


async def save_message(
        chat_id: int,
        message_id: int,
        user_id: int,
        username: Optional[str],
        first_name: Optional[str],
        text: str
) -> None:
    """Сохранить сообщение в БД (с защитой от дубликатов)"""
    async with pool.acquire() as conn:
        await conn.execute("""
                           INSERT INTO message_history (chat_id, message_id, user_id, username, first_name, text)
                           VALUES ($1, $2, $3, $4, $5, $6) ON CONFLICT (chat_id, message_id) DO NOTHING
                           """, chat_id, message_id, user_id, username, first_name, text)


async def get_last_messages(
        chat_id: int,
        limit: int = MESSAGE_HISTORY_LIMIT
) -> List[MessageRecord]:
    """Получить последние N сообщений из чата"""
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
                                SELECT message_id, user_id, username, first_name, text, timestamp
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
                first_name=row["first_name"],
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
                                    DELETE
                                    FROM message_history
                                    WHERE chat_id = $1
                                      AND id NOT IN (SELECT id
                                                     FROM message_history
                                                     WHERE chat_id = $1
                                                     ORDER BY
                                        timestamp DESC
                                        , id DESC
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


async def save_context_message(chat_id: int, role: str, content: str) -> None:
    """Сохранить сообщение в контекст LLM-диалога (role: user | assistant)"""
    async with pool.acquire() as conn:
        await conn.execute("""
                           INSERT INTO chat_context (chat_id, role, content)
                           VALUES ($1, $2, $3)
                           """, chat_id, role, content)


async def get_context_messages(chat_id: int) -> List[dict]:
    """Получить сообщения контекста чата в хронологическом порядке"""
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
                                SELECT role, content
                                FROM chat_context
                                WHERE chat_id = $1
                                ORDER BY ts ASC, id ASC
                                """, chat_id)
        return [{"role": row["role"], "content": row["content"]} for row in rows]


async def trim_context(chat_id: int, keep_users: int = 20) -> None:
    """
    Обрезать контекст, оставив последние keep_users сообщений пользователя
    и все ответы бота после первого сохранённого.
    """
    async with pool.acquire() as conn:
        # Ищем id первого сообщения, с которого начинаются последние keep_users user-сообщений
        row = await conn.fetchrow("""
                                  SELECT id
                                  FROM chat_context
                                  WHERE chat_id = $1 AND role = 'user'
                                  ORDER BY ts DESC, id DESC
                                  LIMIT 1 OFFSET $2
                                  """, chat_id, max(keep_users - 1, 0))
        # Если user-сообщений меньше или равно keep_users — ничего не чистим
        if row is None:
            return

        cut_id = row["id"]
        await conn.execute("""
                           DELETE FROM chat_context
                           WHERE chat_id = $1 AND id < $2
                           """, chat_id, cut_id)


async def clear_context(chat_id: int) -> None:
    """Полностью очистить контекст чата"""
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM chat_context WHERE chat_id = $1", chat_id)


async def close_db() -> None:
    """
    Закрыть пул соединений при остановке бота
    """
    global pool
    if pool:
        await pool.close()
        logger.info("Database pool closed")
