import { api } from "../api/client";
import type { Subscription } from "../api/contracts";
import { navigate, routes } from "../app/navigation";
import { CabinetCard } from "../components/CabinetCard";
import { useDemoNotice } from "../components/DemoNotice";
import { Icon } from "../components/Icon";
import { Mascot, type MascotVariant } from "../components/Mascot";
import { ErrorState, LoadingState } from "../components/ResourceState";
import { SubscriptionOnboarding } from "../components/SubscriptionOnboarding";
import { useAsyncResource } from "../hooks/useAsyncResource";
import { formatRubles } from "../utils/format";

const VISIBLE_COUNTRIES = 5;

type SubscriptionView = {
  title: string;
  mascot: MascotVariant;
  headline: string;
  hint: string;
  actionLabel: string;
  expired: boolean;
};

function describeSubscription(subscription: Subscription): SubscriptionView {
  if (subscription.status === "expired" || subscription.status === "disabled") {
    return {
      title: "Подписка закончилась",
      mascot: "error",
      headline: "Доступ приостановлен",
      hint: "Продлите подписку, и всё заработает как раньше.",
      actionLabel: "Продлить подписку",
      expired: true,
    };
  }

  if (subscription.status === "trial") {
    return {
      title: "Пробный период",
      mascot: "subscription-active",
      headline: `${subscription.daysLeft} дней`,
      hint: "Оплачивать пока ничего не нужно.",
      actionLabel: "Выбрать тариф",
      expired: false,
    };
  }

  return {
    title: "Подписка активна",
    mascot: "subscription-active",
    headline: `${subscription.daysLeft} дней`,
    hint: `до ${subscription.expiresAt}`,
    actionLabel: "Продлить",
    expired: false,
  };
}

