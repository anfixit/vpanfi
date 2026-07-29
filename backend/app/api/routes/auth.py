from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status

from app.api.dependencies import (
    CurrentUser,
    get_auth_service,
    get_cabinet_service,
)
from app.core.config import get_settings
from app.schemas.auth import (
    AccessTokenResponse,
    ChangePasswordRequest,
    DeleteAccountRequest,
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    TokenPairResponse,
    UpdateProfileRequest,
)
from app.schemas.cabinet import UserProfileResponse
from app.services.auth import (
    AuthService,
    EmailAlreadyRegisteredError,
    EmailTakenError,
    InvalidCredentialsError,
    InvalidRefreshSessionError,
    WrongPasswordError,
)
from app.services.cabinet import CabinetService

router = APIRouter(prefix="/auth", tags=["auth"])
AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]
RefreshCookie = Annotated[str | None, Cookie(alias="vpanfi_refresh")]
CabinetServiceDep = Annotated[CabinetService, Depends(get_cabinet_service)]


def set_refresh_cookie(response: Response, tokens: TokenPairResponse) -> None:
    settings = get_settings()
    response.set_cookie(
        key="vpanfi_refresh",
        value=tokens.refresh_token,
        max_age=settings.refresh_token_days * 24 * 60 * 60,
        httponly=True,
        secure=settings.is_production,
        samesite="lax",
        path=f"{settings.api_prefix}/auth",
    )


def public_token_response(tokens: TokenPairResponse) -> AccessTokenResponse:
    return AccessTokenResponse(
        access_token=tokens.access_token,
        token_type=tokens.token_type,
        expires_in=tokens.expires_in,
    )


@router.post(
    "/register",
    response_model=AccessTokenResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register(
    request: RegisterRequest,
    response: Response,
    service: AuthServiceDep,
) -> AccessTokenResponse:
    try:
        tokens = await service.register(request)
    except EmailAlreadyRegisteredError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "email_already_registered",
                "message": "Аккаунт уже существует",
            },
        ) from error

    set_refresh_cookie(response, tokens)
    return public_token_response(tokens)


@router.post("/login", response_model=AccessTokenResponse)
async def login(
    request: LoginRequest,
    response: Response,
    service: AuthServiceDep,
) -> AccessTokenResponse:
    try:
        tokens = await service.login(request)
    except InvalidCredentialsError as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": "invalid_credentials",
                "message": "Неверный email или пароль",
            },
        ) from error

    set_refresh_cookie(response, tokens)
    return public_token_response(tokens)


@router.post("/refresh", response_model=AccessTokenResponse)
async def refresh(
    response: Response,
    refresh_cookie: RefreshCookie,
    service: AuthServiceDep,
) -> AccessTokenResponse:
    if refresh_cookie is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": "missing_refresh_token",
                "message": "Сеанс завершён",
            },
        )

    try:
        tokens = await service.refresh(
            RefreshRequest(refresh_token=refresh_cookie)
        )
    except InvalidRefreshSessionError as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": "invalid_refresh_token",
                "message": "Сеанс завершён",
            },
        ) from error

    set_refresh_cookie(response, tokens)
    return public_token_response(tokens)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(response: Response) -> None:
    settings = get_settings()
    response.delete_cookie(
        key="vpanfi_refresh",
        path=f"{settings.api_prefix}/auth",
        secure=settings.is_production,
        httponly=True,
        samesite="lax",
    )


@router.get(
    "/me",
    response_model=UserProfileResponse,
    summary="Профиль текущего пользователя",
    description=(
        "Нужен интерфейсу, чтобы обращаться к человеку по имени, а не "
        "показывать всем одно и то же."
    ),
    responses={401: {"description": "Требуется вход в кабинет"}},
)
async def get_me(
    user: CurrentUser,
    service: CabinetServiceDep,
) -> UserProfileResponse:
    return service.build_profile(user)


@router.patch(
    "/me",
    response_model=UserProfileResponse,
    summary="Изменить имя и адрес",
    responses={
        401: {"description": "Требуется вход в кабинет"},
        409: {"description": "Адрес занят другим аккаунтом"},
    },
)
async def update_me(
    request: UpdateProfileRequest,
    user: CurrentUser,
    auth: AuthServiceDep,
    service: CabinetServiceDep,
) -> UserProfileResponse:
    try:
        updated = await auth.update_profile(
            user,
            display_name=request.display_name,
            email=request.email,
        )
    except EmailTakenError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "email_already_registered",
                "message": "Этот адрес уже занят другим аккаунтом",
            },
        ) from error

    return service.build_profile(updated)


def _wrong_password() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={
            "code": "wrong_password",
            "message": "Неверный пароль",
        },
    )


@router.post(
    "/password",
    response_model=AccessTokenResponse,
    summary="Сменить пароль",
    description=(
        "Завершает все остальные сеансы и выдаёт этому устройству новую "
        "пару токенов."
    ),
    responses={
        401: {"description": "Требуется вход в кабинет"},
        403: {"description": "Текущий пароль не подошёл"},
    },
)
async def change_password(
    request: ChangePasswordRequest,
    response: Response,
    user: CurrentUser,
    auth: AuthServiceDep,
) -> AccessTokenResponse:
    try:
        tokens = await auth.change_password(
            user,
            current_password=request.current_password,
            new_password=request.new_password,
        )
    except WrongPasswordError as error:
        raise _wrong_password() from error

    set_refresh_cookie(response, tokens)
    return public_token_response(tokens)


@router.delete(
    "/me",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить аккаунт",
    description=(
        "Обезличивает аккаунт и завершает все сеансы. Историю платежей "
        "удалить нельзя, поэтому строка остаётся без личных данных. "
        "Подписка в панели сохраняется: она может быть оплачена."
    ),
    responses={
        401: {"description": "Требуется вход в кабинет"},
        403: {"description": "Пароль не подошёл"},
    },
)
async def delete_account(
    request: DeleteAccountRequest,
    response: Response,
    user: CurrentUser,
    auth: AuthServiceDep,
) -> Response:
    try:
        await auth.delete_account(user, request.password)
    except WrongPasswordError as error:
        raise _wrong_password() from error

    settings = get_settings()
    response.delete_cookie(
        key="vpanfi_refresh",
        path=f"{settings.api_prefix}/auth",
        secure=settings.is_production,
        httponly=True,
        samesite="lax",
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
