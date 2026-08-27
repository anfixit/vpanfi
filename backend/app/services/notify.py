"""Сообщения владельцу сервиса о том, что происходит на сайте.

Бот продаж давно шлёт такие уведомления, а сайт молчал: покупку через
vpanfi.su можно было заметить только заглянув в панель. 24.08.2026 из-за
этого сутки не замечали, что человек оплатил и не смог подключиться —
подписку выдали без сквада, и в ней не было ни одного сервера.

Отправка намеренно не умеет ронять покупку: деньги уже приняты, и
недоставленное сообщение не повод отвечать платёжной системе ошибкой.
"""

import asyncio
import html
import logging
from datetime import date

import httpx

from app.core.config import Settings

logger = logging.getLogger(__name__)

__all__ = [
    "TelegramNotifier",
    "pokupka_soobshchenie",
    "registraciya_soobshchenie",
    "sboj_vydachi_soobshchenie",
    "vhod_soobshchenie",
]

TELEGRAM_API = "https://api.telegram.org"
SEND_TIMEOUT_SECONDS = 10.0

# Фоновые отправки держим за хвост: без ссылки задачу может собрать
# сборщик мусора прямо посреди запроса, и сообщение молча пропадёт.
_zadachi: set[asyncio.Task[bool]] = set()


def _rub(kopecks: int) -> str:
    return f"{kopecks / 100:,.0f}".replace(",", " ")


def pokupka_soobshchenie(
    *,
    email: str,
    amount_kopecks: int,
    description: str,
    expires_at: date,
    is_new: bool,
    subscription_url: str | None,
) -> str:
    """Сообщение об успешной покупке."""
    kto = "🆕 Новый покупатель" if is_new else "🔁 Продление"
    lines = [
        "💰 <b>ПОКУПКА НА САЙТЕ</b>",
        "",
        f"👤 {html.escape(email)}",
        f"💳 {kto}",
        "",
        f"💵 <b>{_rub(amount_kopecks)} ₽</b> · {html.escape(description)}",
        f"📆 Действует до: {expires_at.strftime('%d.%m.%Y')}",
    ]
    if subscription_url:
        lines += ["", "✅ Подписка выдана, ссылка отправлена на почту"]
    else:
        lines += ["", "⚠️ Ссылка подписки пуста — проверь панель"]
    return "\n".join(lines)


def registraciya_soobshchenie(
    *, email: str, display_name: str, trial_granted: bool
) -> str:
    """Сообщение о новом человеке на сайте.

    Про выданный триал говорим прямо: с 13 по 25 августа его не
    выдавали вовсе, и заметить это можно было только по жалобам,
    которых не было, потому что люди просто уходили.
    """
    lines = [
        "🆕 <b>РЕГИСТРАЦИЯ НА САЙТЕ</b>",
        "",
        f"👤 {html.escape(display_name)}",
        f"✉️ {html.escape(email)}",
    ]
    if trial_granted:
        lines += ["", "🎁 Пробные дни выданы, доступ работает"]
    else:
        lines += ["", "⚠️ Пробные дни НЕ выданы — проверь панель и журнал"]
    return "\n".join(lines)


def vhod_soobshchenie(*, email: str, display_name: str) -> str:
    """Сообщение о входе в кабинет."""
    return "\n".join([
        "🔑 <b>ВХОД В КАБИНЕТ</b>",
        "",
        f"👤 {html.escape(display_name)}",
        f"✉️ {html.escape(email)}",
    ])


def sboj_vydachi_soobshchenie(
    *, email: str, amount_kopecks: int, prichina: str
) -> str:
    """Сообщение о том, что деньги взяли, а доступ не выдали.

    Отдельным видом намеренно: это единственный случай, когда человек уже
    заплатил и остался ни с чем. Такое надо чинить руками и сразу.
    """
    return "\n".join([
        "🔴 <b>ОПЛАТА ПРОШЛА, ДОСТУП НЕ ВЫДАН</b>",
        "",
        f"👤 {html.escape(email)}",
        f"💵 {_rub(amount_kopecks)} ₽",
        "",
        f"<b>Причина.</b> {html.escape(prichina)}",
        "",
        "Человек заплатил и ничего не получил. "
        "Выдать доступ вручную в панели и написать ему.",
    ])


class TelegramNotifier:
    """Отправляет сообщения владельцу. Молчит, если не настроен."""

    def __init__(self, settings: Settings) -> None:
        self._token = (
            settings.telegram_alert_bot_token.get_secret_value()
            if settings.telegram_alert_bot_token
            else None
        )
        self._chat_id = settings.telegram_alert_chat_id

    @property
    def is_configured(self) -> bool:
        return bool(self._token and self._chat_id)

    def send_later(self, text: str) -> None:
        """Отправить, не задерживая человека.

        Регистрация и вход не должны ждать телеграм: он может
        отвечать долго или не отвечать вовсе, а человек в это время
        смотрит на крутящуюся кнопку.
        """
        if not self.is_configured:
            return
        try:
            zadacha = asyncio.create_task(self.send(text))
        except RuntimeError:
            # Нет запущенного цикла: значит, зовут не из запроса.
            logger.warning("Уведомление не отправлено: нет цикла событий")
            return
        _zadachi.add(zadacha)
        zadacha.add_done_callback(_zadachi.discard)

    async def send(self, text: str) -> bool:
        """Отправить. Возвращает, дошло ли. Исключений не выпускает."""
        if not self.is_configured:
            logger.info("Уведомления в телеграм не настроены — пропускаю")
            return False
        try:
            timeout = SEND_TIMEOUT_SECONDS
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(
                    f"{TELEGRAM_API}/bot{self._token}/sendMessage",
                    json={
                        "chat_id": self._chat_id,
                        "text": text,
                        "parse_mode": "HTML",
                        "disable_web_page_preview": True,
                    },
                )
        except httpx.HTTPError:
            logger.exception("Уведомление в телеграм не ушло")
            return False

        if response.status_code != 200:
            logger.warning(
                "Телеграм отказал: %s %s",
                response.status_code,
                response.text[:200],
            )
            return False
        return True
