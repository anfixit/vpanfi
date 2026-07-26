import { api } from "../api/client";
import { navigate, routes } from "../app/navigation";
import { CabinetCard } from "../components/CabinetCard";
import { Mascot } from "../components/Mascot";
import { ErrorState, LoadingState } from "../components/ResourceState";
import { useAsyncResource } from "../hooks/useAsyncResource";
import { formatRubles } from "../utils/format";

export function DashboardPage() {
  const dashboard = useAsyncResource(api.getDashboard);

  if (dashboard.loading && !dashboard.data) return <LoadingState />;
  if (dashboard.error || !dashboard.data) {
    return <ErrorState message={dashboard.error ?? "Данные кабинета не найдены"} onRetry={dashboard.reload} />;
  }

  const { subscription, countries, recentPayments } = dashboard.data;

  return (
    <>
      <div className="cabinet-grid cabinet-grid-top">
        <CabinetCard title="Подписка активна" icon="✓" className="subscription-card">
          <div className="subscription-main">
            <div>
              <span className="muted">Дней осталось</span>
              <strong className="days-left">{subscription.daysLeft} дней</strong>
              <span className="muted">до {subscription.expiresAt}</span>
            </div>
            <Mascot variant="subscription" className="card-mascot" decorative />
          </div>
          <div className="subscription-meta">
            <span><small>Тариф</small><strong>{subscription.planName}</strong></span>
            <span><small>Продление</small><strong>Дни суммируются</strong></span>
          </div>
          <button className="button button-primary full-button" type="button" onClick={() => navigate(routes.payments)}>Продлить</button>
        </CabinetCard>

        <CabinetCard title="Трафик" icon="⌁">
          <strong className="big-stat">{subscription.trafficLabel}</strong>
          <p className="muted">Пользуйтесь спокойно, считать гигабайты не нужно.</p>
          <div className="card-decoration" aria-hidden="true">🌿</div>
        </CabinetCard>

        <CabinetCard title="Устройства" icon="▣">
          <strong className="big-stat">{subscription.devicesUsed} / {subscription.devicesLimit}</strong>
          <p className="muted">{subscription.devicesUsed >= subscription.devicesLimit ? "Все доступные места заняты." : "Есть свободное место для нового устройства."}</p>
          <button className="small-action" type="button" onClick={() => navigate(routes.devices)}>Управлять устройствами</button>
        </CabinetCard>

        <CabinetCard title="Страны" icon="🌱">
          <div className="cabinet-flags">
            {countries.slice(0, 5).map((country) => <span key={country.code}>{country.flag}</span>)}
          </div>
          <p className="muted">Страна выбирается уже внутри приложения.</p>
          <button className="text-action" type="button" onClick={() => navigate(routes.connect)}>Как подключиться</button>
        </CabinetCard>
      </div>

      <div className="quick-actions">
        <button type="button" onClick={() => navigate(routes.connect)}><span>⌁</span><strong>Подключить устройство</strong></button>
        <button type="button" onClick={() => navigate(routes.connect)}><span>▦</span><strong>Показать QR-код</strong></button>
        <button type="button" onClick={() => navigate(routes.payments)}><span>♕</span><strong>Продлить подписку</strong></button>
        <button type="button" onClick={() => navigate(routes.devices)}><span>▣</span><strong>Устройства</strong></button>
      </div>

      <div className="cabinet-content-grid">
        <section className="connection-panel cabinet-card">
          <div className="connection-heading">
            <div>
              <span className="cabinet-kicker">Рекомендуем</span>
              <h2>Подключение</h2>
              <p className="muted">Выберите устройство, остальное Анфиса покажет по шагам.</p>
            </div>
            <Mascot variant="checking" className="card-mascot" decorative />
          </div>
          <div className="recommended-app">
            <div className="happ-logo">HAPP</div>
            <div><strong>HAPP</strong><p>Самый простой вариант для начала.</p></div>
            <button className="button button-primary" type="button" onClick={() => navigate(routes.connect)}>Подключить</button>
          </div>
        </section>

        <aside className="cabinet-side-column">
          <CabinetCard title="Поддержка" icon="🎧" className="cabinet-support">
            <Mascot variant="support" className="card-mascot" decorative />
            <strong>Мы на связи</strong>
            <p className="muted">Напишите, если что-то не получается.</p>
            <button className="button button-primary full-button" type="button" onClick={() => navigate(routes.support)}>Получить помощь</button>
          </CabinetCard>
        </aside>
      </div>

      <div className="cabinet-grid cabinet-grid-bottom">
        <CabinetCard title="Последние платежи" icon="▱">
          <div className="payment-list">
            {recentPayments.map((payment) => (
              <span key={payment.id}>
                <div><strong>{payment.createdAt}</strong><small>{payment.description}</small></div>
                <b>{formatRubles(payment.amountRub)}</b>
              </span>
            ))}
          </div>
          <button className="text-action" type="button" onClick={() => navigate(routes.payments)}>Вся история</button>
        </CabinetCard>

        <CabinetCard title="Автопродление и баланс" icon="↻">
          <div className="renewal-status"><span>Автопродление</span><strong>{subscription.autoRenewEnabled ? "Включено" : "Выключено"}</strong></div>
          <p className="muted">При наличии средств следующий период оплатится автоматически.</p>
          <div className="balance-row"><span>Баланс</span><strong>{formatRubles(subscription.balanceRub)}</strong></div>
          <button className="small-action" type="button" onClick={() => navigate(routes.payments)}>Пополнить баланс</button>
        </CabinetCard>

        <CabinetCard title="Состояние" icon="✓" className="status-card">
          <Mascot variant="success" className="card-mascot" decorative />
          <strong>Всё работает отлично!</strong>
          <p className="muted">Подключение активно и готово к работе.</p>
          <span className="status-pill">Подключено</span>
        </CabinetCard>
      </div>
    </>
  );
}
