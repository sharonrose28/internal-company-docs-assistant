from datetime import UTC, datetime, timedelta
from uuid import UUID

import jwt
from pwdlib import PasswordHash

from app.core.config import Settings

password_hash = PasswordHash.recommended()


def verify_password(plain: str, hashed: str) -> bool:
    return password_hash.verify(plain, hashed)


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def create_access_token(user_id: UUID, token_version: int, settings: Settings) -> tuple[str, int]:
    now = datetime.now(UTC)
    expires = now + timedelta(minutes=settings.access_token_minutes)
    payload = {
        "sub": str(user_id), "ver": token_version, "iat": now, "exp": expires,
        "iss": settings.jwt_issuer, "aud": settings.jwt_audience,
    }
    token = jwt.encode(payload, settings.jwt_secret.get_secret_value(), algorithm="HS256")
    return token, int((expires - now).total_seconds())


def decode_access_token(token: str, settings: Settings) -> dict:
    return jwt.decode(
        token,
        settings.jwt_secret.get_secret_value(),
        algorithms=["HS256"],
        issuer=settings.jwt_issuer,
        audience=settings.jwt_audience,
        options={"require": ["sub", "exp", "iat", "iss", "aud"]},
    )

