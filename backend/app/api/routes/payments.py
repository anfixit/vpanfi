from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies import get_checkout_service
from app.schemas.cabinet import (
    CheckoutRequest,
    CheckoutResponse,
    PaymentStatusResponse,
)
from app.services.checkout import (
    CheckoutNotConfiguredError,
    CheckoutService,
    CheckoutUnavailableError,
)
from app.services.shop import UnknownTariffError

router = APIRouter(prefix="/payments", tags=["payments"])
CheckoutServiceDep = Annotated[CheckoutService, Depends(get_checkout_service)]


@router.post(
    "/checkout",
    response_model=CheckoutResponse,
    summary="Создать платёж и получить ссылку на оплату",
)
async def start_checkout(
    payload: CheckoutRequest,
    checkout: CheckoutServiceDep,
) -> CheckoutResponse:
    try:
        started = await checkout.start(
            email=payload.email,
            tariff_id=payload.tariff_id,
            period_days=payload.period_days,
        )
    except CheckoutNotConfiguredError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "payments_not_configured",
                "message": "Оплата на сайте пока не подключена",
            },
        ) from error
    except UnknownTariffError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "tariff_not_found",
                "message": "Такого тарифа нет",
            },
        ) from error
    except CheckoutUnavailableError as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "code": "payments_unavailable",
                "message": (
                    "Платёжная система не отвечает, попробуйте ещё раз"
                ),
            },
        ) from error

    return CheckoutResponse(
        payment_id=started.payment_id,
        redirect_url=started.redirect_url,
    )


@router.get(
    "/{payment_id}",
    response_model=PaymentStatusResponse,
    summary="Состояние платежа",
)
async def payment_status(
    payment_id: UUID,
    checkout: CheckoutServiceDep,
) -> PaymentStatusResponse:
    state = await checkout.state(payment_id)
    if state is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "payment_not_found",
                "message": "Платёж не найден",
            },
        )
    return state
