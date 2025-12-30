"""
Database engine and session management
"""
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import text
from models.document import Base
from core.config import DATABASE_URL
from utils.logging import log

# Global instances
engine = None
async_session = None


async def init_db():
    """Initialize database and create tables."""
    global engine, async_session

    engine = create_async_engine(DATABASE_URL, echo=False)
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with engine.begin() as conn:
        # Create pgvector extension
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        # Create tables
        await conn.run_sync(Base.metadata.create_all)

    log("✅ Database initialized")


async def get_session() -> AsyncSession:
    """Dependency for getting database session."""
    async with async_session() as session:
        yield session


async def close_db():
    """Close database connections."""
    global engine
    if engine:
        await engine.dispose()
        log("🔌 Database connections closed")
