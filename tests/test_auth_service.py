from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.core.config import Settings
from app.core.exceptions import AppError
from app.models.user import Role
from app.schemas.auth import LoginRequest
from app.services.auth import AuthService


class StubUsers:
    def __init__(self, user):
        self._user = user

    async def by_email(self, email: str):
        return self._user if self._user and self._user.email == email else None


@pytest.mark.asyncio
async def test_login_returns_401_when_password_verification_raises(monkeypatch):
    user = SimpleNamespace(
        id=uuid4(),
        email="person@example.com",
        password_hash="broken-hash",
        is_active=True,
        token_version=1,
        role=Role.EMPLOYEE,
    )
    service = AuthService(StubUsers(user), Settings(jwt_secret="x" * 32))

    def explode(_plain: str, _hashed: str) -> bool:
        raise ValueError("unsupported hash format")

    monkeypatch.setattr("app.services.auth.verify_password", explode)

    with pytest.raises(AppError) as exc_info:
        await service.login(LoginRequest(email="person@example.com", password="abc12"))

    assert exc_info.value.status_code == 401
    assert exc_info.value.code == "invalid_credentials"
