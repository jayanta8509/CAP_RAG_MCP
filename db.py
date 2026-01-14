import os
import asyncpg
from dotenv import load_dotenv
from typing import Any, Dict, List, Optional, Sequence

load_dotenv()

_POOL: Optional[asyncpg.Pool] = None


def _env_bool(name: str, default: bool = False) -> bool:
    v = os.getenv(name)
    if v is None:
        return default
    return v.strip().lower() in ("1", "true", "yes", "y", "on")


def build_dsn() -> str:
    host = os.getenv("PG_HOST", "127.0.0.1")
    port = int(os.getenv("PG_PORT", "5432"))
    db = os.getenv("PG_DATABASE", "")
    user = os.getenv("PG_USER", "")
    pw = os.getenv("PG_PASSWORD", "")
    return f"postgresql://{user}:{pw}@{host}:{port}/{db}"


async def init_pool() -> asyncpg.Pool:
    global _POOL
    if _POOL is not None:
        return _POOL

    dsn = build_dsn()
    min_size = int(os.getenv("PG_POOL_MIN", "1"))
    max_size = int(os.getenv("PG_POOL_MAX", "10"))
    ssl_required = _env_bool("PG_SSL", False)

    _POOL = await asyncpg.create_pool(
        dsn=dsn,
        min_size=min_size,
        max_size=max_size,
        ssl="require" if ssl_required else None,
        command_timeout=30,
    )
    return _POOL


async def close_pool():
    global _POOL
    if _POOL is not None:
        await _POOL.close()
        _POOL = None


async def fetch_one(query: str, *args) -> Optional[Dict[str, Any]]:
    pool = await init_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(query, *args)
        return dict(row) if row else None


async def fetch_all(query: str, *args) -> List[Dict[str, Any]]:
    pool = await init_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(query, *args)
        return [dict(r) for r in rows]


async def execute(query: str, *args) -> str:
    pool = await init_pool()
    async with pool.acquire() as conn:
        return await conn.execute(query, *args)


def build_ilike_pattern(q: str) -> str:
    return f"%{q.strip()}%"
