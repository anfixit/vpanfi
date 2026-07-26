from typing import Annotated

from fastapi import APIRouter, Depends, Response, status

from app.api.dependencies import get_cabinet_service
from app.schemas.cabinet import (
    ConnectionClientResponse,
    DashboardResponse,
    DeviceResponse,
    PaymentResponse,
)
from app.services.cabinet import CabinetService

router = APIRouter(prefix="/cabinet", tags=["cabinet"])
CabinetServiceDep = Annotated[CabinetService, Depends(get_cabinet_service)]


@router.get("/dashboard", response_model=DashboardResponse)
async def get_dashboard(service: CabinetServiceDep) -> DashboardResponse:
    return await service.get_demo_dashboard()


@router.get("/devices", response_model=list[DeviceResponse])
async def get_devices(service: CabinetServiceDep) -> list[DeviceResponse]:
    return service.get_demo_devices()


@router.delete("/devices/{device_id}", status_code=status.HTTP_204_NO_CONTENT)
async def unlink_device(device_id: str, service: CabinetServiceDep) -> Response:
    # The real implementation will validate ownership and call the Remnawave
    # HWID/device endpoint. The route and frontend contract are ready now.
    _ = (device_id, service)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/payments", response_model=list[PaymentResponse])
async def get_payments(service: CabinetServiceDep) -> list[PaymentResponse]:
    return service.get_demo_payments()


@router.get("/connection-clients", response_model=list[ConnectionClientResponse])
async def get_connection_clients(
    service: CabinetServiceDep,
) -> list[ConnectionClientResponse]:
    return service.get_connection_clients()
