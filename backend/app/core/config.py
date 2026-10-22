from datetime import UTC, datetime
from functools import lru_cache
from typing import Literal, Self

from pydantic import AnyHttpUrl, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

__all__ = ["Settings", "get_settings"]

DEFAULT_JWT_SECRET = "change-me-before-production"
MIN_JWT_SECRET_LENGTH = 32


class Settings(BaseSettings):
    """Конфигурация VPaNfi из переменных окружения."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="VPANFI_",
        extra="ignore",
    )

    environment: Literal["development", "test", "production"] = "development"
    debug: bool = False
    api_prefix: str = "/api/v1"
    frontend_origin: str = "http://localhost:5173"

    database_url: SecretStr = SecretStr(
        "postgresql+asyncpg://vpanfi:vpanfi@postgres:5432/vpanfi"
    )
    redis_url: SecretStr = SecretStr("redis://redis:6379/0")

    jwt_secret: SecretStr = SecretStr(DEFAULT_JWT_SECRET)
    access_token_minutes: int = 15
    refresh_token_days: int = 30

    remnawave_base_url: AnyHttpUrl | None = None
    remnawave_api_token: SecretStr | None = None
    remnawave_timeout_seconds: float = 10.0

    # Сквад, в который попадает купивший через сайт. Без него ноды не
    # видят пользователя: подписка отдаётся, серверов в ней нет,
    # подключиться нельзя. 24.08.2026 так прошла первая живая продажа.
    remnawave_squad_uuid: str | None = None

    # Пробный доступ, который обещает главная страница. С 13.08 по
    # 25.08.2026 кнопка «получить 7 дней бесплатно» вела на форму
    # регистрации, аккаунт заводился, а доступа не появлялось: выдачи
    # триала в коде не было вовсе. Шесть живых людей ушли ни с чем.
    # Ноль в trial_days выключает выдачу, не трогая витрину.
    trial_days: int = 7
    trial_device_limit: int = 3

    # Касса сайта: ЮKassa. С 22.08.2026 деньги принимала Platega, с
    # 22.10.2026 — ЮKassa; 22.10.2026 через неё прошёл первый боевой
    # платёж, и код прежней кассы удалён. Магазин общий с ботом продаж,
    # но ключ свой: сайт ходит в кассу сам.
    yookassa_shop_id: str | None = None
    yookassa_secret_key: SecretStr | None = None
    yookassa_base_url: AnyHttpUrl = AnyHttpUrl("https://api.yookassa.ru/v3")
    yookassa_timeout_seconds: float = 15.0
    # За сколько дней предупреждать об окончании подписки. Бот шлёт
    # такие письма только тем, кто в нём есть, а покупателя сайта там
    # нет: он платит почтой, без телеграма. Пустой список выключает
    # напоминания целиком.
    reminder_days: str = "7,3,1"
    # Как часто обходить людей. Чаще раза в сутки не нужно, но и реже
    # нельзя: при суточном шаге пропущенный обход съедает целый порог.
    reminder_interval_hours: int = 6

    # Сколько живёт ссылка восстановления пароля. Час это разумный
    # запас: человек успевает дойти до почты, а забытое в чужом ящике
    # письмо перестаёт быть ключом от аккаунта к концу дня.
    password_reset_ttl_minutes: int = 60

    # Способы оплаты ЮKassa — это значения payment_method_data.type:
    # bank_card, sbp, yoo_money, sberbank, tinkoff_bank.
    #
    # Что показываем на выбор. Пусто по умолчанию, и это сознательно:
    # ЮKassa сама покажет на своей странице ровно те способы, которые
    # включены у магазина. Список здесь пришлось бы сверять с кабинетом
    # вручную, а показать выключенный способ значит завести человека
    # в тупик уже после того, как он решился платить. 22.10.2026 у
    # магазина включены карта, ЮMoney, SberPay и T-Pay, а СБП нет.
    yookassa_payment_methods: str = ""

    # Почта. Единственный канал, который переживает оплату по СБП:
    # она заканчивается в приложении банка, и вкладку с результатом
    # человек чаще всего теряет.
    smtp_host: str | None = None
    smtp_port: int = 2525
    smtp_user: str | None = None
    smtp_password: SecretStr | None = None
    smtp_from_email: str | None = None
    smtp_from_name: str = "VPaNfi"
    smtp_use_tls: bool = True
    smtp_timeout_seconds: float = 20.0

    # Витрина бота: сайт читает оттуда тарифы и цены, чтобы они не
    # разъехались с ботом.
    shop_base_url: AnyHttpUrl = AnyHttpUrl(
        "https://vpanfibot.ru/cabinet/landing"
    )
    shop_slug: str = "vpanfi"

    # Поддержка — живой человек, а не бот оформления: с вопросом
    # в меню покупки идти некуда.
    telegram_support_url: AnyHttpUrl = AnyHttpUrl("https://t.me/artem_vpanfi_bot")

    # Почта и MAX открываются без VPN, телеграм — нет. Письмо со ссылкой
    # получает и тот, у кого подписка не заработала: контакт, до которого
    # он не дотянется, в таком письме бесполезен.
    support_email: str = "anfisa.kovganyuk@gmail.com"
    max_support_url: str = "https://max.ru/id632418110551_bot"

    # Способы входа в кабинет. Каждый включается независимо: провайдер
    # без учётных данных просто не предлагается на экране входа, а не
    # ломает вход остальным.
    #
    # Бот входа — отдельная сущность от бота, который продаёт подписки.
    # Telegram здесь только подтверждает личность и ничего не говорит о
    # том, какая подписка принадлежит человеку: её находит собственная
    # ссылка подписки.
    # Уведомления о покупках на сайте. Бот продаж такие шлёт давно, а сайт
    # молчал: покупку можно было заметить, только заглянув в панель.
    telegram_alert_bot_token: SecretStr | None = None
    telegram_alert_chat_id: str | None = None
    # О чём сообщать. Входы отделены от прочего намеренно: их сильно
    # больше, чем регистраций и покупок, и когда поток вырастет, поток
    # сообщений придётся убавить, не теряя главного.
    telegram_alert_events: str = "registration,login,payment"

    telegram_login_bot_token: SecretStr | None = None
    telegram_login_bot_username: str | None = None
    vk_client_id: str | None = None
    vk_client_secret: SecretStr | None = None
    yandex_client_id: str | None = None
    yandex_client_secret: SecretStr | None = None
    oauth_redirect_url: AnyHttpUrl | None = None

    # Рефералка. Выключена по умолчанию: пока флаг ложный, сайт ведёт
    # себя как прежде, код в оплате не сохраняется и награды не выдаются.
    referral_enabled: bool = False
    # Дни, которые получает друг и пригласивший за первую оплату друга.
    # Размер награды зашит и в клиентские тексты: src/pages/BuyPage.tsx,
    # src/pages/DashboardPage.tsx и база знаний бота поддержки. Смена
    # этих настроек без правки тех же текстов оставит их врущими.
    referral_friend_days: int = 15
    referral_inviter_days: int = 15
    # Дни пригласившему за первое продление того же друга (19.09.2026).
    # Другу на продлении сверху ничего не полагается: бонус за друга он
    # уже получил при первой покупке. Ноль отключает эту награду, не
    # трогая награду за первую покупку.
    referral_renewal_days: int = 15
    # Сколько дней должно пройти от первой покупки друга, чтобы новый
    # платёж посчитался продлением, а не повторной покупкой в тот же
    # вечер. Покупатель месячного периода продлевается на 30-й день, и
    # 20 дней надёжно отделяют настоящее продление от второй оплаты той
    # же ночью или от сговора с самим собой. Ноль отключает проверку.
    referral_renewal_min_gap_days: int = 20
    # Потолок наград одному пригласившему за 30 дней. Сверх него другу
    # дни всё равно выдаются, а награда пригласившему ждёт своей очереди.
    referral_monthly_cap: int = 5
    # Как часто фоновая задача повторяет зависшие выдачи.
    referral_retry_minutes: int = 30
    # Мост к боту продаж: друг может купить подписку не на сайте, а в
    # боте, и награды всё равно заводятся. Выключен по умолчанию и
    # работает только вместе с referral_enabled и настроенным
    # bedolaga_api_token; выключенный, он не делает ни одного запроса.
    # Единственная из трёх настроек ниже, что идёт из переменной
    # окружения (VPANFI_REFERRAL_BOT_ENABLED, из vars в workflow), а
    # остальные две только для конфига, как остальные числовые
    # настройки рефералки выше.
    referral_bot_enabled: bool = False
    # Как часто фон вычитывает из бота продаж новых людей и покупки.
    referral_bot_sync_minutes: int = 30
    # Имя бота продаж в Telegram: используется в ссылке
    # "https://t.me/<username>?start=<код>" на странице покупки.
    telegram_sales_bot_username: str = "VPaNfi_bot"

    # Бот продаж хранит подписки телеграм-клиентов и умеет продлевать их
    # сам. Пустой ключ значит, что до него не дотянуться: наградам
    # пригласившим из бота тогда неоткуда взяться.
    bedolaga_api_url: str = "https://vpanfibot.ru/api"
    bedolaga_api_token: SecretStr | None = None

    # Защита от награды задним числом: покупки, завершённые до этого
    # момента, никогда не превращаются в награду. Сегодня бот всегда
    # ставит referred_by_id только новому человеку, но если он когда-
    # нибудь научится привязывать пригласившего к уже существующему
    # покупателю, старая покупка не должна вдруг стать наградой. Пусто
    # выключает защиту целиком, как было раньше. Только для конфига,
    # без деплойных секретов и переменных workflow.
    referral_bot_since: datetime | None = None

    @field_validator("referral_bot_since", mode="after")
    @classmethod
    def normalize_referral_bot_since_to_utc(
        cls, value: datetime | None
    ) -> datetime | None:
        """Достроить зону там, где в переменной окружения её не было.

        ``purchases[].completed_at`` от бота продаж всегда осведомлён о
        зоне (UTC), и сравнение с наивным значением упало бы прямо на
        первом сравнении. Наивное здесь может значить только UTC: весь
        проект и так работает в нём.
        """
        if value is not None and value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value

    @field_validator(
        "remnawave_base_url",
        "remnawave_api_token",
        "remnawave_squad_uuid",
        "yookassa_shop_id",
        "yookassa_secret_key",
        "smtp_host",
        "smtp_user",
        "smtp_password",
        "smtp_from_email",
        "telegram_alert_bot_token",
        "telegram_alert_chat_id",
        "telegram_login_bot_token",
        "telegram_login_bot_username",
        "vk_client_id",
        "vk_client_secret",
        "yandex_client_id",
        "yandex_client_secret",
        "oauth_redirect_url",
        "bedolaga_api_token",
        mode="before",
    )
    @classmethod
    def empty_optional_secret_to_none(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @model_validator(mode="after")
    def production_requires_real_secrets(self) -> Self:
        """Не дать приложению подняться в проде с дефолтным ключом.

        Раньше отсутствие настройки означало бы рабочий сервис, который
        подписывает токены общеизвестным значением: любой смог бы
        выпустить себе валидный access token.

        Raises:
            ValueError: Если в production JWT-ключ дефолтный или короткий.
        """
        if not self.is_production:
            return self

        secret = self.jwt_secret.get_secret_value()
        if secret == DEFAULT_JWT_SECRET:
            raise ValueError(
                "VPANFI_JWT_SECRET must be set to a unique value in "
                "production"
            )
        if len(secret) < MIN_JWT_SECRET_LENGTH:
            raise ValueError(
                "VPANFI_JWT_SECRET must be at least "
                f"{MIN_JWT_SECRET_LENGTH} characters in production"
            )

        if self.debug:
            raise ValueError("VPANFI_DEBUG must stay off in production")

        return self

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def vk_enabled(self) -> bool:
        return bool(self.vk_client_id and self.vk_client_secret)

    @property
    def yandex_enabled(self) -> bool:
        return bool(self.yandex_client_id and self.yandex_client_secret)

    @property
    def telegram_enabled(self) -> bool:
        return bool(
            self.telegram_login_bot_token
            and self.telegram_login_bot_username
        )

    @property
    def redirect_url(self) -> str:
        """Куда провайдер возвращает пользователя после согласия."""
        if self.oauth_redirect_url is not None:
            return str(self.oauth_redirect_url)

        origin = self.allowed_origins[0] if self.allowed_origins else ""
        return f"{origin.rstrip('/')}/auth/callback"

    @property
    def is_mail_configured(self) -> bool:
        """Письма можно слать, только когда описан узел и отправитель."""
        return bool(self.smtp_host and self.smtp_from_email)

    @property
    def is_yookassa_configured(self) -> bool:
        """Касса готова, только когда есть и магазин, и ключ.

        Половина реквизитов хуже, чем ничего: платёж создастся и упрётся
        в отказ авторизации уже после того, как человек нажал «оплатить».
        """
        return bool(self.yookassa_shop_id and self.yookassa_secret_key)

    @property
    def is_bedolaga_configured(self) -> bool:
        """Наградам пригласившим через бота нужен рабочий ключ."""
        return bool(self.bedolaga_api_token)

    @property
    def reminder_days_list(self) -> list[int]:
        """Пороги предупреждений, по возрастанию.

        Мусор молча отбрасываем: опечатка в настройке не должна
        оставлять людей без предупреждений вовсе.
        """
        dni: list[int] = []
        for chunk in str(self.reminder_days or "").split(","):
            chunk = chunk.strip()
            if chunk.isdigit() and int(chunk) > 0 and int(chunk) not in dni:
                dni.append(int(chunk))
        return sorted(dni)

    @property
    def alert_events(self) -> set[str]:
        """О каких событиях сайта сообщать в бота."""
        return {
            chunk.strip().lower()
            for chunk in str(self.telegram_alert_events or "").split(",")
            if chunk.strip()
        }

    @property
    def payment_method_types(self) -> list[str]:
        """Способы оплаты для витрины, в порядке показа.

        Пустой список здесь законен и означает «не выбирать за
        человека»: витрина не покажет переключатель, платёж уйдёт без
        ``payment_method_data``, и ЮKassa предложит на своей странице
        всё, что включено у магазина.
        """
        types: list[str] = []
        for chunk in str(self.yookassa_payment_methods or "").split(","):
            name = chunk.strip().lower()
            if name and name not in types:
                types.append(name)
        return types

    @property
    def allowed_origins(self) -> list[str]:
        """Источники, которым разрешён доступ к API из браузера."""
        origins = self.frontend_origin.split(",")
        return [origin.strip() for origin in origins if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
