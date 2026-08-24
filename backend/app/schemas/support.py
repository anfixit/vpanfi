from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

__all__ = ["TicketCategory", "TicketCreateRequest", "TicketCreatedResponse"]

MESSAGE_MIN = 10
MESSAGE_MAX = 4000


class TicketCategory(StrEnum):
    """Темы обращений — те же, что в форме на сайте.

    Закрытый перечень, а не свободная строка: по теме обращения
    разбирают, и «оплата», «Оплата» и «плачу второй раз» стали бы
    тремя разными темами об одном и том же.
    """

    CONNECTION = "connection"
    PAYMENT = "payment"
    DEVICES = "devices"
    OTHER = "other"


class TicketCreateRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    category: TicketCategory = TicketCategory.OTHER
    message: str = Field(
        min_length=MESSAGE_MIN,
        max_length=MESSAGE_MAX,
        description="Что случилось, своими словами",
    )

    @field_validator("message")
    @classmethod
    def message_must_carry_words(cls, value: str) -> str:
        """Проверять длину после обрезки пробелов.

        Десять пробелов проходят `min_length`, но обращением не
        являются: тема из них не выведется, и отвечать будет не на что.
        """
        stripped = value.strip()
        if len(stripped) < MESSAGE_MIN:
            raise ValueError(
                f"Опишите проблему хотя бы {MESSAGE_MIN} символами"
            )
        return stripped


class TicketCreatedResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)

    id: UUID
    subject: str
    # Подтверждение приёма, а не «мы уже решили»: обещать сроки нечем,
    # поддержка — один человек.
    status: str
