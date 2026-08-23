"""Отправка писем покупателю.

Транспорт отделён от содержания: здесь только «как отправить», а «что
написано» живёт в ``letters``. Берём стандартный ``smtplib`` и уводим его
в поток — ради одного письма после оплаты незачем тащить в зависимости
асинхронный почтовый клиент.
"""

import asyncio
import logging
import smtplib
from email.message import EmailMessage

from app.core.config import Settings
from app.services.letters import Letter

logger = logging.getLogger(__name__)

__all__ = ["MailNotConfiguredError", "Mailer", "build_message"]


class MailNotConfiguredError(RuntimeError):
    """Почтовый узел не описан в настройках."""


def build_message(
    *,
    letter: Letter,
    to_email: str,
    from_email: str,
    from_name: str,
) -> EmailMessage:
    """Собрать письмо в двух видах — текстом и разметкой.

    Простой текст обязателен: часть почтовиков показывает именно его, и
    ссылка должна остаться читаемой даже там.
    """
    message = EmailMessage()
    message["Subject"] = letter.subject
    message["From"] = f"{from_name} <{from_email}>"
    message["To"] = to_email
    message.set_content(letter.text)
    message.add_alternative(letter.html, subtype="html")
    return message


class Mailer:
    """Отправитель писем через настроенный почтовый узел."""

    def __init__(self, settings: Settings) -> None:
        if not settings.is_mail_configured:
            raise MailNotConfiguredError("SMTP host and sender are required")

        self._host = settings.smtp_host or ""
        self._port = settings.smtp_port
        self._user = settings.smtp_user
        self._password = (
            settings.smtp_password.get_secret_value()
            if settings.smtp_password
            else None
        )
        self._use_tls = settings.smtp_use_tls
        self._from_email = settings.smtp_from_email or ""
        self._from_name = settings.smtp_from_name
        self._timeout = settings.smtp_timeout_seconds

    async def send(self, *, to_email: str, letter: Letter) -> bool:
        """Отправить письмо. Возвращает, дошло ли до почтового узла.

        Исключение наружу не выпускаем: письмо — не то, ради чего стоит
        ронять обработку оплаты. Неудача остаётся в логе.
        """
        message = build_message(
            letter=letter,
            to_email=to_email,
            from_email=self._from_email,
            from_name=self._from_name,
        )

        try:
            await asyncio.to_thread(self._deliver, message)
        except (OSError, smtplib.SMTPException):
            logger.exception("Письмо не отправлено: %s", to_email)
            return False

        logger.info("Письмо отправлено: %s", to_email)
        return True

    def _deliver(self, message: EmailMessage) -> None:
        with smtplib.SMTP(
            self._host, self._port, timeout=self._timeout
        ) as smtp:
            if self._use_tls:
                smtp.starttls()
            if self._user and self._password:
                smtp.login(self._user, self._password)
            smtp.send_message(message)
