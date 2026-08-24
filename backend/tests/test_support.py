"""Обращение не должно теряться, даже если почта лежит."""

from collections.abc import Iterator
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import SecretStr, ValidationError

from app.api.dependencies import get_support_service
from app.core.config import Settings
from app.models.support import MessageAuthor, SupportTicket, TicketStatus
from app.schemas.support import TicketCreateRequest
from app.services import support as support_module
from app.services.support import SupportService, subject_from
from tests.conftest import build_user

SUPPORT_PATH = "/api/v1/cabinet/support"


def _settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "_env_file": None,
        "smtp_host": "smtp.example.test",
        "smtp_user": "user",
        "smtp_password": SecretStr("secret"),
        "smtp_from_email": "noreply@vpanfi.su",
    }
    values.update(overrides)
    return Settings(**values)  # type: ignore[arg-type]


class FakeSession:
    """Запоминает, что и в каком порядке сохраняли.

    Раздаёт первичные ключи на commit — так же, как это делает настоящая
    сессия при записи: до неё ``ticket.id`` пуст.
    """

    def __init__(self) -> None:
        self.added: list[object] = []
        self.commits = 0

    def add(self, obj: object) -> None:
        self.added.append(obj)

    async def commit(self) -> None:
        self.commits += 1
        for obj in self.added:
            if getattr(obj, "id", None) is None:
                obj.id = uuid4()


def test_subject_is_taken_from_the_first_line() -> None:
    assert subject_from("Не работает ютуб\nна макбуке") == "Не работает ютуб"


def test_long_first_line_is_trimmed_to_fit_the_column() -> None:
    """Тема длиннее 200 символов не влезет в базу и оборвёт запись."""
    subject = subject_from("я" * 500)
    assert len(subject) <= 200
    assert subject.endswith("…")


def test_leading_blank_lines_do_not_eat_the_subject() -> None:
    assert subject_from("\n\nвторая строка") == "вторая строка"


def test_message_of_only_spaces_is_refused() -> None:
    """Десять пробелов проходят min_length, но обращением не являются."""
    with pytest.raises(ValidationError):
        TicketCreateRequest(message=" " * 12)


async def test_ticket_is_saved_before_the_letter_is_attempted(
    monkeypatch,
) -> None:
    """Порядок важен: упавшая почта не должна терять обращение."""
    session = FakeSession()

    class ExplodingMailer:
        def __init__(self, settings: object) -> None:
            pass

        async def send(self, *, to_email: str, letter: object) -> bool:
            raise OSError("почтовый узел недоступен")

    monkeypatch.setattr(support_module, "Mailer", ExplodingMailer)

    service = SupportService(session, _settings())  # type: ignore[arg-type]
    result = await service.create(
        build_user(),
        TicketCreateRequest(category="payment", message="Списали дважды"),
    )

    assert session.commits == 1
    assert result.subject == "Списали дважды"

    ticket = session.added[0]
    assert isinstance(ticket, SupportTicket)
    assert ticket.status is TicketStatus.WAITING_FOR_SUPPORT
    assert ticket.category == "payment"
    assert ticket.messages[0].author is MessageAuthor.USER


async def test_letter_goes_to_the_owner_not_to_the_author(
    monkeypatch,
) -> None:
    """Уведомление нужно тому, кто отвечает, а не тому, кто спросил."""
    sent: list[str] = []

    class StubMailer:
        def __init__(self, settings: object) -> None:
            pass

        async def send(self, *, to_email: str, letter: object) -> bool:
            sent.append(to_email)
            return True

    monkeypatch.setattr(support_module, "Mailer", StubMailer)

    settings = _settings(support_email="vladelec@example.test")
    service = SupportService(FakeSession(), settings)  # type: ignore[arg-type]
    await service.create(
        build_user(),
        TicketCreateRequest(message="Не подключается на телефоне"),
    )

    assert sent == ["vladelec@example.test"]


async def test_ticket_survives_a_missing_mail_relay() -> None:
    """Без настроенной почты обращение всё равно принимается."""
    session = FakeSession()
    service = SupportService(  # type: ignore[arg-type]
        session,
        Settings(_env_file=None),
    )

    await service.create(
        build_user(),
        TicketCreateRequest(message="Вопрос про устройства"),
    )

    assert session.commits == 1


class StubSupportService:
    def __init__(self) -> None:
        self.calls: list[TicketCreateRequest] = []

    async def create(self, user: object, request: TicketCreateRequest):
        self.calls.append(request)
        from uuid import uuid4

        from app.schemas.support import TicketCreatedResponse

        return TicketCreatedResponse(
            id=uuid4(),
            subject=request.message,
            status="waiting_for_support",
        )


@pytest.fixture
def stub_service(app: FastAPI) -> Iterator[StubSupportService]:
    service = StubSupportService()
    app.dependency_overrides[get_support_service] = lambda: service
    yield service
    app.dependency_overrides.pop(get_support_service, None)


def test_support_needs_a_signed_in_account(
    anonymous_client: TestClient,
) -> None:
    """Гостю отвечать некуда — для него на странице есть почта и MAX."""
    response = anonymous_client.post(
        SUPPORT_PATH,
        json={"message": "Здравствуйте, не работает"},
    )
    assert response.status_code == 401


def test_too_short_a_message_is_refused(
    client: TestClient,
    stub_service: StubSupportService,
) -> None:
    """«Помогите» без подробностей — потерянный круг переписки."""
    response = client.post(SUPPORT_PATH, json={"message": "ало"})

    assert response.status_code == 422
    assert stub_service.calls == []


def test_accepted_ticket_comes_back_with_its_subject(
    client: TestClient,
    stub_service: StubSupportService,
) -> None:
    response = client.post(
        SUPPORT_PATH,
        json={"category": "devices", "message": "Восьмое устройство не лезет"},
    )

    assert response.status_code == 201
    assert response.json()["subject"] == "Восьмое устройство не лезет"
    assert stub_service.calls[0].category.value == "devices"
