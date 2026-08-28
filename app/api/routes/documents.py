from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, File, Form, Query, Response, UploadFile, status

from app.api.dependencies import CurrentUser, DocumentServiceDep, SessionDep
from app.repositories.document import DocumentRepository
from app.repositories.job import JobRepository
from app.schemas.document import DocumentList, DocumentRead
from app.workers.tasks import dispatch_task

router = APIRouter(tags=["documents"])


@router.post("/upload", response_model=DocumentRead, status_code=status.HTTP_202_ACCEPTED)
async def upload(
    file: Annotated[UploadFile, File()],
    background_tasks: BackgroundTasks,
    user: CurrentUser,
    service: DocumentServiceDep,
    session: SessionDep,
    title: Annotated[str | None, Form(max_length=255)] = None,
) -> DocumentRead:
    document = await service.upload(file, title, user)
    job = await JobRepository(session).create(document.id)
    # Starlette runs response background tasks before FastAPI finishes generator
    # dependency cleanup. Commit explicitly so inline ingestion can always see
    # the document, durable source, and job rows before it starts.
    await session.commit()
    background_tasks.add_task(
        dispatch_task,
        "documents.extract",
        [str(document.id), str(job.id)],
    )
    return DocumentRead.model_validate(document)


@router.get("/documents", response_model=DocumentList)
async def list_documents(
    user: CurrentUser,
    session: SessionDep,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> DocumentList:
    items, total = await DocumentRepository(session).list_authorized(user, offset, limit)
    return DocumentList(items=[DocumentRead.model_validate(item) for item in items], total=total)


@router.get("/documents/{document_id}", response_model=DocumentRead)
async def get_document(document_id: UUID, user: CurrentUser, service: DocumentServiceDep):
    return await service.get(document_id, user)


@router.delete("/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: UUID,
    background_tasks: BackgroundTasks,
    user: CurrentUser,
    service: DocumentServiceDep,
):
    storage_key, vector_ids = await service.delete(document_id, user)
    background_tasks.add_task(
        dispatch_task,
        "documents.delete_file",
        [storage_key],
    )
    if vector_ids:
        background_tasks.add_task(
            dispatch_task,
            "documents.delete_vectors",
            [vector_ids],
        )
    background_tasks.add_task(dispatch_task, "documents.invalidate_cache")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.put("/documents/{document_id}/assignments/{target_user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def assign_document(
    document_id: UUID,
    target_user_id: UUID,
    background_tasks: BackgroundTasks,
    user: CurrentUser,
    service: DocumentServiceDep,
):
    await service.assign(document_id, target_user_id, user)
    background_tasks.add_task(
        dispatch_task,
        "documents.sync_permissions",
        [str(document_id)],
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/documents/{document_id}/assignments/{target_user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def unassign_document(
    document_id: UUID,
    target_user_id: UUID,
    background_tasks: BackgroundTasks,
    user: CurrentUser,
    service: DocumentServiceDep,
):
    await service.unassign(document_id, target_user_id, user)
    background_tasks.add_task(
        dispatch_task,
        "documents.sync_permissions",
        [str(document_id)],
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
