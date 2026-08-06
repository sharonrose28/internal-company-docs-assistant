from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Query, Response, status

from app.api.dependencies import CacheServiceDep, CurrentUser, RAGServiceDep, SessionDep
from app.core.exceptions import ForbiddenError
from app.repositories.chat import ChatRepository
from app.repositories.conversation import ConversationRepository
from app.schemas.chat import (
    ChatHistoryItem, ChatRequest, ChatResponse, ChatSessionCreate, ChatSessionRead,
)

router = APIRouter(tags=["chat"])


@router.post("/chat", response_model=ChatResponse)
async def chat(
    payload: ChatRequest,
    background_tasks: BackgroundTasks,
    user: CurrentUser,
    service: RAGServiceDep,
    cache: CacheServiceDep,
) -> ChatResponse:
    response = await service.ask(payload, user)
    background_tasks.add_task(cache.bump_history, str(user.id))
    return response


@router.get("/chat/history", response_model=list[ChatHistoryItem])
async def history(
    user: CurrentUser,
    session: SessionDep,
    cache: CacheServiceDep,
    session_id: UUID,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
):
    version = await cache.history_version(str(user.id))
    conversations = ConversationRepository(session)
    if not await conversations.get_owned(session_id, user.id):
        raise ForbiddenError("You are not authorized to access this chat session")
    key = cache.history_key(str(user.id), str(session_id), version, offset, limit)
    cached = await cache.get_json(key)
    if cached is not None:
        return [ChatHistoryItem.model_validate(item) for item in cached]
    items = await ChatRepository(session).history(user, session_id, offset, limit)
    serialized = [ChatHistoryItem.model_validate(item).model_dump(mode="json") for item in items]
    await cache.set_json(key, serialized)
    return items


@router.post("/chat/sessions", response_model=ChatSessionRead, status_code=201)
async def create_session(payload: ChatSessionCreate, user: CurrentUser, session: SessionDep):
    return await ConversationRepository(session).create(user.id, payload.title)


@router.get("/chat/sessions", response_model=list[ChatSessionRead])
async def list_sessions(
    user: CurrentUser,
    session: SessionDep,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
):
    return await ConversationRepository(session).list_owned(user.id, offset, limit)


@router.delete("/chat/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_session(
    session_id: UUID,
    background_tasks: BackgroundTasks,
    user: CurrentUser,
    session: SessionDep,
    cache: CacheServiceDep,
):
    deleted = await ConversationRepository(session).delete_owned(session_id, user.id)
    if not deleted:
        raise ForbiddenError("You are not authorized to delete this chat session")
    background_tasks.add_task(cache.bump_history, str(user.id))
    return Response(status_code=status.HTTP_204_NO_CONTENT)
