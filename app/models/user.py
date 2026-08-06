import enum
from uuid import UUID

from sqlalchemy import Boolean, Enum, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin


class Role(str, enum.Enum):
    ADMIN = "admin"
    MANAGER = "manager"
    EMPLOYEE = "employee"


class User(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "users"
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[Role] = mapped_column(Enum(Role, name="user_role"), default=Role.EMPLOYEE)
    department_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("departments.id"))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    token_version: Mapped[int] = mapped_column(default=1)
    department = relationship("Department")


class Department(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "departments"
    name: Mapped[str] = mapped_column(String(120), unique=True)

