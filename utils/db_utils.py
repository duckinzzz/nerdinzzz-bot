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
    """A single chat message."""
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
    await init_user_table()

    logger.info("Database initialized")


async def init_message_history_table() -> None:
    """Create the message history table."""
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

        # Prevent duplicate (chat_id, message_id) rows
        await conn.execute("""
                           CREATE UNIQUE INDEX IF NOT EXISTS uq_message_history_chat_message
                               ON message_history(chat_id, message_id);
                           """)

        # Speed up per-chat lookups
        await conn.execute("""
                           CREATE INDEX IF NOT EXISTS idx_message_history_chat_timestamp
                               ON message_history(chat_id, timestamp DESC);
                           """)


async def init_user_table() -> None:
    """Create the users table (normalized user data)."""
    async with pool.acquire() as conn:
        await conn.execute("""
                           CREATE TABLE IF NOT EXISTS users
                           (
                               user_id
                               BIGINT
                               PRIMARY
                               KEY,
                               username
                               TEXT,
                               first_name
                               TEXT
                           );
                           """)


async def init_chat_context_table() -> None:
    """Create the LLM dialog context table."""
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
    """Save a message, upserting its user into the users table."""
    async with pool.acquire() as conn:
        async with conn.transaction():
            if user_id:
                await conn.execute("""
                                   INSERT INTO users (user_id, username, first_name)
                                   VALUES ($1, $2, $3)
                                   ON CONFLICT (user_id) DO UPDATE SET
                                       username = COALESCE(EXCLUDED.username, users.username),
                                       first_name = COALESCE(EXCLUDED.first_name, users.first_name)
                                   """, user_id, username, first_name)

            await conn.execute("""
                               INSERT INTO message_history (chat_id, message_id, user_id, text)
                               VALUES ($1, $2, $3, $4) ON CONFLICT (chat_id, message_id) DO NOTHING
                               """, chat_id, message_id, user_id, text)


async def get_last_messages(
        chat_id: int,
        limit: int = MESSAGE_HISTORY_LIMIT
) -> List[MessageRecord]:
    """Return the last N messages from a chat, in chronological order."""
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
                                SELECT m.message_id, m.user_id,
                                       u.username, u.first_name,
                                       m.text, m.timestamp
                                FROM message_history m
                                LEFT JOIN users u ON u.user_id = m.user_id
                                WHERE m.chat_id = $1
                                ORDER BY m.timestamp DESC, m.id DESC
                                    LIMIT $2
                                """, chat_id, limit)

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
    """Delete old messages, keeping only the last N."""
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
    """Trim history in every chat, keeping the last N messages each."""
    async with pool.acquire() as conn:
        chat_ids = await conn.fetch("SELECT DISTINCT chat_id FROM message_history")

        results = {}
        for row in chat_ids:
            chat_id = row["chat_id"]
            deleted = await cleanup_old_messages(chat_id, keep_last)
            results[chat_id] = deleted

        return results


async def save_context_message(chat_id: int, role: str, content: str) -> None:
    """Save a message to the LLM dialog context (role: user | assistant)."""
    async with pool.acquire() as conn:
        await conn.execute("""
                           INSERT INTO chat_context (chat_id, role, content)
                           VALUES ($1, $2, $3)
                           """, chat_id, role, content)


async def get_context_messages(chat_id: int) -> List[dict]:
    """Return the chat's context messages in chronological order."""
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
                                SELECT role, content
                                FROM chat_context
                                WHERE chat_id = $1
                                ORDER BY ts ASC, id ASC
                                """, chat_id)
        return [{"role": row["role"], "content": row["content"]} for row in rows]


async def trim_context(chat_id: int, keep_users: int = 20) -> None:
    """Keep the last keep_users user messages plus all following bot replies."""
    async with pool.acquire() as conn:
        # Find the first message of the last keep_users user messages
        row = await conn.fetchrow("""
                                  SELECT id
                                  FROM chat_context
                                  WHERE chat_id = $1 AND role = 'user'
                                  ORDER BY ts DESC, id DESC
                                  LIMIT 1 OFFSET $2
                                  """, chat_id, max(keep_users - 1, 0))
        if row is None:
            return

        cut_id = row["id"]
        await conn.execute("""
                           DELETE FROM chat_context
                           WHERE chat_id = $1 AND id < $2
                           """, chat_id, cut_id)


async def clear_context(chat_id: int) -> None:
    """Clear the chat's LLM context."""
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM chat_context WHERE chat_id = $1", chat_id)


async def close_db() -> None:
    """Close the connection pool on bot shutdown."""
    global pool
    if pool:
        await pool.close()
        logger.info("Database pool closed")
