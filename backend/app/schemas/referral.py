from pydantic import BaseModel, ConfigDict, Field


class ReferralInviteResponse(BaseModel):
    """Ссылка на бота продаж для друга, пришедшего по приглашению.

    ``telegram_url`` пуст, если моста к боту продаж нет, код не похож
    на имя учётки, пригласивший не найден или не привязан к боту.
    Разницы между этими случаями снаружи нет намеренно: маршрут не
    должен объяснять держателю ссылки, что именно не так с чужой
    учёткой.
    """

    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)

    telegram_url: str | None = Field(
        default=None, serialization_alias="telegramUrl"
    )
