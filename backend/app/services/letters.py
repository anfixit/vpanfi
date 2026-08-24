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

__all__ = ["Letter", "subscription_ready_letter"]

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
