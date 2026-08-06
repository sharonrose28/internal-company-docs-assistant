from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.core.config import Settings
from app.core.exceptions import ForbiddenError
from app.models.user import Role
from app.services.document import DocumentService


class FakeRepository:
    def __init__(self, document, assigned=False):
        self.document = document
        self.assigned = assigned
        self.deleted = None

    async def get(self, _document_id):
        return self.document

    async def is_assigned(self, _document_id, _user_id):
        return self.assigned

    async def vector_ids(self, _document_id):
        return ["vector-1"]

    async def delete(self, document_id):
        self.deleted = document_id


class FakeUsers:
    async def by_id(self, _user_id):
        return None


def service(repository):
    return DocumentService(repository, FakeUsers(), Settings(jwt_secret="x" * 32))


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("role", "same_department", "assigned", "allowed"),
    [
        (Role.ADMIN, False, False, True),
        (Role.MANAGER, True, False, True),
        (Role.MANAGER, False, False, False),
        (Role.EMPLOYEE, True, True, True),
        (Role.EMPLOYEE, True, False, False),
    ],
)
async def test_get_permission_matrix(user_factory, role, same_department, assigned, allowed):
    document_department = uuid4()
    user_department = document_department if same_department else uuid4()
    user = user_factory(role, user_department)
    document = SimpleNamespace(id=uuid4(), department_id=document_department)
    subject = service(FakeRepository(document, assigned))
    if allowed:
        assert await subject.get(document.id, user) is document
    else:
        with pytest.raises(ForbiddenError):
            await subject.get(document.id, user)


@pytest.mark.asyncio
async def test_only_admin_or_own_department_manager_can_delete(user_factory):
    department = uuid4()
    document = SimpleNamespace(id=uuid4(), department_id=department, storage_key="safe.pdf")
    repository = FakeRepository(document)
    employee = user_factory(Role.EMPLOYEE, department)
    with pytest.raises(ForbiddenError):
        await service(repository).delete(document.id, employee)
    assert repository.deleted is None

    manager = user_factory(Role.MANAGER, department)
    assert await service(repository).delete(document.id, manager) == ("safe.pdf", ["vector-1"])
    assert repository.deleted == document.id
