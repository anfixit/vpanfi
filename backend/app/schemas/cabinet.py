from datetime import date, datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class SubscriptionStatus(StrEnum):
    TRIAL = "trial"
    ACTIVE = "active"
    EXPIRED = "expired"
    DISABLED = "disabled"


class SubscriptionResponse(BaseModel):
    status: SubscriptionStatus
    plan_name: str = Field(serialization_alias="planName")
    days_left: int = Field(ge=0, serialization_alias="daysLeft")
    expires_at: date = Field(serialization_alias="expiresAt")
    traffic_label: str = Field(serialization_alias="trafficLabel")
    devices_used: int = Field(ge=0, serialization_alias="devicesUsed")
    devices_limit: int = Field(ge=1, serialization_alias="devicesLimit")
    auto_renew_enabled: bool = Field(serialization_alias="autoRenewEnabled")
    balance_rub: int = Field(ge=0, serialization_alias="balanceRub")


class CountryResponse(BaseModel):
    code: str = Field(min_length=2, max_length=2)
    name: str
    flag: str
    available: bool = True


class PaymentStatus(StrEnum):
    PENDING = "pending"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    REFUNDED = "refunded"


class PaymentResponse(BaseModel):
    id: UUID | str
    created_at: datetime = Field(serialization_alias="createdAt")
    description: str
    amount_rub: int = Field(ge=0, serialization_alias="amountRub")
    status: PaymentStatus


class UserProfileResponse(BaseModel):
    id: UUID | str
    display_name: str = Field(serialization_alias="displayName")
    email: EmailStr
    telegram_linked: bool = Field(serialization_alias="telegramLinked")
    yandex_linked: bool = Field(serialization_alias="yandexLinked")
    vk_linked: bool = Field(serialization_alias="vkLinked")
    password_enabled: bool = Field(serialization_alias="passwordEnabled")


class DashboardResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)

    subscription: SubscriptionResponse
    countries: list[CountryResponse]
    recent_payments: list[PaymentResponse] = Field(serialization_alias="recentPayments")
    profile: UserProfileResponse


class DeviceResponse(BaseModel):
    id: UUID | str
    name: str
    platform: str
    last_seen_at: datetime | None = Field(serialization_alias="lastSeenAt")
    created_at: datetime = Field(serialization_alias="createdAt")
    current: bool = False


class ConnectionClientResponse(BaseModel):
    id: str
    name: str
    platform: str
    recommended: bool
    description: str
    install_url: str = Field(serialization_alias="installUrl")
    deep_link: str | None = Field(default=None, serialization_alias="deepLink")
