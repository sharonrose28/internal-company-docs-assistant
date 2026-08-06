from collections.abc import AsyncIterator
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.ext.compiler import compiles

from app.db.base import Base
from app.models.user import Department, Role, User


@compiles(JSONB, "sqlite")
def compile_jsonb_for_sqlite(_type, _compiler, **_kwargs):
    return "JSON"


@pytest.fixture
def department_id():
    return uuid4()


@pytest.fixture
def user_factory():
    def factory(role=Role.EMPLOYEE, department_id=None, **overrides):
        values = {
            "id": uuid4(),
            "email": f"{uuid4()}@example.com",
            "password_hash": "hashed",
            "role": role,
            "department_id": department_id,
            "is_active": True,
            "token_version": 1,
        }
        values.update(overrides)
        return User(**values)
    return factory


@pytest_asyncio.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield session
        await session.rollback()
    await engine.dispose()


@pytest_asyncio.fixture
async def persisted_department(db_session):
    department = Department(name=f"Department-{uuid4()}")
    db_session.add(department)
    await db_session.flush()
    return department
