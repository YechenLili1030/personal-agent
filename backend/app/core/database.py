from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from .config import DATABASE_URL, DATABASE_URL_SYNC

engine = create_async_engine(DATABASE_URL, pool_size=10, max_overflow=20, echo=False)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncSession:
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db():
    """Create all tables. Call on startup."""
    from sqlalchemy import create_engine as sync_create_engine
    sync_engine = sync_create_engine(DATABASE_URL_SYNC, echo=False)
    Base.metadata.create_all(sync_engine)
    sync_engine.dispose()
