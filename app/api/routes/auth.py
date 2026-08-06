from fastapi import APIRouter

from app.api.dependencies import AuthServiceDep
from app.schemas.auth import LoginRequest, TokenResponse

router = APIRouter(tags=["authentication"])


@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest, service: AuthServiceDep) -> TokenResponse:
    return await service.login(payload)

