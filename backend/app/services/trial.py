"""Пробный доступ, который обещает витрина.

Главная страница зовёт «получить 7 дней бесплатно», но выдачи пробного
периода в коде не существовало: регистрация заводила запись в базе и на
этом заканчивалась. Человек нажимал кнопку, оставлял почту и попадал
в кабинет с надписью «Выберите подписку» и тремя ценами.

С 13 по 25 августа 2026 так ушли шестеро: ни одному из них доступ не
достался. Один заходил десять раз подряд, видимо, искал обещанное.

Модуль закрывает разрыв между обещанием и делом.
"""

import logging
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.integrations.remnawave.client import (
    RemnawaveGateway,
    RemnawaveUnavailableError,
    RemnawaveUserNotFoundError,
)
from app.models.user import User
from app.services.checkout import panel_username
from app.services.panel import read_panel_user

logger = logging.getLogger(__name__)

TRIAL_TAG = "TRIAL"


@dataclass(frozen=True)
class TrialGranted:
    """Выданный пробный доступ.

    Ссылка нужна снаружи: без неё письмо получателю писать не о чем,
    а сам он в кабинет не возвращается. С 13.08 по 03.09.2026 четверо
    зарегистрировались, получили доступ и ни разу не открыли ссылку,
    потому что о ней никто не сказал.
    """

    subscription_url: str | None
    expires_at: date


class TrialService:
    """Заводит пробную подписку сразу после регистрации."""

    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self._session = session
        self._settings = settings

    async def grant(self, user: User) -> TrialGranted | None:
        """Выдать пробный доступ. Наверх не бросает ничего и никогда.

        Регистрация не должна падать из-за панели. Человек уже ввёл
        почту и пароль, и потерять из-за недоступного узла сам аккаунт
        куда хуже, чем остаться без пробных дней: аккаунт он заводит
        один раз, а триал можно довыдать руками. Невыданный триал
        виден в журнале.

        Возвращает выданный доступ вместе со ссылкой, либо None.
        """
        if user.remnawave_user_id is not None:
            # Уже привязан: второй вызов не должен плодить дубли
            # в панели. По этой же причине сначала ищем по имени.
            return None

        days = self._settings.trial_days
        if days <= 0:
            return None

        squad = self._settings.remnawave_squad_uuid
        if not squad:
            # Молча завести учётку без сквада хуже, чем не заводить:
            # подписка отдаётся, серверов в ней нет, человек видит
            # пустой список и не понимает, что сломалось.
            logger.error(
                "Пробный доступ не выдан (%s): не задан REMNAWAVE_SQUAD_UUID",
                user.email,
            )
            return None

        username = panel_username(user.email)
        expires_at = datetime.now(UTC) + timedelta(days=days)

        try:
            async with RemnawaveGateway(self._settings) as panel:
                try:
                    # Имя выводится из почты детерминированно, поэтому
                    # учётка может уже существовать: например, человек
                    # покупал раньше, удалил кабинет и завёл заново.
                    # Тогда привязываем её, а не создаём вторую.
                    payload = await panel.get_user_by_username(username)
                except RemnawaveUserNotFoundError:
                    payload = await panel.create_user(
                        username=username,
                        expire_at=expires_at,
                        email=user.email,
                        hwid_device_limit=self._settings.trial_device_limit,
                        active_internal_squads=[squad],
                        tag=TRIAL_TAG,
                    )
        except RemnawaveUnavailableError:
            logger.exception(
                "Пробный доступ не выдан (%s): панель недоступна", user.email
            )
            return None

        panel_user = read_panel_user(payload)
        user.remnawave_user_id = panel_user.id
        user.remnawave_username = panel_user.username or username
        await self._session.commit()
        return TrialGranted(
            subscription_url=panel_user.subscription_url,
            expires_at=panel_user.expires_at or expires_at.date(),
        )
