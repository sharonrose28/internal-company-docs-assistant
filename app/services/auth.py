import logging

from sqlalchemy.exc import IntegrityError

from app.core.config import Settings
from app.core.exceptions import AppError
from app.core.metrics import AUTH_ATTEMPTS
from app.core.security import create_access_token, hash_password, verify_password
from app.models.user import Department, Role, User
from app.repositories.user import UserRepository
from app.schemas.auth import LoginRequest, SignupRequest, TokenResponse

logger = logging.getLogger("app.authentication")


class AuthService:
    def __init__(self, users: UserRepository, settings: Settings):
        self.users = users
        self.settings = settings

    async def login(self, request: LoginRequest) -> TokenResponse:
        user = await self.users.by_email(str(request.email))
        if (
            not user
            or not user.is_active
            or not verify_password(request.password, user.password_hash)
        ):
            AUTH_ATTEMPTS.labels("failure").inc()
            logger.warning("authentication_failed", extra={"email": str(request.email)})
            raise AppError("invalid_credentials", "Invalid email or password", 401)
        token, expires_in = create_access_token(user.id, user.token_version, self.settings)
        AUTH_ATTEMPTS.labels("success").inc()
        logger.info(
            "authentication_succeeded",
            extra={"authenticated_user_id": str(user.id), "role": user.role.value},
        )
        return TokenResponse(access_token=token, expires_in=expires_in)

    async def signup(self, request: SignupRequest) -> TokenResponse:
        email = str(request.email).strip().lower()
        if await self.users.by_email(email):
            raise AppError(
                "email_already_registered", "An account with this email already exists", 409
            )

        department = await self.users.department_by_name(request.department)
        if department is None:
            department = Department(name=request.department)
            self.users.add_department(department)
            await self.users.flush()

        user = User(
            email=email,
            password_hash=hash_password(request.password),
            role=Role.EMPLOYEE,
            department_id=department.id,
            is_active=True,
        )
        self.users.add(user)
        try:
            await self.users.flush()
        except IntegrityError as exc:
            raise AppError(
                "email_already_registered", "An account with this email already exists", 409
            ) from exc

        token, expires_in = create_access_token(user.id, user.token_version, self.settings)
        logger.info(
            "account_registered",
            extra={"authenticated_user_id": str(user.id), "role": user.role.value},
        )
        return TokenResponse(access_token=token, expires_in=expires_in)
