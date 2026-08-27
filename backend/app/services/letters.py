"""Тексты писем покупателю.

Отделены от отправки намеренно: содержание письма — это то, что читает
живой человек, и его надо проверять тестами, не поднимая почтовый сервер.

Главное правило здесь одно: в письме лежит **сама ссылка на подписку**, а
не приглашение куда-то зайти. Человек, оплативший по СБП, заканчивает в
приложении банка, вкладку с результатом теряет и до кабинета не доходит —
письмо остаётся единственным, что у него есть.
"""

from dataclasses import dataclass
from datetime import date
from html import escape

__all__ = [
    "Letter",
    "password_reset_letter",
    "subscription_ready_letter",
    "support_alert_letter",
]

APP_IPHONE = "https://apps.apple.com/ru/app/incy/id6756943388"
APP_ANDROID = "https://play.google.com/store/apps/details?id=com.happproxy"


@dataclass(frozen=True)
class Letter:
    """Письмо в двух видах: простым текстом и разметкой."""

    subject: str
    text: str
    html: str


def subscription_ready_letter(
    *,
    subscription_url: str,
    expires_at: date,
    support_url: str,
    support_email: str,
    max_url: str,
) -> Letter:
    """Письмо о готовой подписке."""
    until = expires_at.strftime("%d.%m.%Y")

    text = f"""Подписка VPaNfi готова.

Вот ваша ссылка — скопируйте её целиком:

{subscription_url}

Что с ней делать: установите приложение и вставьте эту ссылку в него.
Сама по себе ссылка ничего не включает.

  iPhone и iPad — INCY: {APP_IPHONE}
  Android — HAPP: {APP_ANDROID}

Подписка действует до {until}.

Сохраните это письмо: та же ссылка понадобится, чтобы подключить
другое устройство.

Если что-то не получается, напишите нам:

  Почта: {support_email} — работает без VPN
  MAX: {max_url}
  Telegram: {support_url} — нужен включённый VPN
"""

    safe_url = escape(subscription_url, quote=True)
    safe_support = escape(support_url, quote=True)
    safe_mail = escape(support_email, quote=True)
    safe_max = escape(max_url, quote=True)
    html = f"""<!DOCTYPE html>
<html lang="ru">
<head><meta charset="utf-8"></head>
<body style="margin:0;padding:24px;background:#f6f5f2;
             font-family:-apple-system,Segoe UI,Roboto,sans-serif;
             color:#1c1c1c;">
  <div style="max-width:560px;margin:0 auto;background:#ffffff;
              border-radius:16px;padding:28px;">
    <h1 style="font-size:22px;margin:0 0 16px;">Подписка VPaNfi готова</h1>

    <p style="margin:0 0 8px;">Вот ваша ссылка — скопируйте её целиком:</p>
    <p style="margin:0 0 20px;padding:14px;background:#f2f1ee;
              border-radius:12px;word-break:break-all;font-size:14px;">
      <a href="{safe_url}"
         style="color:#5b53d6;">{escape(subscription_url)}</a>
    </p>

    <p style="margin:0 0 16px;">Установите приложение и вставьте эту ссылку
      в него. Сама по себе ссылка ничего не включает.</p>

    <p style="margin:0 0 20px;">
      <a href="{APP_IPHONE}"
         style="color:#5b53d6;">iPhone и iPad — INCY</a><br>
      <a href="{APP_ANDROID}" style="color:#5b53d6;">Android — HAPP</a>
    </p>

    <p style="margin:0 0 16px;">Подписка действует до
      <strong>{until}</strong>.</p>

    <p style="margin:0 0 16px;color:#6b6b6b;font-size:14px;">Сохраните это
      письмо: та же ссылка понадобится, чтобы подключить другое
      устройство.</p>

    <p style="margin:0 0 8px;color:#6b6b6b;font-size:14px;">Если что-то не
      получается, напишите нам:</p>
    <p style="margin:0;color:#6b6b6b;font-size:14px;line-height:1.8;">
      <a href="mailto:{safe_mail}"
         style="color:#5b53d6;">{escape(support_email)}</a>
      — почта, работает без VPN<br>
      <a href="{safe_max}" style="color:#5b53d6;">MAX</a>
      — мессенджер, тоже без VPN<br>
      <a href="{safe_support}"
         style="color:#5b53d6;">{escape(support_url)}</a>
      — telegram, нужен включённый VPN
    </p>
  </div>
</body>
</html>"""

    return Letter(
        subject="Ваша подписка VPaNfi готова",
        text=text,
        html=html,
    )


