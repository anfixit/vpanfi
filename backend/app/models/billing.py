from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
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
    )

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    payment_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("payments.id", ondelete="RESTRICT"),
        nullable=False,
    )
    # Почта друга: вторая защита от повторной выдачи, если платежей у
    # него окажется несколько до того, как первый успеет обработаться.
    friend_email: Mapped[str] = mapped_column(String(320), nullable=False)
    friend_panel_user_id: Mapped[int | None] = mapped_column(BigInteger)
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

    payment: Mapped[Payment] = relationship()
