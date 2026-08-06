from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import Department, User


class UserRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def by_email(self, email: str) -> User | None:
        return await self.session.scalar(select(User).where(User.email == email.lower()))

    async def by_id(self, user_id: UUID) -> User | None:
        return await self.session.get(User, user_id)

    async def department_by_name(self, name: str) -> Department | None:
        return await self.session.scalar(select(Department).where(Department.name == name))

    def add(self, user: User) -> None:
        self.session.add(user)

    def add_department(self, department: Department) -> None:
        self.session.add(department)

    async def flush(self) -> None:
        await self.session.flush()
