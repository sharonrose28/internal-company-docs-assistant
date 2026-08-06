from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.core.config import Settings
from app.core.exceptions import ForbiddenError
from app.models.user import Role, User
from app.schemas.search import SearchFilters, SearchMode
from app.services.retrieval import RetrievalService


class FakeDense:
    async def aembed_query(self, _):
        return [0.1, 0.2, 0.3]


class FakeSparse:
    def query_embed(self, _):
        yield SimpleNamespace(indices=Array([1]), values=Array([1.0]))


class Array(list):
    def tolist(self):
        return list(self)


class FakeQdrant:
    def __init__(self):
        self.kwargs = None

    async def collection_exists(self, _collection):
        return True

    async def query_points(self, **kwargs):
        self.kwargs = kwargs
        return SimpleNamespace(points=[SimpleNamespace(
            score=0.91,
            payload={
                "text": "Authorized policy passage",
                "page": 4,
                "document_id": str(uuid4()),
                "department": str(uuid4()),
            },
        )])


class FakeAuthorizer:
    async def authorized_document_ids(self, _user, document_ids):
        return document_ids


class EmptyQdrant(FakeQdrant):
    async def collection_exists(self, _collection):
        return False


@pytest.mark.asyncio
async def test_hybrid_search_applies_permission_filter_and_returns_five_or_fewer():
    department_id = uuid4()
    user = User(id=uuid4(), email="employee@example.com", password_hash="x", role=Role.EMPLOYEE,
                department_id=department_id, is_active=True, token_version=1)
    qdrant = FakeQdrant()
    service = RetrievalService(
        Settings(jwt_secret="x" * 32, openai_api_key="test-key"),
        dense_embeddings=FakeDense(), sparse_embeddings=FakeSparse(), qdrant=qdrant,
    )
    results = await service.search(
        "security policy", user, FakeAuthorizer(), SearchMode.HYBRID
    )
    assert len(results) == 1
    assert results[0].chunk == "Authorized policy passage"
    assert results[0].page_number == 4
    assert qdrant.kwargs["limit"] == 5
    assert len(qdrant.kwargs["prefetch"]) == 2


@pytest.mark.asyncio
async def test_department_filter_fails_closed_outside_user_scope():
    user = User(id=uuid4(), email="manager@example.com", password_hash="x", role=Role.MANAGER,
                department_id=uuid4(), is_active=True, token_version=1)
    service = RetrievalService(
        Settings(jwt_secret="x" * 32, openai_api_key="test-key"),
        dense_embeddings=FakeDense(), sparse_embeddings=FakeSparse(), qdrant=FakeQdrant(),
    )
    with pytest.raises(ForbiddenError):
        await service.search(
            "policy", user, FakeAuthorizer(), filters=SearchFilters(department_id=uuid4())
        )


@pytest.mark.asyncio
async def test_missing_collection_is_an_empty_knowledge_base_not_an_error():
    user = User(
        id=uuid4(), email="admin@example.com", password_hash="x", role=Role.ADMIN,
        department_id=None, is_active=True, token_version=1,
    )
    service = RetrievalService(
        Settings(jwt_secret="x" * 32, openai_api_key="test-key"),
        dense_embeddings=FakeDense(), sparse_embeddings=FakeSparse(), qdrant=EmptyQdrant(),
    )
    assert await service.search("policy", user, FakeAuthorizer()) == []
