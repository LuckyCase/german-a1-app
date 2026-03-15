"""
Add ui_language column to users table for interface localization.
"""


async def upgrade(conn) -> None:
    await conn.execute(
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS ui_language TEXT DEFAULT 'ru'"
    )
