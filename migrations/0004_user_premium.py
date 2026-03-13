"""
Add is_premium column to users table for tiered pronunciation STT.
"""


async def upgrade(conn) -> None:
    await conn.execute(
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS is_premium INTEGER DEFAULT 0"
    )
