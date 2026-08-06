import hashlib
import logging
from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile

from app.core.config import Settings
from app.core.exceptions import AppError, ForbiddenError, NotFoundError
from app.core.permissions import can_manage_document, can_read_document
from app.models.document import Document, DocumentType
from app.models.user import Role, User
from app.core.metrics import UPLOADS
from app.repositories.document import DocumentRepository
from app.repositories.user import UserRepository

ALLOWED_TYPES = {
    "application/pdf": DocumentType.PDF,
    "text/markdown": DocumentType.MARKDOWN,
    "text/x-markdown": DocumentType.MARKDOWN,
    "application/json": DocumentType.SLACK_JSON,
}
logger = logging.getLogger("app.uploads")


class DocumentService:
    def __init__(self, repository: DocumentRepository, users: UserRepository, settings: Settings):
        self.repository = repository
        self.users = users
        self.settings = settings

    async def upload(self, file: UploadFile, title: str | None, user: User) -> Document:
        if not user.department_id:
            raise ForbiddenError("A department membership is required to upload documents")
        document_type = ALLOWED_TYPES.get(file.content_type or "")
        if not document_type and Path(file.filename or "").suffix.lower() in {".md", ".markdown"}:
            if file.content_type in {"text/plain", "application/octet-stream"}:
                document_type = DocumentType.MARKDOWN
        if not document_type:
            raise AppError("unsupported_file", "Only PDF, Markdown, and Slack JSON are supported", 415)

        storage_name = f"{uuid4()}{Path(file.filename or '').suffix.lower()}"
        destination = self.settings.upload_dir / storage_name
        digest, size = hashlib.sha256(), 0
        try:
            with destination.open("xb") as output:
                while chunk := await file.read(1024 * 1024):
                    size += len(chunk)
                    if size > self.settings.max_upload_bytes:
                        raise AppError("file_too_large", "Upload exceeds the configured size limit", 413)
                    digest.update(chunk)
                    output.write(chunk)
        except Exception:
            destination.unlink(missing_ok=True)
            raise
        finally:
            await file.close()

        document = Document(
            title=title or Path(file.filename or "Untitled").stem,
            filename=Path(file.filename or "upload").name,
            media_type=file.content_type or "application/octet-stream",
            document_type=document_type,
            storage_key=storage_name,
            size_bytes=size,
            content_sha256=digest.hexdigest(),
            department_id=user.department_id,
            uploaded_by=user.id,
        )
        document = await self.repository.add(document)
        if user.role == Role.EMPLOYEE:
            await self.repository.assign(document.id, user.id, user.id)
        UPLOADS.labels(document_type.value, "accepted").inc()
        logger.info(
            "document_uploaded",
            extra={
                "document_id": str(document.id),
                "document_type": document_type.value,
                "document_filename": document.filename,
                "size_bytes": size,
                "department_id": str(document.department_id),
            },
        )
        return document

    async def get(self, document_id, user: User) -> Document:
        document = await self.repository.get(document_id)
        if not document:
            raise NotFoundError("Document not found")
        assigned = (
            await self.repository.is_assigned(document.id, user.id)
            if user.role == Role.EMPLOYEE else False
        )
        if not can_read_document(user, document, assigned=assigned):
            raise ForbiddenError("You are not authorized to access this document")
        return document

    async def delete(self, document_id, user: User) -> tuple[str, list[str]]:
        document = await self.get(document_id, user)
        if not can_manage_document(user, document):
            raise ForbiddenError("Only administrators or the department manager may delete this document")
        vector_ids = await self.repository.vector_ids(document.id)
        await self.repository.delete(document.id)
        return document.storage_key, vector_ids

    async def assign(self, document_id, target_user_id, actor: User) -> None:
        document = await self.repository.get(document_id)
        if not document:
            raise NotFoundError("Document not found")
        if not can_manage_document(actor, document):
            raise ForbiddenError("You cannot manage assignments for this document")
        target = await self.users.by_id(target_user_id)
        if not target or not target.is_active:
            raise NotFoundError("User not found")
        if target.role != Role.EMPLOYEE:
            raise AppError("invalid_assignment", "Only employees require document assignments", 422)
        if actor.role == Role.MANAGER and target.department_id != actor.department_id:
            raise ForbiddenError("Managers may assign documents only within their department")
        await self.repository.assign(document.id, target.id, actor.id)

    async def unassign(self, document_id, target_user_id, actor: User) -> None:
        document = await self.repository.get(document_id)
        if not document:
            raise NotFoundError("Document not found")
        if not can_manage_document(actor, document):
            raise ForbiddenError("You cannot manage assignments for this document")
        await self.repository.unassign(document.id, target_user_id)
