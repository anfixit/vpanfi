from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.dependencies import (
    CurrentAdmin,
    ReferralScheduler,
    get_admin_service,
    get_referral_scheduler,
    get_reward_store,
)
from app.models.billing import ReferralReward
from app.schemas.admin import (
    AdminOverviewResponse,
    AdminUserResponse,
    ExtendSubscriptionRequest,
    GrantTrialRequest,
    ReferralRewardAdminResponse,
)
from app.services import admin as admin_service
from app.services.admin import (
    AdminService,
    ReferralRewardNotFoundError,
    ReferralRewardStatusError,
    UsernameAlreadyTakenError,
)
from app.services.referral import RewardStore
from app.services.subscription import (
    PanelUnavailableError,
    SubscriptionNotFoundError,
)

router = APIRouter(prefix="/admin", tags=["admin"])
AdminServiceDep = Annotated[AdminService, Depends(get_admin_service)]
RewardStoreDep = Annotated[RewardStore, Depends(get_reward_store)]
ReferralSchedulerDep = Annotated[
    ReferralScheduler, Depends(get_referral_scheduler)
]

MAX_USERS_LIMIT = 200
MAX_REFERRAL_REWARDS_LIMIT = 200
DEFAULT_REFERRAL_REWARDS_LIMIT = 50

FORBIDDEN_RESPONSES = {
    401: {"description": "Требуется вход"},
    403: {"description": "Доступно только администратору"},
}


def _panel_unavailable() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail={
            "code": "panel_unavailable",
            "message": "Панель сейчас недоступна, попробуйте чуть позже",
        },
    )


def _user_not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={
            "code": "user_not_found",
            "message": "Пользователь или его подписка не найдены",
        },
    )


def _reward_not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={
            "code": "referral_reward_not_found",
            "message": "Награда за приглашение не найдена",
        },
    )


def _reward_status_conflict(current_status: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={
            "code": "referral_reward_status_conflict",
            "message": f"Награда сейчас в статусе {current_status}",
        },
    )


def _describe_reward(reward: ReferralReward) -> ReferralRewardAdminResponse:
    return ReferralRewardAdminResponse(
        id=reward.id,
        friend_email=reward.friend_email,
        inviter_username=reward.inviter_username,
        status=reward.status,
        kind=reward.kind,
        friend_days=reward.friend_days,
        inviter_days=reward.inviter_days,
        created_at=reward.created_at,
        last_error=reward.last_error,
    )


@router.get(
    "/overview",
    response_model=AdminOverviewResponse,
    summary="Показатели сервиса",
    responses=FORBIDDEN_RESPONSES,
)
async def get_overview(
    admin: CurrentAdmin,
    service: AdminServiceDep,
) -> AdminOverviewResponse:
    _ = admin
    return await service.overview()


@router.get(
    "/users",
    response_model=list[AdminUserResponse],
    summary="Пользователи кабинета",
    responses=FORBIDDEN_RESPONSES,
)
async def list_users(
    admin: CurrentAdmin,
    service: AdminServiceDep,
    search: Annotated[str | None, Query(max_length=200)] = None,
    limit: Annotated[int, Query(ge=1, le=MAX_USERS_LIMIT)] = 50,
) -> list[AdminUserResponse]:
    _ = admin
    return await service.list_users(search=search, limit=limit)


@router.post(
    "/users/{user_id}/subscription/extend",
    response_model=AdminUserResponse,
    summary="Продлить подписку пользователя",
    description=(
        "Двигает дату окончания в панели. Живёт в административном "
        "разделе намеренно: без платёжного провайдера самостоятельное "
        "продление означало бы бесплатный доступ для любого желающего."
    ),
    responses=FORBIDDEN_RESPONSES
    | {
        404: {"description": "Пользователь или подписка не найдены"},
        503: {"description": "Панель недоступна"},
    },
)
async def extend_subscription(
    user_id: UUID,
    request: ExtendSubscriptionRequest,
    admin: CurrentAdmin,
    service: AdminServiceDep,
) -> AdminUserResponse:
    _ = admin
    try:
        return await service.extend_subscription(user_id, request.days)
    except SubscriptionNotFoundError as error:
        raise _user_not_found() from error
    except PanelUnavailableError as error:
        raise _panel_unavailable() from error


