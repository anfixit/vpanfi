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
    PaymentMethodResponse,
    PaymentStatusResponse,
)
from app.services.checkout import (
    CheckoutNotConfiguredError,
    CheckoutService,
    CheckoutUnavailableError,
    UnknownPaymentMethodError,
)
from app.services.payment_methods import known_methods
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
            payment_method=payload.payment_method,
            referral_code=payload.ref,
        )
    except CheckoutNotConfiguredError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "payments_not_configured",
                "message": "Оплата на сайте пока не подключена",
            },
        ) from error
    except UnknownPaymentMethodError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "payment_method_not_available",
                "message": "Такой способ оплаты сейчас недоступен",
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
    "/methods",
    response_model=list[PaymentMethodResponse],
    summary="Способы оплаты, доступные покупателю",
)
async def payment_methods(
    settings: SettingsDep,
) -> list[PaymentMethodResponse]:
    """Что показать на экране оплаты.

    Объявлен выше маршрута с ``payment_id``: FastAPI разбирает пути
    по порядку, и иначе «methods» уехало бы в разбор UUID и вернуло
    бы 422 вместо списка.
    """
    return [
        PaymentMethodResponse(
            code=method.code,
            name=method.name,
            description=method.description,
        )
        for method in known_methods(settings.payment_method_types)
    ]


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
    "/yookassa/webhook",
    summary="Уведомление ЮKassa об оплате",
    include_in_schema=False,
)
async def yookassa_webhook(
    request: Request,
    checkout: CheckoutServiceDep,
) -> Response:
    """Принять уведомление об оплате.

    ЮKassa уведомления не подписывает, и адрес вебхука знает кто угодно.
    Поэтому из тела берётся ровно одно поле — идентификатор платежа, а
    состояние и сумму ``confirm`` спрашивает у самой кассы.

    Ответ почти всегда 200: на любой другой код ЮKassa будет слать
    уведомление снова. Исключение одно — касса не ответила: тогда повтор
    как раз и нужен, иначе оплата потеряется молча.
    """
    body = await request.body()

    # Пустой запрос по адресу вебхука ошибкой не считаем.
    if not body.strip():
        return Response(status_code=status.HTTP_200_OK)

    try:
        payload = jsonlib.loads(body)
    except ValueError:
        return Response(status_code=status.HTTP_400_BAD_REQUEST)

    obj = payload.get("object") if isinstance(payload, dict) else None
    identifier = str(obj.get("id") or "") if isinstance(obj, dict) else ""
    if not identifier:
        # Повторять такое уведомление бессмысленно: разбирать нечего.
        return Response(status_code=status.HTTP_200_OK)

    try:
        paid = await checkout.confirm(provider_payment_id=identifier)
    except CheckoutUnavailableError:
        return Response(status_code=status.HTTP_503_SERVICE_UNAVAILABLE)
    except CheckoutNotConfiguredError:
        return Response(status_code=status.HTTP_503_SERVICE_UNAVAILABLE)

    # Подписку выдаём тому вызову, который сам перевёл платёж в succeeded:
    # ЮKassa присылает уведомление несколько раз, и повтор не должен
    # продлевать. Исключение одно: если в прошлый раз панель не ответила,
    # платёж оплачен, а ссылки нет, и повтор вебхука довыдаёт подписку.
    if paid or await checkout.needs_delivery(provider_payment_id=identifier):
        await checkout.deliver(provider_payment_id=identifier)

    return Response(status_code=status.HTTP_200_OK)
