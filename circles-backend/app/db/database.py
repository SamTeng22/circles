import json
import asyncpg
from app.core.config import settings

_pool = None

async def _init_connection(conn):
    # Auto encode/decode JSONB columns as Python objects (lists/dicts) instead
    # of raw JSON strings.
    await conn.set_type_codec(
        "jsonb",
        encoder=json.dumps,
        decoder=json.loads,
        schema="pg_catalog",
    )

async def get_pool():
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(settings.DATABASE_URL, init=_init_connection)
    return _pool

async def init_db():
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                firebase_uid TEXT UNIQUE NOT NULL,
                email TEXT UNIQUE NOT NULL,
                display_name TEXT,
                created_at TIMESTAMPTZ DEFAULT now()
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS circles (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                name TEXT NOT NULL,
                description TEXT,
                invite_code TEXT UNIQUE NOT NULL,
                owner_id UUID REFERENCES users(id) ON DELETE CASCADE,
                created_at TIMESTAMPTZ DEFAULT now()
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS circle_members (
                circle_id UUID REFERENCES circles(id) ON DELETE CASCADE,
                user_id UUID REFERENCES users(id) ON DELETE CASCADE,
                joined_at TIMESTAMPTZ DEFAULT now(),
                PRIMARY KEY (circle_id, user_id)
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS notes (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                circle_id UUID REFERENCES circles(id) ON DELETE CASCADE,
                user_id UUID REFERENCES users(id) ON DELETE CASCADE,
                filename TEXT NOT NULL,
                content TEXT,
                s3_key TEXT,
                content_type TEXT,
                size_bytes BIGINT,
                status TEXT DEFAULT 'ready',
                error TEXT,
                created_at TIMESTAMPTZ DEFAULT now(),
                edited_at TIMESTAMPTZ
            )
        """)
        # Migration for existing databases created before edited_at existed.
        await conn.execute(
            "ALTER TABLE notes ADD COLUMN IF NOT EXISTS edited_at TIMESTAMPTZ"
        )
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS note_chunks (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                note_id UUID REFERENCES notes(id) ON DELETE CASCADE,
                circle_id UUID REFERENCES circles(id) ON DELETE CASCADE,
                user_id UUID REFERENCES users(id) ON DELETE CASCADE,
                content TEXT NOT NULL,
                embedding vector(768),
                created_at TIMESTAMPTZ DEFAULT now()
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS conflicts (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                circle_id UUID REFERENCES circles(id) ON DELETE CASCADE,
                chunk_a_id UUID REFERENCES note_chunks(id) ON DELETE CASCADE,
                chunk_b_id UUID REFERENCES note_chunks(id) ON DELETE CASCADE,
                explanation TEXT NOT NULL,
                resolved BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMPTZ DEFAULT now()
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS quizzes (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                circle_id UUID REFERENCES circles(id) ON DELETE CASCADE,
                created_by UUID REFERENCES users(id),
                title TEXT NOT NULL,
                questions JSONB NOT NULL,
                created_at TIMESTAMPTZ DEFAULT now()
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS quiz_scores (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                quiz_id UUID REFERENCES quizzes(id) ON DELETE CASCADE,
                user_id UUID REFERENCES users(id) ON DELETE CASCADE,
                score INTEGER NOT NULL,
                answers JSONB,
                completed_at TIMESTAMPTZ DEFAULT now()
            )
        """)
    print("Database initialized")
