import logging
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from app.config import settings

logger = logging.getLogger("na7la.database")

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    connect_args={"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {}
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False
)


class Base(DeclarativeBase):
    pass


async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def _migrate_sqlite_columns(conn):
    """Safely adds missing columns to existing SQLite tables without losing data."""
    migrations = {
        "users": [
            ("user_token", "TEXT"),
            ("email", "TEXT"),
            ("password_hash", "TEXT"),
            ("pin_code", "TEXT"),
        ],
        "devices": [
            ("min_voltage", "FLOAT DEFAULT 190.0"),
            ("max_voltage", "FLOAT DEFAULT 245.0"),
            ("max_power_w", "FLOAT DEFAULT 3200.0"),
            ("child_lock_enabled", "BOOLEAN DEFAULT 0"),
            ("away_mode_enabled", "BOOLEAN DEFAULT 0"),
            ("surge_router_channel", "INTEGER DEFAULT 1"),
        ],
        "outlets": [
            ("icon", "TEXT DEFAULT 'outlet'"),
            ("auto_off_minutes", "INTEGER DEFAULT 0"),
            ("standby_cutoff_w", "FLOAT DEFAULT 0.0"),
            ("standby_cutoff_minutes", "INTEGER DEFAULT 15"),
            ("is_surge_priority", "BOOLEAN DEFAULT 0"),
            ("last_turned_on", "DATETIME"),
        ],
    }

    for table, cols in migrations.items():
        try:
            res = await conn.execute(text(f"PRAGMA table_info({table})"))
            existing = {row[1] for row in res.fetchall()}
            for col_name, col_type in cols:
                if col_name not in existing:
                    logger.info(f"Auto-migrating DB: adding column {col_name} to {table}")
                    await conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col_name} {col_type}"))
        except Exception as e:
            logger.debug(f"Migration check for {table} skipped or table not yet created: {e}")


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        if "sqlite" in settings.DATABASE_URL:
            await _migrate_sqlite_columns(conn)
