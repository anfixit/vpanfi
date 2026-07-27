from typing import Annotated

from fastapi import APIRouter, Depends, Response, status

from app.api.dependencies import CurrentUser, get_cabinet_service
from app.schemas.cabinet import (
    ConnectionClientResponse,
    DashboardResponse,
    DeviceResponse,
    PaymentResponse,
)
from app.services.cabinet import CabinetService

router = APIRouter(prefix="/cabinet", tags=["cabinet"])
CabinetServiceDep = Annotated[CabinetService, Depends(get_cabinet_service)]

UNAUTHORIZED_RESPONSE = {401: {"description": "Требуется вход в кабинет"}}


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
