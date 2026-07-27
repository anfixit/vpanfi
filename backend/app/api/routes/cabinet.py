from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status

from app.api.dependencies import (
    CurrentUser,
    get_cabinet_service,
    get_subscription_service,
)
from app.schemas.cabinet import (
    ConnectionClientResponse,
    DashboardResponse,
    DeviceResponse,
    PaymentResponse,
    SubscriptionLinkRequest,
    SubscriptionLinkResponse,
)
from app.services.cabinet import CabinetService
from app.services.subscription import (
    PanelUnavailableError,
    SubscriptionAlreadyClaimedError,
    SubscriptionLinkInvalidError,
    SubscriptionNotFoundError,
    SubscriptionService,
)

router = APIRouter(prefix="/cabinet", tags=["cabinet"])
CabinetServiceDep = Annotated[CabinetService, Depends(get_cabinet_service)]

SubscriptionServiceDep = Annotated[
    SubscriptionService, Depends(get_subscription_service)
]

UNAUTHORIZED_RESPONSE = {401: {"description": "Требуется вход в кабинет"}}


def _panel_unavailable() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail={
            "code": "panel_unavailable",
            "message": (
                "Панель сейчас недоступна, попробуйте чуть позже"
            ),
        },
    )


@router.get(
    "/dashboard",
    response_model=DashboardResponse,
    summary="Сводка кабинета",
    description=(
        "Подписка, страны, последние платежи и профиль. Пока панель "
        "Remnawave не подключена, отдаются демонстрационные данные."
    ),
    responses=UNAUTHORIZED_RESPONSE,
)
async def get_dashboard(
    user: CurrentUser,
    service: CabinetServiceDep,
) -> DashboardResponse:
    _ = user
    return await service.get_demo_dashboard()


@router.get(
    "/devices",
    response_model=list[DeviceResponse],
    summary="Устройства пользователя",
    responses=UNAUTHORIZED_RESPONSE,
)
async def get_devices(
    user: CurrentUser,
    service: CabinetServiceDep,
) -> list[DeviceResponse]:
    _ = user
    return service.get_demo_devices()


@router.delete(
    "/devices/{device_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Отвязать устройство",
    responses=UNAUTHORIZED_RESPONSE,
)
async def unlink_device(
    device_id: str,
    user: CurrentUser,
    service: CabinetServiceDep,
) -> Response:
    # The real implementation will validate ownership and call the
    # Remnawave HWID endpoint. The route and its contract are ready now.
    _ = (device_id, user, service)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/payments",
    response_model=list[PaymentResponse],
    summary="История платежей",
    responses=UNAUTHORIZED_RESPONSE,
)
async def get_payments(
    user: CurrentUser,
    service: CabinetServiceDep,
) -> list[PaymentResponse]:
    _ = user
    return service.get_demo_payments()


@router.get(
    "/connection-clients",
    response_model=list[ConnectionClientResponse],
    summary="Приложения для подключения",
    description=(
        "Список не зависит от пользователя, поэтому доступен без входа: "
        "инструкция по подключению нужна и на публичных страницах."
    ),
)
async def get_connection_clients(
    service: CabinetServiceDep,
) -> list[ConnectionClientResponse]:
    return service.get_connection_clients()


@router.get(
    "/subscription",
    response_model=SubscriptionLinkResponse,
    summary="Состояние привязанной подписки",
    responses=UNAUTHORIZED_RESPONSE
    | {503: {"description": "Панель недоступна"}},
)
async def get_subscription(
    user: CurrentUser,
    service: SubscriptionServiceDep,
) -> SubscriptionLinkResponse:
    try:
        return await service.describe(user)
    except PanelUnavailableError as error:
        raise _panel_unavailable() from error


@router.post(
    "/subscription/link",
    response_model=SubscriptionLinkResponse,
    summary="Привязать подписку по ссылке",
    description=(
        "Принимает ссылку на подписку из бота или её идентификатор. "
        "Панель остаётся источником правды: кабинет запоминает только "
        "ссылку на пользователя панели."
    ),
    responses=UNAUTHORIZED_RESPONSE
    | {
        404: {"description": "Подписка не найдена"},
        409: {"description": "Подписка уже привязана к другому аккаунту"},
        422: {"description": "Ссылку не удалось разобрать"},
        503: {"description": "Панель недоступна"},
    },
)
async def link_subscription(
    request: SubscriptionLinkRequest,
    user: CurrentUser,
    service: SubscriptionServiceDep,
) -> SubscriptionLinkResponse:
    try:
        return await service.link(user, request.subscription_link)
    except SubscriptionLinkInvalidError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={
                "code": "invalid_subscription_link",
                "message": (
                    "Это не похоже на ссылку подписки. Скопируйте её "
                    "целиком из бота."
                ),
            },
        ) from error
    except SubscriptionNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "subscription_not_found",
                "message": "Такая подписка не найдена",
            },
        ) from error
    except SubscriptionAlreadyClaimedError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "subscription_already_claimed",
                "message": "Эта подписка уже привязана к другому аккаунту",
            },
        ) from error
    except PanelUnavailableError as error:
        raise _panel_unavailable() from error


@router.delete(
    "/subscription/link",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Отвязать подписку от аккаунта",
    description="Подписка в панели сохраняется, снимается только связь.",
    responses=UNAUTHORIZED_RESPONSE,
)
async def unlink_subscription(
    user: CurrentUser,
    service: SubscriptionServiceDep,
) -> Response:
    await service.unlink(user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
