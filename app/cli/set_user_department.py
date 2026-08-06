import argparse
import asyncio

from sqlalchemy import select

from app.db.session import SessionFactory
from app.models.user import Department, User


async def set_department(email: str, department_name: str) -> None:
    async with SessionFactory.begin() as session:
        normalized_email = email.strip().lower()
        user = await session.scalar(select(User).where(User.email == normalized_email))
        if not user:
            raise SystemExit(f"User {normalized_email} does not exist")
        name = department_name.strip()
        department = await session.scalar(select(Department).where(Department.name == name))
        if not department:
            department = Department(name=name)
            session.add(department)
            await session.flush()
        user.department_id = department.id
    print(f"Assigned {normalized_email} to {name}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Assign a user to a department")
    parser.add_argument("--email", required=True)
    parser.add_argument("--department", required=True)
    arguments = parser.parse_args()
    asyncio.run(set_department(arguments.email, arguments.department))


if __name__ == "__main__":
    main()
