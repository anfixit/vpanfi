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
    "nagrada_itog_soobshchenie",
    "nagrada_soobshchenie",
    "otmena_oplaty_soobshchenie",
    "pokupka_soobshchenie",
    "registraciya_soobshchenie",
    "sboj_vydachi_soobshchenie",
    "sovpadenie_ustrojstv_soobshchenie",
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


def nagrada_soobshchenie(
    *,
    friend_email: str,
    inviter_username: str,
    status: str,
    kind: str = "first",
    source: str = "site",
) -> str:
    """Сообщение о начисленной награде за приглашение или за продление.

    kind "renewal" значит, что друг не новый: он уже был вознаграждён
    за первую покупку, а теперь просто продлил подписку, и именно это
    продление принесло пригласившему ещё дней. Сам друг тут ничего не
    получает, поэтому и сообщение говорит "продлил", а не "друг".

    source "bot" значит, что покупку завела не касса сайта, а обход
    бота продаж (``ReferralService.sync_bot``): ``friend_email`` тогда
    это не почта, а ключ вида ``tg:<telegram_id>``, потому что у
    друга из бота почты просто нет. Отдельная строка в сообщении не
    даёт спутать этот случай с обычной покупкой на сайте.

    Статус held означает, что пригласивший уже выбрал месячный потолок
    наград: другу дни всё равно ушли (при первой покупке), а решение
    по пригласившему ждёт человека, а не фоновую задачу.
    """
    is_renewal = kind == "renewal"
    lines = [
        (
            "🎁 <b>НАГРАДА ЗА ПРОДЛЕНИЕ ДРУГА</b>"
            if is_renewal
            else "🎁 <b>НАГРАДА ЗА ПРИГЛАШЕНИЕ</b>"
        ),
        "",
        (
            f"👤 Друг продлил подписку: {html.escape(friend_email)}"
            if is_renewal
            else f"👤 Друг: {html.escape(friend_email)}"
        ),
        f"🔗 Пригласил: {html.escape(inviter_username)}",
    ]
    if source == "bot":
        lines.append("📱 Покупка сделана в боте продаж")
    if status == "held":
        lines += [
            "",
            "⏳ У пригласившего потолок наград за месяц, награда "
            "ждёт Вашего решения",
        ]
    else:
        lines += ["", "✅ Награда заведена, дни начисляются"]
    return "\n".join(lines)


def nagrada_itog_soobshchenie(
    *,
    friend_email: str,
    inviter_username: str,
    status: str,
    friend_granted: bool,
    inviter_granted: bool,
    friend_days: int,
    inviter_days: int,
    last_error: str | None,
    kind: str = "first",
) -> str:
    """Сообщение об итоге обработки награды: выдана или сдалась.

    Зовётся ровно на переходе в granted или failed, поэтому status
    здесь всегда один из этих двух и других вариантов не разбирает.

    kind "renewal" значит, что друг ничего не получал (friend_days
    всегда 0): сообщение говорит "продлил подписку", а не называет
    выдачу дней, которой для друга и не было.
    """
    is_renewal = kind == "renewal"
    if status == "granted":
        friend_line = (
            f"👤 Друг продлил подписку: {html.escape(friend_email)}"
            if is_renewal
            else f"👤 Друг: {html.escape(friend_email)}, {friend_days} дн."
        )
        return "\n".join([
            "✅ <b>НАГРАДА ЗА ПРИГЛАШЕНИЕ ВЫДАНА</b>",
            "",
            friend_line,
            f"🔗 Пригласил: {html.escape(inviter_username)}, "
            f"{inviter_days} дн.",
        ])

    friend_hint = (
        "продление не требовалось"
        if is_renewal
        else ("выдано" if friend_granted else "не выдано")
    )
    inviter_hint = "выдано" if inviter_granted else "не выдано"
    lines = [
        "🔴 <b>НАГРАДА ЗА ПРИГЛАШЕНИЕ НЕ ВЫДАНА</b>",
        "",
        f"👤 Друг: {html.escape(friend_email)}, {friend_hint}",
        f"🔗 Пригласил: {html.escape(inviter_username)}, {inviter_hint}",
    ]
    if last_error:
        lines += ["", f"<b>Последняя ошибка.</b> {html.escape(last_error)}"]
    lines += [
        "",
        "Десять попыток кончились. Недостающие дни нужно добавить "
        "вручную в панели или в боте продаж, а после этого награду "
        "можно отклонить через POST /admin/referral-rewards/{id}/reject "
        "либо оставить как есть.",
    ]
    return "\n".join(lines)


def otmena_oplaty_soobshchenie(
    *,
    email: str,
    amount_kopecks: int,
    status_name: str,
    referral_code: str | None,
) -> str:
    """Сообщение о статусе, пришедшем после того, как платёж уже выдан.

    Ничего не меняет само: подписка уже выдана и остаётся выданной,
    сообщение только просит проверить платёж и, если есть код
    приглашения, награду по нему глазами.
    """
    lines = [
        "⚠️ <b>СТАТУС ПОСЛЕ УЖЕ ВЫДАННОЙ ОПЛАТЫ</b>",
        "",
        f"👤 {html.escape(email)}",
        f"💵 {_rub(amount_kopecks)} ₽",
        f"📡 Провайдер прислал статус: {html.escape(status_name)}",
        "",
        "Платёж уже был доставлен раньше, ничего не изменено "
        "автоматически. Стоит проверить платёж вручную.",
    ]
    if referral_code:
        lines += [
            "",
            "У платежа есть код приглашения, награду за него тоже "
            "стоит проверить через GET /admin/referral-rewards.",
        ]
    return "\n".join(lines)


def _ustrojstva_slovo(n: int) -> str:
    """Форма слова «устройство» после числительного n.

    Обычное русское правило: 11-14 и оканчивающиеся на них всегда
    «устройств», иначе по последней цифре: 1 это «устройство», 2-4
    это «устройства», остальное «устройств».
    """
    if 11 <= n % 100 <= 14:
        return "устройств"
    last_digit = n % 10
    if last_digit == 1:
        return "устройство"
    if 2 <= last_digit <= 4:
        return "устройства"
    return "устройств"


def sovpadenie_ustrojstv_soobshchenie(
    *, friend_email: str, inviter_username: str, common: int, status: str
) -> str:
    """Сообщение о совпадении устройств у друга и пригласившего.

    Совпадение само по себе ничего не решает: строка только
    предупреждает человека, а решение (release или reject) он
    принимает через административный раздел сам.
    """
    lines = [
        "⚠️ <b>СОВПАДЕНИЕ УСТРОЙСТВ</b>",
        "",
        f"👤 Друг: {html.escape(friend_email)}",
        f"🔗 Пригласил: {html.escape(inviter_username)}",
        f"📱 Совпадает: {common} {_ustrojstva_slovo(common)}",
        f"📌 Статус награды: {html.escape(status)}",
        "",
        "Ничего не изменено автоматически. Найти запись можно через "
        "GET /admin/referral-rewards?status=held, отклонить через "
        "POST /admin/referral-rewards/{id}/reject.",
    ]
    return "\n".join(lines)


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