export function DashboardPage() {
  const dashboard = useAsyncResource(api.getDashboard);
  const subscriptionLink = useAsyncResource(api.getSubscription);
  const { explain } = useDemoNotice();

  const reloadEverything = () => {
    subscriptionLink.reload();
    dashboard.reload();
  };

  if (
    (dashboard.loading && !dashboard.data) ||
    (subscriptionLink.loading && !subscriptionLink.data)
  ) {
    return <LoadingState />;
  }

  // Пока аккаунт не связан с подпиской, показывать сроки и устройства
  // нечего: вместо этого предлагаем оформить её и перенести имеющуюся.
  if (subscriptionLink.data?.linked === false) {
    return <SubscriptionOnboarding onLinked={reloadEverything} />;
  }

  if (dashboard.error || !dashboard.data) {
    return (
      <ErrorState
        message={dashboard.error ?? "Данные кабинета не найдены"}
        onRetry={dashboard.reload}
      />
    );
  }

  const { subscription, countries, recentPayments } = dashboard.data;

  // Сюда попадают только связанные аккаунты, но подписка может исчезнуть
  // из панели между двумя запросами — тогда честнее предложить её
  // добавить заново, чем показать пустые карточки.
  if (!subscription) {
    return <SubscriptionOnboarding onLinked={reloadEverything} />;
  }

  const view = describeSubscription(subscription);
  const devicesFull = subscription.devicesUsed >= subscription.devicesLimit;

  return (
    <>
      <div className="cabinet-grid cabinet-grid-top">
        <CabinetCard
          title={view.title}
          icon={view.expired ? "refresh" : "check"}
          className={`subscription-card ${view.expired ? "is-expired" : ""}`.trim()}
        >
          <div className="subscription-main">
            <div>
              <span className="muted">{view.expired ? "Состояние" : "Дней осталось"}</span>
              <strong className="days-left">{view.headline}</strong>
              <span className="muted">{view.hint}</span>
            </div>
            <Mascot variant={view.mascot} className="card-mascot" decorative />
          </div>
          <div className="subscription-meta">
            <span>
              <small>Тариф</small>
              <strong>{subscription.planName}</strong>
            </span>
            <span>
              <small>Продление</small>
              <strong>Дни суммируются</strong>
            </span>
          </div>
          <button
            className="button button-primary full-button"
            type="button"
            onClick={() => navigate(routes.payments)}
          >
            {view.actionLabel}
          </button>
        </CabinetCard>

        <CabinetCard title="Трафик" icon="infinity">
          <strong className="big-stat">{subscription.trafficLabel}</strong>
          <p className="muted">Пользуйтесь спокойно, считать гигабайты не нужно.</p>
        </CabinetCard>

        <CabinetCard title="Устройства" icon="devices">
          <strong className="big-stat">
            {subscription.devicesUsed} / {subscription.devicesLimit}
          </strong>
          <p className="muted">
            {devicesFull
              ? "Все доступные места заняты."
              : "Есть свободное место для нового устройства."}
          </p>
          <button className="small-action" type="button" onClick={() => navigate(routes.devices)}>
            Управлять устройствами
          </button>
        </CabinetCard>

        <CabinetCard title="Страны" icon="globe">
          <div className="cabinet-flags">
            {countries.slice(0, VISIBLE_COUNTRIES).map((country) => (
              <span key={country.code} title={country.name}>
                {country.flag}
              </span>
            ))}
          </div>
          <p className="muted">Страна выбирается уже внутри приложения.</p>
          <button className="text-action" type="button" onClick={() => navigate(routes.connect)}>
            Как подключиться
          </button>
        </CabinetCard>
      </div>

      <div className="quick-actions">
        <button type="button" onClick={() => navigate(routes.connect)}>
          <Icon name="connect" />
          <strong>Подключить устройство</strong>
        </button>
        <button type="button" onClick={() => navigate(routes.connect)}>
          <Icon name="qr" />
          <strong>Показать QR-код</strong>
        </button>
        <button type="button" onClick={() => navigate(routes.payments)}>
          <Icon name="payments" />
          <strong>Продлить подписку</strong>
        </button>
        <button type="button" onClick={() => navigate(routes.devices)}>
          <Icon name="devices" />
          <strong>Устройства</strong>
        </button>
      </div>

      <div className="cabinet-content-grid">
        <section className="connection-panel cabinet-card">
          <div className="connection-heading">
            <div>
              <span className="cabinet-kicker">Рекомендуем</span>
              <h2>Подключение</h2>
              <p className="muted">Выберите устройство, остальное Анфиса покажет по шагам.</p>
            </div>
            <Mascot variant="phone" className="card-mascot" decorative />
          </div>
          <div className="recommended-app">
            <div className="happ-logo">HAPP</div>
            <div>
              <strong>HAPP</strong>
              <p>Самый простой вариант для начала.</p>
            </div>
            <button
              className="button button-primary"
              type="button"
              onClick={() => navigate(routes.connect)}
            >
              Подключить
            </button>
          </div>
        </section>

        <aside className="cabinet-side-column">
          <CabinetCard title="Поддержка" icon="support" className="cabinet-support">
            <Mascot variant="support" className="card-mascot" decorative />
            <strong>Мы на связи</strong>
            <p className="muted">Напишите, если что-то не получается.</p>
            <button
              className="button button-primary full-button"
              type="button"
              onClick={() => navigate(routes.support)}
            >
              Получить помощь
            </button>
          </CabinetCard>
        </aside>
      </div>

      <div className="cabinet-grid cabinet-grid-bottom">
        <CabinetCard title="Последние платежи" icon="payments">
          {recentPayments.length > 0 ? (
            <div className="payment-list">
              {recentPayments.map((payment) => (
                <span key={payment.id}>
                  <div>
                    <strong>{payment.createdAt}</strong>
                    <small>{payment.description}</small>
                  </div>
                  <b>{formatRubles(payment.amountRub)}</b>
                </span>
              ))}
            </div>
          ) : (
            <p className="muted">Платежей пока не было.</p>
          )}
          <button className="text-action" type="button" onClick={() => navigate(routes.payments)}>
            Вся история
          </button>
        </CabinetCard>

        <CabinetCard title="Автопродление и баланс" icon="refresh">
          <div className="renewal-status">
            <span>Автопродление</span>
            <strong>{subscription.autoRenewEnabled ? "Включено" : "Выключено"}</strong>
          </div>
          <p className="muted">При наличии средств следующий период оплатится автоматически.</p>
          <div className="balance-row">
            <span>Баланс</span>
            <strong>{formatRubles(subscription.balanceRub)}</strong>
          </div>
          <button
            className="small-action"
            type="button"
            onClick={() => explain("Пополнение баланса откроется вместе с платёжным провайдером.")}
          >
            Пополнить баланс
          </button>
        </CabinetCard>

        <CabinetCard
          title="Состояние"
          icon={view.expired ? "refresh" : "check"}
          className="status-card"
        >
          <Mascot
            variant={view.expired ? "error" : "connected"}
            className="card-mascot"
            decorative
          />
          <strong>{view.expired ? "Подключение приостановлено" : "Всё работает отлично!"}</strong>
          <p className="muted">
            {view.expired
              ? "После продления доступ вернётся автоматически."
              : "Подключение активно и готово к работе."}
          </p>
          <span className={`status-pill ${view.expired ? "is-warning" : ""}`.trim()}>
            {view.expired ? "Не подключено" : "Подключено"}
          </span>
        </CabinetCard>
      </div>
    </>
  );
}
