"""Схемы административного раздела."""

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field

__all__ = [
    "AdminOverviewResponse",
    "AdminUserResponse",
    "ExtendSubscriptionRequest",
    "GrantTrialRequest",
]

MIN_EXTENSION_DAYS = 1
MAX_EXTENSION_DAYS = 730


class AdminSchema(BaseModel):
    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)


class AdminUserResponse(AdminSchema):
    id: UUID
    email: EmailStr
    display_name: str = Field(serialization_alias="displayName")
    created_at: datetime = Field(serialization_alias="createdAt")
    is_active: bool = Field(serialization_alias="isActive")
    is_admin: bool = Field(serialization_alias="isAdmin")
    panel_username: str | None = Field(
        default=None, serialization_alias="panelUsername"
    )
    subscription_linked: bool = Field(
        serialization_alias="subscriptionLinked"
    )
    expires_at: date | None = Field(
        default=None, serialization_alias="expiresAt"
    )
    days_left: int | None = Field(
        default=None, serialization_alias="daysLeft"
    )


class AdminOverviewResponse(AdminSchema):
    total_users: int = Field(serialization_alias="totalUsers")
    linked_users: int = Field(serialization_alias="linkedUsers")
    admins: int
    registered_last_30_days: int = Field(
        serialization_alias="registeredLast30Days"
    )


class ExtendSubscriptionRequest(AdminSchema):
    days: int = Field(
        ge=MIN_EXTENSION_DAYS,
        le=MAX_EXTENSION_DAYS,
        description="На сколько дней продлить подписку в панели",
    )


class GrantTrialRequest(AdminSchema):
    username: str = Field(
        min_length=3,
        max_length=64,
        pattern=r"^[A-Za-z0-9_-]+$",
        description="Имя пользователя в панели",
    )
    days: int = Field(
        default=7,
        ge=MIN_EXTENSION_DAYS,
        le=MAX_EXTENSION_DAYS,
    )
