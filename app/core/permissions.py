from app.models.document import Document
from app.models.user import Role, User


def can_read_document(user: User, document: Document, *, assigned: bool) -> bool:
    if user.role == Role.ADMIN:
        return True
    if user.role == Role.MANAGER:
        return user.department_id is not None and user.department_id == document.department_id
    return assigned


def can_manage_document(user: User, document: Document) -> bool:
    if user.role == Role.ADMIN:
        return True
    return (
        user.role == Role.MANAGER
        and user.department_id is not None
        and user.department_id == document.department_id
    )
