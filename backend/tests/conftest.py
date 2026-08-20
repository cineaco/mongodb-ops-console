import base64
import os

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///test.db")
os.environ.setdefault("JWT_SECRET", "test-jwt-secret-for-tests")
os.environ.setdefault("MASTER_KEY", base64.b64encode(os.urandom(32)).decode())
os.environ.setdefault("CORS_ALLOWED_ORIGINS", "http://localhost:5173")

from app.core.database import get_db  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Base, Role, User  # noqa: E402

_engine = create_async_engine("sqlite+aiosqlite:///test.db", echo=False)
_session_factory = async_sessionmaker(_engine, class_=AsyncSession, expire_on_commit=False)


@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with _session_factory() as session:
        for name, desc in [("admin", "Admin"), ("operator", "Operator"), ("viewer", "Viewer")]:
            session.add(Role(name=name, description=desc))
        await session.commit()
    yield
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def db_session():
    async with _session_factory() as session:
        yield session


@pytest_asyncio.fixture
async def client(db_session: AsyncSession):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def admin_user(db_session: AsyncSession) -> User:
    from sqlalchemy import select

    result = await db_session.execute(select(Role).where(Role.name == "admin"))
    role = result.scalar_one()
    pw_hash = await hash_password("admin-password")
    user = User(username="admin", password_hash=pw_hash, role_id=role.id)
    db_session.add(user)
    await db_session.commit()
    return user
