from datetime import UTC, date, datetime, timedelta

from app.models.user import IdentityProvider, User
from app.schemas.cabinet import (
    ConnectionClientResponse,
    CountryResponse,
    DashboardResponse,
    DeviceResponse,
    PaymentResponse,
    PaymentStatus,
    SubscriptionResponse,
    SubscriptionStatus,
    UserProfileResponse,
)


class CabinetService:
    """Собирает данные кабинета для пользователя.

    Demo-методы делают разработку фронтенда предсказуемой.
    Production-методы сначала найдут локального пользователя, а затем
    обогатят его данными панели через изолированный gateway.
    """

    async def get_demo_dashboard(self) -> DashboardResponse:
        today = date.today()
        expires_at = today + timedelta(days=184)
        return DashboardResponse(
            subscription=SubscriptionResponse(
                status=SubscriptionStatus.ACTIVE,
                plan_name="6 месяцев",
                days_left=184,
                expires_at=expires_at,
                traffic_label="Без лимита",
                devices_used=3,
                devices_limit=3,
                auto_renew_enabled=True,
                balance_rub=0,
            ),
            countries=self.get_countries(),
            recent_payments=self.get_demo_payments(),
            profile=UserProfileResponse(
                id="user_demo",
                display_name="Алексей",
                email="alexey@vpanfi.demo",
                telegram_linked=True,
                yandex_linked=False,
                vk_linked=False,
                password_enabled=True,
                is_admin=False,
            ),
        )

    def get_countries(self) -> list[CountryResponse]:
        """Страны, где у сервиса действительно есть узлы.

        Список отдаётся и витрине, и кабинету, чтобы они не разъехались.
        Обновлять его нужно вместе с узлами в панели: обещать страну,
        которой нет, значит обманывать на главной странице.
        """
        return [
            CountryResponse(code="AT", name="Австрия", flag="🇦🇹"),
            CountryResponse(code="DE", name="Германия", flag="🇩🇪"),
            CountryResponse(code="NL", name="Нидерланды", flag="🇳🇱"),
            CountryResponse(code="FI", name="Финляндия", flag="🇫🇮"),
            CountryResponse(code="SE", name="Швеция", flag="🇸🇪"),
            CountryResponse(code="KZ", name="Казахстан", flag="🇰🇿"),
            CountryResponse(code="US", name="США", flag="🇺🇸"),
        ]

    def get_demo_payments(self) -> list[PaymentResponse]:
        now = datetime.now(UTC)
        return [
            PaymentResponse(
                id="pay_demo_1",
                created_at=now - timedelta(days=30),
                description="Продление на 6 месяцев",
                amount_rub=1500,
                status=PaymentStatus.SUCCEEDED,
            ),
            PaymentResponse(
                id="pay_demo_2",
                created_at=now - timedelta(days=210),
                description="Продление на 3 месяца",
                amount_rub=800,
                status=PaymentStatus.SUCCEEDED,
            ),
        ]

    def get_demo_devices(self) -> list[DeviceResponse]:
        now = datetime.now(UTC)
        return [
            DeviceResponse(
                id="device_android",
                name="Samsung Galaxy",
                platform="Android",
                last_seen_at=now,
                created_at=now - timedelta(days=8),
                current=True,
            ),
            DeviceResponse(
                id="device_macos",
                name="MacBook Air",
                platform="macOS",
                last_seen_at=now - timedelta(days=1),
                created_at=now - timedelta(days=23),
            ),
            DeviceResponse(
                id="device_tv",
                name="Телевизор",
                platform="Android TV",
                last_seen_at=now - timedelta(days=2),
                created_at=now - timedelta(days=44),
            ),
        ]

    def get_connection_clients(self) -> list[ConnectionClientResponse]:
        return [
            ConnectionClientResponse(
                id="happ-android",
                name="HAPP",
                platform="Android",
                recommended=True,
                description="Самый простой вариант для подключения.",
                install_url="https://play.google.com/store/apps/details?id=com.happproxy",
            ),
            ConnectionClientResponse(
                id="incy-ios",
                name="INCY",
                platform="iPhone / iPad",
                recommended=True,
                description=(
                    "Есть в российском App Store — страну учётной записи "
                    "менять не нужно."
                ),
                install_url="https://apps.apple.com/ru/app/incy/id6756943388",
            ),
            ConnectionClientResponse(
                id="happ-ios",
                name="HAPP",
                platform="iPhone / iPad",
                recommended=False,
                description=(
                    "Подойдёт, если App Store у вас не российский: из "
                    "российского приложение убрали."
                ),
                install_url="https://apps.apple.com/us/app/happ-proxy-utility/id6504287215",
            ),
            ConnectionClientResponse(
                id="happ-windows",
                name="HAPP",
                platform="Windows",
                recommended=True,
                description="Простое подключение на Windows.",
                install_url="https://github.com/Happ-proxy/happ-desktop/releases",
            ),
            ConnectionClientResponse(
                id="happ-macos",
                name="HAPP",
                platform="macOS",
                recommended=True,
                description="Основное приложение для компьютеров Mac.",
                install_url="https://apps.apple.com/us/app/happ-proxy-utility/id6504287215",
            ),
            ConnectionClientResponse(
                id="nekobox-linux",
                name="NekoBox",
                platform="Linux",
                recommended=True,
                description="Понятный клиент для Linux.",
                install_url="https://github.com/MatsuriDayo/nekoray/releases",
            ),
            ConnectionClientResponse(
                id="happ-android-tv",
                name="HAPP",
                platform="Android TV",
                recommended=True,
                description="Подключение телевизора или приставки.",
                install_url="https://play.google.com/",
            ),
            ConnectionClientResponse(
                id="shadowrocket-apple-tv",
                name="Shadowrocket",
                platform="Apple TV",
                recommended=True,
                description="Подключение Apple TV через знакомое приложение.",
                install_url="https://apps.apple.com/",
            ),
        ]

    def build_profile(self, user: User) -> UserProfileResponse:
        """Профиль из локальной записи, а не из демонстрационных данных."""
        providers = {identity.provider for identity in user.identities}
        return UserProfileResponse(
            id=user.id,
            display_name=user.display_name,
            email=user.email,
            telegram_linked=IdentityProvider.TELEGRAM in providers,
            yandex_linked=IdentityProvider.YANDEX in providers,
            vk_linked=IdentityProvider.VK in providers,
            password_enabled=user.password_digest is not None,
            is_admin=user.is_admin,
        )
