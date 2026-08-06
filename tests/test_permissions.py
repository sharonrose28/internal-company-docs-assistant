from types import SimpleNamespace
from uuid import uuid4

from app.core.permissions import can_manage_document, can_read_document
from app.models.user import Role


def user(role, department_id=None):
    return SimpleNamespace(id=uuid4(), role=role, department_id=department_id)


def test_admin_can_read_and_manage_every_document():
    admin = user(Role.ADMIN)
    document = SimpleNamespace(department_id=uuid4())
    assert can_read_document(admin, document, assigned=False)
    assert can_manage_document(admin, document)


def test_manager_is_limited_to_own_department():
    department = uuid4()
    manager = user(Role.MANAGER, department)
    assert can_read_document(manager, SimpleNamespace(department_id=department), assigned=False)
    assert not can_read_document(manager, SimpleNamespace(department_id=uuid4()), assigned=True)


def test_employee_requires_explicit_assignment_and_cannot_manage():
    employee = user(Role.EMPLOYEE, uuid4())
    document = SimpleNamespace(department_id=employee.department_id)
    assert not can_read_document(employee, document, assigned=False)
    assert can_read_document(employee, document, assigned=True)
    assert not can_manage_document(employee, document)
