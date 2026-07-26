from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies import get_auth_service
from app.schemas.auth import LoginRequest, RefreshRequest, RegisterRequest, TokenPairResponse
from app.services.auth import (
    AuthService,
    EmailAlreadyRegisteredError,
    InvalidCredentialsError,
    InvalidRefreshSessionError,
)

router = APIRouter(prefix="/auth", tags=["auth"])
AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]


@router.post(
    "/register",
    response_model=TokenPairResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register(request: RegisterRequest, service: AuthServiceDep) -> TokenPairResponse:
    try:
        return await service.register(request)
    except EmailAlreadyRegisteredError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "email_already_registered", "message": "Аккаунт уже существует"},
        ) from error


@router.post("/login", response_model=TokenPairResponse)
async def login(request: LoginRequest, service: AuthServiceDep) -> TokenPairResponse:
    try:
        return await service.login(request)
    except InvalidCredentialsError as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "invalid_credentials", "message": "Неверный email или пароль"},
        ) from error


@router.post("/refresh", response_model=TokenPairResponse)
async def refresh(request: RefreshRequest, service: AuthServiceDep) -> TokenPairResponse:
    try:
        return await service.refresh(request)
    except InvalidRefreshSessionError as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "invalid_refresh_token", "message": "Сеанс завершён"},
        ) from error
