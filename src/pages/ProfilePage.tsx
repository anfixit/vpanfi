import { api } from "../api/client";
import { Mascot } from "../components/Mascot";
import { ErrorState, LoadingState } from "../components/ResourceState";
import { useAsyncResource } from "../hooks/useAsyncResource";

function ConnectionStatus({ connected }: { connected: boolean }) {
  return <span className={`connection-status ${connected ? "is-connected" : ""}`}>{connected ? "Подключено" : "Не подключено"}</span>;
}

export function ProfilePage() {
  const dashboard = useAsyncResource(api.getDashboard);

  if (dashboard.loading && !dashboard.data) return <LoadingState label="Анфиса открывает профиль…" />;
  if (dashboard.error || !dashboard.data) return <ErrorState message={dashboard.error ?? "Профиль не найден"} onRetry={dashboard.reload} />;

  const { profile } = dashboard.data;

  return (
    <div className="cabinet-page">
      <section className="page-intro cabinet-card">
        <div>
          <span className="cabinet-kicker">Ваш аккаунт</span>
          <h2>Профиль</h2>
          <p className="muted">Здесь можно изменить данные и привязать удобные способы входа.</p>
        </div>
        <Mascot variant="greeting" className="page-intro-mascot" decorative />
      </section>

      <section className="profile-grid">
        <article className="cabinet-card profile-details">
          <header><span aria-hidden="true">○</span><h3>Основные данные</h3></header>
          <label>Имя<input defaultValue={profile.displayName} /></label>
          <label>Email<input type="email" defaultValue={profile.email} /></label>
          <button className="button button-primary" type="button">Сохранить изменения</button>
        </article>

        <article className="cabinet-card profile-security">
          <header><span aria-hidden="true">⌾</span><h3>Безопасность</h3></header>
          <div className="security-row"><div><strong>Пароль</strong><p className="muted">{profile.passwordEnabled ? "Пароль установлен" : "Пароль ещё не создан"}</p></div><button className="button button-secondary" type="button">Изменить</button></div>
          <div className="security-row"><div><strong>Активные сеансы</strong><p className="muted">Управление входами на других устройствах.</p></div><button className="button button-secondary" type="button">Посмотреть</button></div>
        </article>
      </section>

      <section className="cabinet-card linked-accounts">
        <div className="section-heading compact-heading"><div><span className="section-kicker">Вход без лишних препятствий</span><h2>Связанные аккаунты</h2></div></div>
        <div className="linked-account-list">
          <div className="linked-account"><span className="tg">➤</span><div><strong>Telegram</strong><p>Вход через знакомый аккаунт и связь с поддержкой.</p></div><ConnectionStatus connected={profile.telegramLinked} /><button className="button button-ghost" type="button">{profile.telegramLinked ? "Отвязать" : "Подключить"}</button></div>
          <div className="linked-account"><span className="ya">Я</span><div><strong>Яндекс</strong><p>Быстрый вход без отдельного пароля.</p></div><ConnectionStatus connected={profile.yandexLinked} /><button className="button button-ghost" type="button">{profile.yandexLinked ? "Отвязать" : "Подключить"}</button></div>
          <div className="linked-account"><span className="vk">VK</span><div><strong>VK</strong><p>Ещё один удобный способ войти в кабинет.</p></div><ConnectionStatus connected={profile.vkLinked} /><button className="button button-ghost" type="button">{profile.vkLinked ? "Отвязать" : "Подключить"}</button></div>
        </div>
      </section>

      <section className="cabinet-card danger-zone">
        <div><h3>Удаление аккаунта</h3><p className="muted">Аккаунт и история будут удалены после подтверждения. Активная подписка при этом не возвращается автоматически.</p></div>
        <button className="button button-ghost danger-action" type="button">Удалить аккаунт</button>
      </section>
    </div>
  );
}
