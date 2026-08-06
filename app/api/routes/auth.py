from fastapi import APIRouter

from app.api.dependencies import AuthServiceDep
from app.schemas.auth import LoginRequest, SignupRequest, TokenResponse

router = APIRouter(tags=["authentication"])


@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest, service: AuthServiceDep) -> TokenResponse:
    return await service.login(payload)


@router.post("/signup", response_model=TokenResponse, status_code=201)
async def signup(payload: SignupRequest, service: AuthServiceDep) -> TokenResponse:
    return await service.signup(payload)
