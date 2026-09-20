"""Открытый маршрут рефералки: ссылка на бота продаж для друга.

Без токена, как и вебхук Platega в ``payments.py``: страница покупки
показывает эту ссылку и незалогиненному человеку, пришедшему по
приглашению, до какой-либо оплаты.
"""

from fastapi import APIRouter

from app.api.dependencies import InviteResolverDep, SettingsDep
from app.schemas.referral import ReferralInviteResponse

router = APIRouter(prefix="/referral", tags=["referral"])


@router.get(
    "/invite",
    response_model=ReferralInviteResponse,
    summary="Ссылка на бота продаж для друга по коду приглашения",
)
async def get_invite(
    settings: SettingsDep,
    resolver: InviteResolverDep,
    ref: str | None = None,
) -> ReferralInviteResponse:
    """Отдать ссылку в бота продаж или пустой ответ, всегда 200.

    ``ref`` необязателен намеренно: пустой или отсутствующий код не
    должен превращаться в 422 там, где любой другой негодный код даёт
    200 с пустой ссылкой. Резолвер сам не поднимает исключений, и
    маршрут остаётся тонкой обёрткой без своих try/except: любой исход
    здесь превращается в тот же самый ответ с пустой ссылкой.
    """
    telegram_url = await resolver.resolve(ref, settings)
    return ReferralInviteResponse(telegram_url=telegram_url)
