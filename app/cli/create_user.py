import argparse
import asyncio
from getpass import getpass

from sqlalchemy import select

from app.core.security import hash_password
from app.db.session import SessionFactory
from app.models.user import Department, Role, User


async def create_user(email: str, role: Role, department_name: str | None) -> None:
    password = getpass("Password: ")
    confirmation = getpass("Confirm password: ")
    if password != confirmation:
        raise SystemExit("Passwords do not match")
    if len(password) < 5:
        raise SystemExit("Password must contain at least 5 characters")
    if not any(character.isalpha() for character in password) or not any(
        character.isdigit() for character in password
    ):
        raise SystemExit("Password must contain at least one letter and one number")

    async with SessionFactory.begin() as session:
        normalized_email = email.strip().lower()
        if await session.scalar(select(User.id).where(User.email == normalized_email)):
            raise SystemExit(f"A user with email {normalized_email} already exists")

        department = None
        if department_name:
            name = department_name.strip()
            department = await session.scalar(select(Department).where(Department.name == name))
            if not department:
                department = Department(name=name)
                session.add(department)
                await session.flush()
        if role != Role.ADMIN and not department:
            raise SystemExit("Managers and employees require --department")

        session.add(User(
            email=normalized_email,
            password_hash=hash_password(password),
            role=role,
            department_id=department.id if department else None,
            is_active=True,
        ))
    print(f"Created {role.value} user {normalized_email}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Create an Internal Docs Assistant user")
    parser.add_argument("--email", required=True)
    parser.add_argument("--role", choices=[role.value for role in Role], default=Role.EMPLOYEE.value)
    parser.add_argument("--department", help="Required for manager and employee roles")
    arguments = parser.parse_args()
    asyncio.run(create_user(arguments.email, Role(arguments.role), arguments.department))


if __name__ == "__main__":
    main()
