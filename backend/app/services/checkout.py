"""Покупка: создать платёж, дождаться оплаты, выдать подписку.

Платёж записывается в базу до похода в Platega. Если Platega не ответит, у
нас всё равно останется след с суммой и почтой — иначе деньги могли бы уйти
по ссылке, о существовании которой сайт ничего не знает.
"""

import logging
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.integrations.platega.client import (
    PlategaGateway,
    PlategaNotConfiguredError,
    PlategaUnavailableError,
)
from app.models.billing import Payment, PaymentPurpose, PaymentStatus
from app.schemas.cabinet import PaymentStatusResponse
from app.services.shop import (
    ShopCatalogue,
    ShopUnavailableError,
    UnknownTariffError,
)

logger = logging.getLogger(__name__)

KOPECKS_IN_RUBLE = 100
PROVIDER = "platega"


class CheckoutNotConfiguredError(RuntimeError):
    """Касса не настроена."""


class CheckoutUnavailableError(RuntimeError):
    """Платёжная система или витрина недоступны."""


@dataclass(frozen=True)
class StartedCheckout:
    """Начатая покупка: наш платёж и ссылка, куда идти платить."""

    payment_id: UUID
    redirect_url: str


class CheckoutService:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self._session = session
        self._settings = settings

    async def start(
        self,
        *,
        email: str,
        tariff_id: int,
        period_days: int,
    ) -> StartedCheckout:
        """Создать платёж и вернуть ссылку на оплату."""
        if not self._settings.is_platega_configured:
            raise CheckoutNotConfiguredError("Platega is not configured")

        async with ShopCatalogue(self._settings) as shop:
            try:
                amount_kopecks = await shop.price_kopecks(
                    tariff_id, period_days
                )
                name = await shop.tariff_name(tariff_id)
            except ShopUnavailableError as error:
                raise CheckoutUnavailableError(str(error)) from error

        payment = Payment(
            user_id=None,
            contact_email=email,
            amount_kopecks=amount_kopecks,
            status=PaymentStatus.PENDING,
            purpose=PaymentPurpose.SUBSCRIPTION,
            provider=PROVIDER,
            description=f"{name}, {period_days} дн.",
            tariff_id=tariff_id,
            period_days=period_days,
        )
        self._session.add(payment)
        await self._session.flush()

        origin = (
            self._settings.allowed_origins[0]
            if self._settings.allowed_origins
            else ""
        ).rstrip("/")

        try:
            async with PlategaGateway(self._settings) as platega:
                created = await platega.create_payment(
                    amount_rubles=amount_kopecks / KOPECKS_IN_RUBLE,
                    description=payment.description,
                    payload=str(payment.id),
                    return_url=f"{origin}/pay/{payment.id}",
                    failed_url=f"{origin}/pay/{payment.id}?failed=1",
                )
        except PlategaNotConfiguredError as error:
            raise CheckoutNotConfiguredError(str(error)) from error
        except PlategaUnavailableError as error:
            # Платёж помечаем несостоявшимся: висящий pending без
            # идентификатора у Platega никогда не подтвердится.
            payment.status = PaymentStatus.FAILED
            await self._session.commit()
            raise CheckoutUnavailableError(str(error)) from error

        payment.provider_payment_id = created.id
        await self._session.commit()

        return StartedCheckout(
            payment_id=payment.id,
            redirect_url=created.redirect_url,
        )

    async def state(self, payment_id: UUID) -> PaymentStatusResponse | None:
        """Состояние платежа для страницы результата."""
        payment = await self._session.get(Payment, payment_id)
        if payment is None:
            return None
        return PaymentStatusResponse(
            status=payment.status.value,
            paid=payment.status is PaymentStatus.SUCCEEDED,
            subscription_url=payment.subscription_url,
        )

    async def _by_provider_id(
        self,
        provider_payment_id: str,
    ) -> Payment | None:
        statement = select(Payment).where(
            Payment.provider == PROVIDER,
            Payment.provider_payment_id == provider_payment_id,
        )
        return await self._session.scalar(statement)


__all__ = [
    "CheckoutNotConfiguredError",
    "CheckoutService",
    "CheckoutUnavailableError",
    "StartedCheckout",
    "UnknownTariffError",
]
