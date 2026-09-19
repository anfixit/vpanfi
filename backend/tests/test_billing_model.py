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


def test_referral_reward_has_unique_constraints_on_payment_and_email() -> (
    None
):
    """Без них повторная выдача завела бы вторую награду на тот же платёж

    или на ту же почту, и друг с пригласившим получили бы дни дважды.
    """
    names = {c.name for c in ReferralReward.__table__.constraints}

    assert "uq_referral_rewards_payment_id" in names
    assert "uq_referral_rewards_friend_email" in names


def test_referral_reward_default_status_and_attempts() -> None:
    """Значения по умолчанию проверяем на колонке: без сессии SQLAlchemy

    не применяет их к самому объекту, только при вставке в базу.
    """
    columns = ReferralReward.__table__.columns

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


def test_reward_keeps_its_payment_from_being_deleted() -> None:
    """Награда это единственная запись о выданных днях.

    Каскад молча стирал бы её вместе с платежом, поэтому удаление
    платежа с наградой база обязана запретить.
    """
    from app.models.billing import ReferralReward

    fk = next(iter(ReferralReward.__table__.c.payment_id.foreign_keys))

    assert fk.ondelete == "RESTRICT"