def support_alert_letter(
    *,
    ticket_id: str,
    subject: str,
    category: str,
    message: str,
    author_name: str,
    author_email: str,
) -> Letter:
    """Письмо владельцу сервиса о новом обращении.

    Обращение целиком лежит в теле письма, а не за ссылкой в кабинет:
    отвечать чаще приходится с телефона, и лишний вход ради двух строк
    означает, что письмо отложат «на потом».

    Обратный адрес человека вынесен наверх — ответить надо ему, а не
    в пустоту.
    """
    text = f"""Новое обращение в поддержку.

От кого: {author_name} <{author_email}>
Тема: {subject}
Раздел: {category}

{message}

--
Обращение {ticket_id}
"""

    safe_mail = escape(author_email, quote=True)
    html = f"""<!DOCTYPE html>
<html lang="ru">
<head><meta charset="utf-8"></head>
<body style="margin:0;padding:24px;background:#f6f5f2;
             font-family:-apple-system,Segoe UI,Roboto,sans-serif;
             color:#1c1c1c;">
  <div style="max-width:560px;margin:0 auto;background:#ffffff;
              border-radius:16px;padding:28px;">
    <h1 style="font-size:20px;margin:0 0 16px;">Новое обращение</h1>

    <p style="margin:0 0 4px;font-size:14px;color:#6b6b6b;">От кого</p>
    <p style="margin:0 0 16px;">
      {escape(author_name)} —
      <a href="mailto:{safe_mail}"
         style="color:#5b53d6;">{escape(author_email)}</a>
    </p>

    <p style="margin:0 0 4px;font-size:14px;color:#6b6b6b;">Раздел</p>
    <p style="margin:0 0 16px;">{escape(category)}</p>

    <p style="margin:0 0 8px;font-size:14px;color:#6b6b6b;">Сообщение</p>
    <p style="margin:0 0 20px;padding:14px;background:#f2f1ee;
              border-radius:12px;white-space:pre-wrap;">{escape(message)}</p>

    <p style="margin:0;color:#9a9a9a;font-size:12px;">
      Обращение {escape(ticket_id)}</p>
  </div>
</body>
</html>"""

    return Letter(
        subject=f"Поддержка VPaNfi: {subject}",
        text=text,
        html=html,
    )


def password_reset_letter(
    *,
    reset_url: str,
    ttl_minutes: int,
    support_url: str,
    support_email: str,
) -> Letter:
    """Письмо со ссылкой на смену пароля.

    Срок жизни ссылки назван прямо в письме: человек, открывший его
    назавтра, должен понимать, почему ссылка не сработала, а не
    решить, что сломался сайт.

    Строка про «если это были не Вы» здесь не формальность: письмо
    может прийти тому, кого никто не просил ничего восстанавливать,
    и ему надо сказать, что делать. Делать не надо ничего.
    """
    safe_url = escape(reset_url, quote=True)
    hours = ttl_minutes // 60
    if hours >= 1:
        srok = "час" if hours == 1 else f"{hours} ч."
    else:
        srok = f"{ttl_minutes} мин."

    text = f"""Здравствуйте!

Вы попросили сменить пароль в кабинете VPaNfi.

Откройте ссылку и придумайте новый пароль:
{reset_url}

Ссылка действует {srok}. После смены пароля она перестанет работать,
а все входы в кабинет придётся выполнить заново.

Если Вы ничего не просили, просто удалите это письмо: пароль
останется прежним, делать ничего не нужно.

Не получается? Напишите нам:
   {support_url}
   {support_email}

Анфиса, VPaNfi
"""

    html = f"""<!doctype html>
<html lang="ru">
<body style="margin:0;padding:24px;background:#f7f6f3;
             font-family:-apple-system,Segoe UI,Roboto,sans-serif;
             color:#22201d;line-height:1.6;">
  <div style="max-width:520px;margin:0 auto;padding:28px;
              background:#ffffff;border-radius:16px;">
    <h1 style="margin:0 0 16px;font-size:22px;">Смена пароля</h1>

    <p style="margin:0 0 20px;">
      Вы попросили сменить пароль в кабинете VPaNfi.</p>

    <p style="margin:0 0 24px;">
      <a href="{safe_url}"
         style="display:inline-block;padding:12px 22px;background:#5b53d6;
                color:#ffffff;text-decoration:none;border-radius:12px;
                font-weight:600;">Придумать новый пароль</a></p>

    <p style="margin:0 0 20px;font-size:14px;color:#6b6b6b;">
      Ссылка действует {escape(srok)}. После смены пароля она перестанет
      работать, а все входы в кабинет придётся выполнить заново.</p>

    <p style="margin:0 0 20px;padding:14px;background:#f2f1ee;
              border-radius:12px;font-size:14px;">
      Если Вы ничего не просили, просто удалите это письмо: пароль
      останется прежним, делать ничего не нужно.</p>

    <p style="margin:0;font-size:14px;color:#6b6b6b;">
      Не получается? Напишите нам:
      <a href="{escape(support_url, quote=True)}"
         style="color:#5b53d6;">в Телеграм</a> или на
      <a href="mailto:{escape(support_email, quote=True)}"
         style="color:#5b53d6;">{escape(support_email)}</a>.</p>
  </div>
</body>
</html>"""

    return Letter(
        subject="Смена пароля в кабинете VPaNfi",
        text=text,
        html=html,
    )
