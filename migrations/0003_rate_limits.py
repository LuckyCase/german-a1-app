"""
Add shared rate limit table for multi-instance deployments.
"""


async def upgrade(conn) -> None:
    await conn.execute(
        """
        CREATE TABLE IF NOT EXISTS rate_limits (
            id SERIAL PRIMARY KEY,
            user_id BIGINT NOT NULL,
            action TEXT NOT NULL,
            window_start TIMESTAMP NOT NULL,
            request_count INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, action, window_start)
        )
        """
    )

    await conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_rate_limits_action_window
            ON rate_limits(action, window_start DESC)
        """
    )