@router.post(
    "/users/{user_id}/subscription/trial",
    response_model=AdminUserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Завести подписку в панели и привязать её",
    responses=FORBIDDEN_RESPONSES
    | {
        404: {"description": "Пользователь не найден"},
        409: {"description": "Имя занято в панели"},
        503: {"description": "Панель недоступна"},
    },
)
async def grant_trial(
    user_id: UUID,
    request: GrantTrialRequest,
    admin: CurrentAdmin,
    service: AdminServiceDep,
) -> AdminUserResponse:
    _ = admin
    try:
        return await service.grant_trial(
            user_id,
            username=request.username,
            days=request.days,
        )
    except UsernameAlreadyTakenError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "panel_username_taken",
                "message": "Такое имя уже занято в панели",
            },
        ) from error
    except SubscriptionNotFoundError as error:
        raise _user_not_found() from error
    except PanelUnavailableError as error:
        raise _panel_unavailable() from error


@router.get(
    "/referral-rewards",
    response_model=list[ReferralRewardAdminResponse],
    summary="Список наград за приглашение",
    description=(
        "Без status отдаёт последние 50 наград любого статуса. Список "
        "нужен, чтобы найти id перед release или reject: у обоих "
        "маршрутов id обязателен, а сообщение о совпадении устройств "
        "его не несёт."
    ),
    responses=FORBIDDEN_RESPONSES,
)
async def list_referral_rewards(
    admin: CurrentAdmin,
    store: RewardStoreDep,
    status_filter: Annotated[
        str | None, Query(alias="status", max_length=16)
    ] = None,
    limit: Annotated[
        int, Query(ge=1, le=MAX_REFERRAL_REWARDS_LIMIT)
    ] = DEFAULT_REFERRAL_REWARDS_LIMIT,
) -> list[ReferralRewardAdminResponse]:
    _ = admin
    rewards = await admin_service.list_referral_rewards(
        store, status=status_filter, limit=limit
    )
    return [_describe_reward(reward) for reward in rewards]


@router.post(
    "/referral-rewards/{reward_id}/release",
    response_model=ReferralRewardAdminResponse,
    summary="Снять придержание награды и запустить выдачу",
    description=(
        "Только из held: переводит в pending и сразу ставит обработку "
        "в фон, не дожидаясь похода в панель и в бота продаж внутри "
        "самого запроса."
    ),
    responses=FORBIDDEN_RESPONSES
    | {
        404: {"description": "Награда не найдена"},
        409: {"description": "Награда не в статусе held"},
    },
)
async def release_referral_reward(
    reward_id: UUID,
    admin: CurrentAdmin,
    store: RewardStoreDep,
    scheduler: ReferralSchedulerDep,
) -> ReferralRewardAdminResponse:
    _ = admin
    try:
        reward = await admin_service.release_referral_reward(
            store, reward_id
        )
    except ReferralRewardNotFoundError as error:
        raise _reward_not_found() from error
    except ReferralRewardStatusError as error:
        raise _reward_status_conflict(str(error)) from error
    scheduler(reward.id)
    return _describe_reward(reward)


@router.post(
    "/referral-rewards/{reward_id}/reject",
    response_model=ReferralRewardAdminResponse,
    summary="Отклонить награду за приглашение",
    description=(
        "Из held, pending или failed. Дни, которые уже выданы, назад "
        "не забирает: вернуть их можно только руками в панели."
    ),
    responses=FORBIDDEN_RESPONSES
    | {
        404: {"description": "Награда не найдена"},
        409: {"description": "Награда уже granted или rejected"},
    },
)
async def reject_referral_reward(
    reward_id: UUID,
    admin: CurrentAdmin,
    store: RewardStoreDep,
) -> ReferralRewardAdminResponse:
    _ = admin
    try:
        reward = await admin_service.reject_referral_reward(store, reward_id)
    except ReferralRewardNotFoundError as error:
        raise _reward_not_found() from error
    except ReferralRewardStatusError as error:
        raise _reward_status_conflict(str(error)) from error
    return _describe_reward(reward)
