from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin
from app.models.user import User


class PaymentStatus(StrEnum):
    PENDING = "pending"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    REFUNDED = "refunded"
    CANCELLED = "cancelled"


class PaymentPurpose(StrEnum):
    SUBSCRIPTION = "subscription"
    BALANCE_TOP_UP = "balance_top_up"
    EXTRA_DEVICE = "extra_device"


class BillingAccount(TimestampMixin, Base):
    __tablename__ = "billing_accounts"

    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    balance_kopecks: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    auto_renew_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )

    user: Mapped[User] = relationship()


class Payment(TimestampMixin, Base):
    __tablename__ = "payments"
    __table_args__ = (
        UniqueConstraint(
            "provider", "provider_payment_id", name="uq_payment_provider_id"
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    # Гость покупает по почте, и аккаунта у него в момент оплаты нет:
    # поле остаётся пустым, пока подписка не выдана. После выдачи
    # кабинет заводится и связь проставляется — без неё человека некому
    # предупредить об окончании срока, обход напоминаний ищет только
    # владельцев кабинетов.
    #
    # До 03.09.2026 заводить кабинет молча было нельзя: почта в users
    # уникальна, а восстановления пароля не существовало, и человек
    # навсегда терял возможность зарегистрироваться сам. Восстановление
    # появилось, и запрет снялся.
    user_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        index=True,
    )
    contact_email: Mapped[str | None] = mapped_column(String(320), index=True)
    amount_kopecks: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[PaymentStatus] = mapped_column(
        Enum(PaymentStatus, name="payment_status"),
        nullable=False,
        default=PaymentStatus.PENDING,
    )
    purpose: Mapped[PaymentPurpose] = mapped_column(
        Enum(PaymentPurpose, name="payment_purpose"),
        nullable=False,
    )
    provider: Mapped[str] = mapped_column(
        String(64), nullable=False, default="sbp"
    )
    provider_payment_id: Mapped[str | None] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    period_months: Mapped[int | None] = mapped_column(Integer)
    extra_devices: Mapped[int | None] = mapped_column(Integer)
    tariff_id: Mapped[int | None] = mapped_column(Integer)
    period_days: Mapped[int | None] = mapped_column(Integer)
    # Панель отдаёт ссылку на подписку один раз — в момент выдачи. Без неё
    # странице результата нечего показать человеку после оплаты.
    subscription_url: Mapped[str | None] = mapped_column(String(500))
    # Отметка, что письмо со ссылкой уже ушло. Platega повторяет
    # уведомление, и без неё покупатель получал бы одно и то же письмо
    # столько раз, сколько она его прислала.
    notified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    # Код приглашения из ссылки: имя учётки пригласившего в панели.
    # Живёт у платежа, а не у пользователя: гость на момент оплаты может
    # ещё не иметь кабинета, а код должен дожить до выдачи подписки.
    referral_code: Mapped[str | None] = mapped_column(
        String(64), index=True
    )

    user: Mapped[User | None] = relationship()


class ReferralReward(TimestampMixin, Base):
    """Награда за приглашение: по дню обеим сторонам за первую оплату.

    С 19.09.2026 у награды появился второй вид (``kind``): друг может
    один раз продлить подписку и принести пригласившему ещё дней,
    сам при этом ничего сверху не получая (``friend_days == 0``).

    С той же даты у награды появился источник (``source``): друг может
    прийти по ссылке не только на сайт, но и в бота продаж. У такой
    награды нет своего платежа сайта, поэтому ``payment_id`` стал
    необязателен, а привязка к боту идёт через ``bot_transaction_id``
    (та же защита от повторной вставки, что даёт платежу его собственный
    уникальный id) и ``friend_telegram_id``.

    Заводится после того, как другу выдана подписка, и живёт своей
    жизнью: сбой панели или бота продаж не должен ронять ответ вебхуку,
    поэтому обработчик наград работает отдельно и умеет повторять
    попытку.
    """

    __tablename__ = "referral_rewards"
    __table_args__ = (
        UniqueConstraint(
            "payment_id", name="uq_referral_rewards_payment_id"
        ),
        UniqueConstraint(
            "bot_transaction_id",
            name="uq_referral_rewards_bot_transaction_id",
        ),
        # Раньше на почту друга был ровно один индекс без kind: одна
        # награда на друга навсегда. С 19.09.2026 у друга может быть
        # две записи: first за первую покупку и одна-единственная
        # renewal за первое продление, поэтому уникальность теперь по
        # паре (почта, вид), а не по одной почте.
        UniqueConstraint(
            "friend_email",
            "kind",
            name="uq_referral_rewards_friend_email_kind",
        ),
        # Оба поиска по почте друга (``first_reward_for``,
        # ``renewal_for``, ``reward_exists``) сравнивают через
        # func.lower(), обычный индекс на friend_email такому запросу
        # не служит. Текстом, а не func.lower(friend_email): колонка
        # friend_email в момент вычисления __table_args__ ещё не
        # определена ниже в теле класса. Объявлено здесь же, чтобы
        # autogenerate не решил, что индекс из миграции 0007 надо
        # снести как неизвестный моделям.
        Index(
            "ix_referral_rewards_friend_email_lower",
            text("lower(friend_email)"),
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    # Nullable с 19.09.2026: у награды из бота продаж своего платежа
    # сайта нет вовсе, FK остаётся RESTRICT для наград с сайта.
    payment_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("payments.id", ondelete="RESTRICT"),
        nullable=True,
    )
    # Источник награды: "site" (по умолчанию, как раньше) или "bot",
    # когда друг купил в боте продаж, а не на сайте.
    source: Mapped[str] = mapped_column(
        String(8), nullable=False, default="site"
    )
    # Почта друга: вторая защита от повторной выдачи, если платежей у
    # него окажется несколько до того, как первый успеет обработаться.
    # Для друга из бота продаж почты может не быть вовсе, поэтому здесь
    # хранится ключ вида "tg:<telegram_id>": уникальность (friend_email,
    # kind) защищает от повторной выдачи так же, как для друга с сайта.
    friend_email: Mapped[str] = mapped_column(String(320), nullable=False)
    friend_panel_user_id: Mapped[int | None] = mapped_column(BigInteger)
    # Телеграм-идентификатор друга из бота продаж: продление ему идёт
    # через Bedolaga, а не через панель, и панельского id может не быть.
    friend_telegram_id: Mapped[int | None] = mapped_column(BigInteger)
    inviter_username: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True
    )
    inviter_panel_user_id: Mapped[int] = mapped_column(
        BigInteger, nullable=False
    )
    # Заполнено только у клиентов бота продаж: им продление идёт через
    # Bedolaga, а не через панель.
    inviter_telegram_id: Mapped[int | None] = mapped_column(BigInteger)
    friend_days: Mapped[int] = mapped_column(Integer, nullable=False)
    inviter_days: Mapped[int] = mapped_column(Integer, nullable=False)
    # Вид награды: "first" за первую оплату друга (обоим по дню),
    # "renewal" за его первое продление (дни только пригласившему).
    # Строкой, а не перечислением Postgres, по той же причине, что и
    # у status.
    kind: Mapped[str] = mapped_column(
        String(16), nullable=False, default="first"
    )
    # Строкой, а не перечислением Postgres: новое значение статуса не
    # потребует миграции типа.
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="pending"
    )
    friend_granted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    inviter_granted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    attempts: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    last_error: Mapped[str | None] = mapped_column(String(500))
    # id транзакции в боте продаж: главная защита от повторной выдачи
    # для наград с source == "bot" (у них ещё нет своего payment_id).
    bot_transaction_id: Mapped[int | None] = mapped_column(Integer)

    payment: Mapped[Payment] = relationship()
