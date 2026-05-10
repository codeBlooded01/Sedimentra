from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from app.core.config import settings

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency: yields an async DB session per request."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db():
    """Create all tables on startup (dev/staging only — use Alembic in production)."""
    from app.db.models.upload import Base
    import app.db.models.user
    import app.db.models.accession
    from app.db.models.ml_models import Base as MLBase
    from sqlalchemy import text
    import logging
    logger = logging.getLogger(__name__)
    
    # 1. Create tables outside of the manual DDL transaction to ensure they commit
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(MLBase.metadata.create_all)

    # 2. Separate transaction for manual schema modifications
    async with engine.begin() as conn:
        try:
            await conn.execute(text("ALTER TABLE users ADD COLUMN is_primary_admin BOOLEAN NOT NULL DEFAULT FALSE;"))
            logger.info("Added is_primary_admin column to users table.")
        except Exception:
            pass

    # 3. Separate transaction for updates (avoids rolling back previous steps)
    async with engine.begin() as conn:
        try:
            await conn.execute(text("UPDATE users SET is_primary_admin = TRUE WHERE role = 'admin' AND is_primary_admin = FALSE;"))
        except Exception:
            pass
