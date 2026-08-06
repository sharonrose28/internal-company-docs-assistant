from types import SimpleNamespace
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.api.dependencies import auth_service, document_service, get_current_user
from app.core.exceptions import ForbiddenError
from app.main import app
from app.models.document import DocumentStatus, DocumentType
from app.models.user import Role


class FakeAuth:
    async def login(self, payload):
        return {"access_token": "mock-jwt", "token_type": "bearer", "expires_in": 900}


class FakeDocuments:
    def __init__(self, document=None, error=None):
        self.document = document
        self.error = error

    async def get(self, _document_id, _user):
        if self.error:
            raise self.error
        return self.document


@pytest.fixture
def api_user(user_factory):
    return user_factory(Role.ADMIN)


@pytest.fixture
def document(api_user):
    return SimpleNamespace(
        id=uuid4(), title="Handbook", filename="handbook.pdf",
        document_type=DocumentType.PDF, status=DocumentStatus.READY, size_bytes=100,
        department_id=uuid4(), uploaded_by=api_user.id,
        created_at="2026-01-01T00:00:00Z",
    )


@pytest_asyncio.fixture
async def client(api_user):
    app.dependency_overrides[get_current_user] = lambda: api_user
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as value:
        yield value
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_login_contract_does_not_call_openai_or_database():
    app.dependency_overrides[auth_service] = lambda: FakeAuth()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/login", json={"email": "person@example.com", "password": "secret-password1"}
        )
    app.dependency_overrides.clear()
    assert response.status_code == 200
    assert response.json() == {
        "access_token": "mock-jwt", "token_type": "bearer", "expires_in": 900,
    }


@pytest.mark.asyncio
async def test_get_document_returns_schema(client, document):
    app.dependency_overrides[document_service] = lambda: FakeDocuments(document)
    response = await client.get(f"/documents/{document.id}")
    assert response.status_code == 200
    assert response.json()["filename"] == "handbook.pdf"


@pytest.mark.asyncio
async def test_permission_failure_is_json_403(client, document):
    app.dependency_overrides[document_service] = lambda: FakeDocuments(
        error=ForbiddenError("Document is outside your access scope")
    )
    response = await client.get(f"/documents/{document.id}")
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"


@pytest.mark.asyncio
async def test_request_validation_returns_422(client):
    response = await client.get("/documents/not-a-uuid")
    assert response.status_code == 422
