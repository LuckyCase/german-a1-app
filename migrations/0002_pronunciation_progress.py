"""
Add pronunciation progress table.
"""


async def upgrade(conn) -> None:
    await conn.execute(
        """
        CREATE TABLE IF NOT EXISTS pronunciation_progress (
            id SERIAL PRIMARY KEY,
            user_id BIGINT NOT NULL,
            item_type TEXT NOT NULL,
            item_id TEXT,
            target_text TEXT NOT NULL,
            recognized_text TEXT NOT NULL,
            score INTEGER NOT NULL,
            verdict TEXT NOT NULL,
            engine TEXT NOT NULL,
            confidence REAL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (user_id)
        )
        """
    )

    await conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_pronunciation_user_created
            ON pronunciation_progress(user_id, created_at DESC)
        """
    )

    await conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_pronunciation_user_item
            ON pronunciation_progress(user_id, item_type, item_id)
        """
    )
