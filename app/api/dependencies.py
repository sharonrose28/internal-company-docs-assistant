from functools import lru_cache
from typing import Annotated
from uuid import UUID

import jwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.exceptions import AppError
from app.core.logging import user_id_ctx
from app.core.security import decode_access_token
from app.db.session import get_session
from app.models.user import User
from app.repositories.chat import ChatRepository
from app.repositories.conversation import ConversationRepository
from app.repositories.document import DocumentRepository
from app.repositories.user import UserRepository
from app.services.auth import AuthService
from app.services.audit import AuditService
from app.services.cache import CacheService
from app.services.generation import AnswerGenerator
from app.services.memory import ConversationMemoryService
from app.services.rag import RAGService
from app.services.document import DocumentService
from app.services.retrieval import RetrievalService

SessionDep = Annotated[AsyncSession, Depends(get_session)]
SettingsDep = Annotated[Settings, Depends(get_settings)]
bearer = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    session: SessionDep,
    settings: SettingsDep,
) -> User:
    unauthorized = AppError("unauthorized", "Authentication required", 401)
    if not credentials:
        raise unauthorized
    try:
        claims = decode_access_token(credentials.credentials, settings)
        user = await UserRepository(session).by_id(UUID(claims["sub"]))
    except (jwt.PyJWTError, ValueError, KeyError):
        raise unauthorized from None
    if not user or not user.is_active or user.token_version != claims.get("ver"):
        raise unauthorized
    user_id_ctx.set(str(user.id))
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def auth_service(session: SessionDep, settings: SettingsDep) -> AuthService:
    return AuthService(UserRepository(session), settings)


def document_service(session: SessionDep, settings: SettingsDep) -> DocumentService:
    return DocumentService(DocumentRepository(session), UserRepository(session), settings)


@lru_cache
def cache_service() -> CacheService:
    return CacheService(get_settings())


@lru_cache
def retrieval_service() -> RetrievalService:
    # Reuse HTTP/Qdrant clients and the sparse model across requests to avoid cold-start latency.
    return RetrievalService(get_settings(), cache=cache_service())


@lru_cache
def answer_generator() -> AnswerGenerator:
    return AnswerGenerator(get_settings())


def rag_service(
    session: SessionDep,
    retrieval: Annotated[RetrievalService, Depends(retrieval_service)],
    generator: Annotated[AnswerGenerator, Depends(answer_generator)],
) -> RAGService:
    documents = DocumentRepository(session)
    return RAGService(
        settings=get_settings(),
        retrieval=retrieval,
        documents=documents,
        chats=ChatRepository(session),
        generator=generator,
        audit=AuditService(),
        memory=ConversationMemoryService(ConversationRepository(session), documents),
        cache=cache_service(),
    )

AuthServiceDep = Annotated[AuthService, Depends(auth_service)]
DocumentServiceDep = Annotated[DocumentService, Depends(document_service)]
RAGServiceDep = Annotated[RAGService, Depends(rag_service)]
RetrievalServiceDep = Annotated[RetrievalService, Depends(retrieval_service)]
CacheServiceDep = Annotated[CacheService, Depends(cache_service)]
