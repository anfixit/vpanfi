from uuid import uuid4

from app.models.billing import (
    Payment,
    PaymentPurpose,
    PaymentStatus,
    ReferralReward,
)


def test_payment_can_belong_to_a_guest() -> None:
    """Гость платит по почте, аккаунта у него может не быть вовсе."""
    payment = Payment(
        user_id=None,
        contact_email="guest@example.com",
        amount_kopecks=30000,
        status=PaymentStatus.PENDING,
        purpose=PaymentPurpose.SUBSCRIPTION,
        provider="platega",
        description="Подписка на 30 дней",
        tariff_id=2,
        period_days=30,
    )

    assert payment.user_id is None
    assert payment.contact_email == "guest@example.com"
    assert payment.period_days == 30
    assert payment.subscription_url is None


def test_payment_has_a_referral_code_column() -> None:
    """Код лежит у платежа, чтобы обработчик наград нашёл пригласившего."""
    cols = {c.name for c in Payment.__table__.columns}
    assert "referral_code" in cols


def test_referral_reward_has_unique_constraints_on_payment_and_kind() -> (
    None
):
    """Без них повторная выдача завела бы вторую награду на тот же платёж

    или на тот же (почта, вид), и друг с пригласившим получили бы дни
    дважды. 19.09.2026 индекс по одной почте сменился на пару (почта,
    вид): у друга теперь может быть до двух наград, first и renewal.
    """
    names = {c.name for c in ReferralReward.__table__.constraints}

    assert "uq_referral_rewards_payment_id" in names
    assert "uq_referral_rewards_friend_email_kind" in names
    assert "uq_referral_rewards_friend_email" not in names


def test_referral_reward_default_status_and_attempts() -> None:
    """Значения по умолчанию проверяем на колонке: без сессии SQLAlchemy

    не применяет их к самому объекту, только при вставке в базу.
    """
    columns = ReferralReward.__table__.columns

    assert columns["kind"].default.arg == "first"
    assert columns["status"].default.arg == "pending"
    assert columns["attempts"].default.arg == 0

    reward = ReferralReward(
        payment_id=uuid4(),
        friend_email="friend@example.com",
        inviter_username="anfisa",
        inviter_panel_user_id=7,
        friend_days=30,
        inviter_days=30,
    )

    assert reward.friend_granted_at is None
    assert reward.inviter_granted_at is None


def test_referral_reward_has_a_lower_email_expression_index() -> None:
    """Поиск first-/renewal-наград всегда идёт через func.lower(friend_email);

    без выражения-индекса такой запрос не смог бы использовать обычный
    индекс на колонку.
    """
    names = {ix.name for ix in ReferralReward.__table__.indexes}

    assert "ix_referral_rewards_friend_email_lower" in names


def test_referral_reward_kind_column_is_a_short_string() -> None:
    """Строкой, а не перечислением: новое значение не потребует миграции."""
    column = ReferralReward.__table__.columns["kind"]

    assert str(column.type) == "VARCHAR(16)"
    assert column.nullable is False


def test_reward_keeps_its_payment_from_being_deleted() -> None:
    """Награда это единственная запись о выданных днях.

    Каскад молча стирал бы её вместе с платежом, поэтому удаление
    платежа с наградой база обязана запретить.
    """
    from app.models.billing import ReferralReward

    fk = next(iter(ReferralReward.__table__.c.payment_id.foreign_keys))

    assert fk.ondelete == "RESTRICT"
