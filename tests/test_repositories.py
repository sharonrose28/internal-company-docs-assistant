from uuid import uuid4

import pytest

from app.models.document import Document, DocumentType
from app.models.user import Role, User
from app.repositories.conversation import ConversationRepository
from app.repositories.document import DocumentRepository
from app.repositories.user import UserRepository


def make_document(department_id, uploaded_by, title="Policy"):
    return Document(
        title=title, filename=f"{title}.pdf", media_type="application/pdf",
        document_type=DocumentType.PDF, storage_key=f"{uuid4()}.pdf", size_bytes=10,
        content_sha256=uuid4().hex * 2, department_id=department_id, uploaded_by=uploaded_by,
    )


@pytest.mark.asyncio
async def test_user_repository_normalizes_email(db_session, persisted_department):
    user = User(
        email="person@example.com", password_hash="x", role=Role.EMPLOYEE,
        department_id=persisted_department.id,
    )
    db_session.add(user)
    await db_session.flush()
    repository = UserRepository(db_session)
    assert await repository.by_email("PERSON@EXAMPLE.COM") == user
    assert await repository.by_id(user.id) == user


@pytest.mark.asyncio
async def test_document_repository_enforces_role_scopes(db_session, persisted_department, user_factory):
    other_department = type(persisted_department)(name=f"Other-{uuid4()}")
    db_session.add(other_department)
    await db_session.flush()
    admin = user_factory(Role.ADMIN)
    manager = user_factory(Role.MANAGER, persisted_department.id)
    employee = user_factory(Role.EMPLOYEE, persisted_department.id)
    uploader = user_factory(Role.ADMIN)
    db_session.add_all([admin, manager, employee, uploader])
    await db_session.flush()
    own = make_document(persisted_department.id, uploader.id, "Own")
    other = make_document(other_department.id, uploader.id, "Other")
    repository = DocumentRepository(db_session)
    await repository.add(own)
    await repository.add(other)
    await repository.assign(own.id, employee.id, admin.id)

    assert (await repository.list_authorized(admin, 0, 10))[1] == 2
    assert (await repository.list_authorized(manager, 0, 10))[0] == [own]
    assert (await repository.list_authorized(employee, 0, 10))[0] == [own]
    assert await repository.authorized_document_ids(employee, {own.id, other.id}) == {own.id}

    await repository.unassign(own.id, employee.id)
    assert not await repository.is_assigned(own.id, employee.id)


@pytest.mark.asyncio
async def test_conversation_repository_is_owner_scoped_and_limits_memory(
    db_session, persisted_department, user_factory,
):
    first = user_factory(department_id=persisted_department.id)
    second = user_factory(department_id=persisted_department.id)
    db_session.add_all([first, second])
    await db_session.flush()
    repository = ConversationRepository(db_session)
    conversation = await repository.create(first.id, "x" * 250)
    assert len(conversation.title) == 200
    assert await repository.get_owned(conversation.id, first.id) == conversation
    assert await repository.get_owned(conversation.id, second.id) is None
    assert await repository.list_owned(first.id, 0, 10) == [conversation]
    assert not await repository.delete_owned(conversation.id, second.id)
    assert await repository.delete_owned(conversation.id, first.id)
    assert await repository.get_owned(conversation.id, first.id) is None
