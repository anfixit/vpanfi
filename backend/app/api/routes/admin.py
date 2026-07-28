from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.dependencies import CurrentAdmin, get_admin_service
from app.schemas.admin import (
    AdminOverviewResponse,
    AdminUserResponse,
    ExtendSubscriptionRequest,
    GrantTrialRequest,
)
from app.services.admin import AdminService, UsernameAlreadyTakenError
from app.services.subscription import (
    PanelUnavailableError,
    SubscriptionNotFoundError,
)

router = APIRouter(prefix="/admin", tags=["admin"])
AdminServiceDep = Annotated[AdminService, Depends(get_admin_service)]

MAX_USERS_LIMIT = 200

FORBIDDEN_RESPONSES = {
    401: {"description": "Требуется вход"},
    403: {"description": "Доступно только администратору"},
}


def _panel_unavailable() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail={
            "code": "panel_unavailable",
            "message": "Панель сейчас недоступна, попробуйте чуть позже",
        },
    )


def _user_not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={
            "code": "user_not_found",
            "message": "Пользователь или его подписка не найдены",
        },
    )


@router.get(
    "/overview",
    response_model=AdminOverviewResponse,
    summary="Показатели сервиса",
    responses=FORBIDDEN_RESPONSES,
)
async def get_overview(
    admin: CurrentAdmin,
    service: AdminServiceDep,
) -> AdminOverviewResponse:
    _ = admin
    return await service.overview()


@router.get(
    "/users",
    response_model=list[AdminUserResponse],
    summary="Пользователи кабинета",
    responses=FORBIDDEN_RESPONSES,
)
async def list_users(
    admin: CurrentAdmin,
    service: AdminServiceDep,
    search: Annotated[str | None, Query(max_length=200)] = None,
    limit: Annotated[int, Query(ge=1, le=MAX_USERS_LIMIT)] = 50,
) -> list[AdminUserResponse]:
    _ = admin
    return await service.list_users(search=search, limit=limit)


@router.post(
    "/users/{user_id}/subscription/extend",
    response_model=AdminUserResponse,
    summary="Продлить подписку пользователя",
    description=(
        "Двигает дату окончания в панели. Живёт в административном "
        "разделе намеренно: без платёжного провайдера самостоятельное "
        "продление означало бы бесплатный доступ для любого желающего."
    ),
    responses=FORBIDDEN_RESPONSES
    | {
        404: {"description": "Пользователь или подписка не найдены"},
        503: {"description": "Панель недоступна"},
    },
)
async def extend_subscription(
    user_id: UUID,
    request: ExtendSubscriptionRequest,
    admin: CurrentAdmin,
    service: AdminServiceDep,
) -> AdminUserResponse:
    _ = admin
    try:
        return await service.extend_subscription(user_id, request.days)
    except SubscriptionNotFoundError as error:
        raise _user_not_found() from error
    except PanelUnavailableError as error:
        raise _panel_unavailable() from error


@router.post(
    "/users/{user_id}/subscription/trial",
    response_model=AdminUserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Завести подписку в панели и привязать её",
    responses=FORBIDDEN_RESPONSES
    | {
        404: {"description": "Пользователь не найден"},
        409: {"description": "Имя занято в панели"},
        503: {"description": "Панель недоступна"},
    },
)
async def grant_trial(
    user_id: UUID,
    request: GrantTrialRequest,
    admin: CurrentAdmin,
    service: AdminServiceDep,
) -> AdminUserResponse:
    _ = admin
    try:
        return await service.grant_trial(
            user_id,
            username=request.username,
            days=request.days,
        )
    except UsernameAlreadyTakenError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "panel_username_taken",
                "message": "Такое имя уже занято в панели",
            },
        ) from error
    except SubscriptionNotFoundError as error:
        raise _user_not_found() from error
    except PanelUnavailableError as error:
        raise _panel_unavailable() from error
