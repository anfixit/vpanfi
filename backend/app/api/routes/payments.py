import hmac
import json as jsonlib
from typing import Annotated
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
    Response,
    status,
)

from app.api.dependencies import SettingsDep, get_checkout_service
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


@router.post(
    "/platega/webhook",
    summary="Уведомление Platega об оплате",
    include_in_schema=False,
)
async def platega_webhook(
    request: Request,
    settings: SettingsDep,
    checkout: CheckoutServiceDep,
) -> Response:
    """Принять уведомление об оплате.

    Platega не подписывает уведомления: она присылает мерчанта и секрет,
    и сверять надо именно их. Ответ почти всегда 200 — на любой другой
    код Platega будет слать уведомление снова.
    """
    merchant = request.headers.get("X-MerchantId", "")
    secret = request.headers.get("X-Secret", "")
    body = await request.body()

    # Platega проверяет адрес пустым запросом без заголовков.
    if not merchant and not secret and not body.strip():
        return Response(status_code=status.HTTP_200_OK)

    expected_secret = (
        settings.platega_secret.get_secret_value()
        if settings.platega_secret
        else ""
    )
    # Сравнение с постоянным временем: обычное сравнение строк
    # подсказывает подбирающему, сколько символов он уже угадал.
    authorised = hmac.compare_digest(
        merchant, settings.platega_merchant_id or ""
    ) and hmac.compare_digest(secret, expected_secret)
    if not authorised:
        return Response(status_code=status.HTTP_401_UNAUTHORIZED)

    try:
        payload = jsonlib.loads(body)
    except ValueError:
        return Response(status_code=status.HTTP_400_BAD_REQUEST)

    identifier = str(payload.get("id") or payload.get("Id") or "")
    state = str(payload.get("status") or payload.get("Status") or "")
    if not identifier:
        return Response(status_code=status.HTTP_200_OK)

    await checkout.confirm(
        provider_payment_id=identifier, status_name=state
    )

    return Response(status_code=status.HTTP_200_OK)
