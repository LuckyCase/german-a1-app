"""
Lightweight database migration runner for asyncpg.

Keeps a `schema_migrations` table with applied version numbers.
Migration modules live in the `migrations/` package and follow the naming
convention `NNNN_description.py`.  Each module exposes:

    async def upgrade(conn: asyncpg.Connection) -> None: ...
"""

import importlib
import logging
import pkgutil
import re

logger = logging.getLogger(__name__)

_MIGRATION_RE = re.compile(r"^(\d+)_")


def _discover_migrations() -> list[tuple[int, str]]:
    """Return sorted list of (version, module_name) from the migrations package."""
    import migrations as pkg

    result = []
    for importer, mod_name, is_pkg in pkgutil.iter_modules(pkg.__path__):
        m = _MIGRATION_RE.match(mod_name)
        if m:
            result.append((int(m.group(1)), mod_name))
    result.sort(key=lambda t: t[0])
    return result


async def run_migrations(pool) -> int:
    """Apply pending migrations. Returns number of migrations applied."""
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        applied = {
            row["version"]
            for row in await conn.fetch("SELECT version FROM schema_migrations")
        }

    migrations = _discover_migrations()
    count = 0

    for version, mod_name in migrations:
        if version in applied:
            continue

        logger.info("Applying migration %04d (%s) …", version, mod_name)
        module = importlib.import_module(f"migrations.{mod_name}")

        async with pool.acquire() as conn:
            async with conn.transaction():
                await module.upgrade(conn)
                await conn.execute(
                    "INSERT INTO schema_migrations (version, name) VALUES ($1, $2)",
                    version, mod_name,
                )
        logger.info("Migration %04d applied.", version)
        count += 1

    if count == 0:
        logger.info("Database schema is up-to-date.")
    else:
        logger.info("Applied %d migration(s).", count)
    return count
