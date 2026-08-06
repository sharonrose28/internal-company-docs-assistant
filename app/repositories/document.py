from uuid import UUID

from sqlalchemy import delete, exists, false, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document, DocumentAssignment, DocumentChunk
from app.models.user import Role, User


class DocumentRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    @staticmethod
    def access_filter(user: User):
        if user.role == Role.ADMIN:
            return True
        if user.role == Role.MANAGER:
            return Document.department_id == user.department_id if user.department_id else false()
        return exists().where(
            DocumentAssignment.document_id == Document.id,
            DocumentAssignment.user_id == user.id,
        )

    async def add(self, document: Document) -> Document:
        self.session.add(document)
        await self.session.flush()
        return document

    async def get(self, document_id: UUID) -> Document | None:
        return await self.session.get(Document, document_id)

    async def is_assigned(self, document_id: UUID, user_id: UUID) -> bool:
        return bool(await self.session.scalar(select(exists().where(
            DocumentAssignment.document_id == document_id,
            DocumentAssignment.user_id == user_id,
        ))))

    async def assign(self, document_id: UUID, user_id: UUID, assigned_by: UUID) -> None:
        if not await self.is_assigned(document_id, user_id):
            self.session.add(DocumentAssignment(
                document_id=document_id, user_id=user_id, assigned_by=assigned_by
            ))
            await self.session.flush()

    async def unassign(self, document_id: UUID, user_id: UUID) -> None:
        await self.session.execute(delete(DocumentAssignment).where(
            DocumentAssignment.document_id == document_id,
            DocumentAssignment.user_id == user_id,
        ))

    async def assigned_user_ids(self, document_id: UUID) -> list[UUID]:
        return list((await self.session.scalars(
            select(DocumentAssignment.user_id).where(DocumentAssignment.document_id == document_id)
        )).all())

    async def list_authorized(self, user: User, offset: int, limit: int) -> tuple[list[Document], int]:
        predicate = self.access_filter(user)
        query = select(Document).where(predicate).order_by(Document.created_at.desc())
        items = list((await self.session.scalars(query.offset(offset).limit(limit))).all())
        total = await self.session.scalar(select(func.count()).select_from(Document).where(predicate))
        return items, total or 0

    async def authorized_document_ids(self, user: User, document_ids: set[UUID]) -> set[UUID]:
        if not document_ids:
            return set()
        values = await self.session.scalars(
            select(Document.id).where(Document.id.in_(document_ids), self.access_filter(user))
        )
        return set(values.all())

    async def vector_ids(self, document_id: UUID) -> list[str]:
        return list((await self.session.scalars(
            select(DocumentChunk.vector_id).where(
                DocumentChunk.document_id == document_id,
                DocumentChunk.vector_id.is_not(None),
            )
        )).all())

    async def delete(self, document_id: UUID) -> None:
        await self.session.execute(delete(Document).where(Document.id == document_id))
