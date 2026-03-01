"""Async database access layer.

The original project used synchronous psycopg2 calls inside async handlers,
which blocks the event loop and can cause Telegram polling to disconnect.

This module provides a small wrapper around an asyncpg connection pool.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

import asyncpg

logger = logging.getLogger(__name__)

_pool: Optional[asyncpg.Pool] = None


def is_initialized() -> bool:
    return _pool is not None


async def init_pool(
    dsn: str,
    *,
    min_size: int = 1,
    max_size: int = 10,
    command_timeout: float = 30.0,
) -> asyncpg.Pool:
    """Initialize the global pool.

    Safe to call multiple times.
    """
    global _pool
    if _pool is not None:
        return _pool

    logger.info("Initializing PostgreSQL pool")
    _pool = await asyncpg.create_pool(
        dsn=dsn,
        min_size=min_size,
        max_size=max_size,
        command_timeout=command_timeout,
    )
    return _pool


async def close_pool() -> None:
    global _pool
    if _pool is None:
        return
    logger.info("Closing PostgreSQL pool")
    await _pool.close()
    _pool = None


def _require_pool() -> asyncpg.Pool:
    if _pool is None:
        raise RuntimeError("Database pool is not initialized. Call init_pool() on startup.")
    return _pool


async def fetch(query: str, *args: Any) -> list[asyncpg.Record]:
    pool = _require_pool()
    async with pool.acquire() as conn:
        return await conn.fetch(query, *args)


async def fetchrow(query: str, *args: Any) -> Optional[asyncpg.Record]:
    pool = _require_pool()
    async with pool.acquire() as conn:
        return await conn.fetchrow(query, *args)


async def fetchval(query: str, *args: Any) -> Any:
    pool = _require_pool()
    async with pool.acquire() as conn:
        return await conn.fetchval(query, *args)


async def execute(query: str, *args: Any) -> str:
    pool = _require_pool()
    async with pool.acquire() as conn:
        return await conn.execute(query, *args)
