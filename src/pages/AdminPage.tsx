import { navigate, routes } from "../app/navigation";
import { Brand } from "../components/Brand";
import { Mascot } from "../components/Mascot";

const adminStats = [
  { label: "Пользователи", value: "128", note: "+9 за 30 дней" },
  { label: "Активные подписки", value: "76", note: "59% пользователей" },
  { label: "Пробный период", value: "11", note: "Нужен онбординг" },
  { label: "Обращения", value: "4", note: "2 ждут ответа" },
];

export function AdminPage() {
  return (
    <div className="admin-layout">
      <header className="admin-header shell">
        <Brand />
        <div><span className="admin-badge">Админка</span><button className="button button-secondary" type="button" onClick={() => navigate(routes.dashboard)}>Открыть кабинет</button></div>
      </header>

      <main className="admin-main shell">
        <section className="page-intro cabinet-card">
          <div><span className="cabinet-kicker">Управление сервисом</span><h1>Добрый день, Анфиса</h1><p className="muted">Главные показатели, пользователи, платежи и обращения без перегруженной панели.</p></div>
          <Mascot variant="working" className="page-intro-mascot" decorative />
        </section>

        <section className="admin-stat-grid">
          {adminStats.map((stat) => <article className="cabinet-card admin-stat" key={stat.label}><span>{stat.label}</span><strong>{stat.value}</strong><small>{stat.note}</small></article>)}
        </section>

        <section className="admin-content-grid">
          <article className="cabinet-card">
            <div className="section-heading compact-heading"><div><span className="section-kicker">Последняя активность</span><h2>Новые пользователи</h2></div><button className="text-action" type="button">Все пользователи</button></div>
            <div className="admin-table">
              <div className="admin-table-row"><div><strong>Марина С.</strong><small>Telegram · сегодня, 10:24</small></div><span className="status-pill">Пробный период</span><button className="button button-ghost" type="button">Открыть</button></div>
              <div className="admin-table-row"><div><strong>Илья К.</strong><small>Яндекс · вчера, 19:11</small></div><span className="status-pill">Активна</span><button className="button button-ghost" type="button">Открыть</button></div>
              <div className="admin-table-row"><div><strong>Светлана П.</strong><small>Логин · вчера, 17:42</small></div><span className="connection-status">Закончилась</span><button className="button button-ghost" type="button">Открыть</button></div>
            </div>
          </article>

          <article className="cabinet-card admin-actions">
            <div className="section-heading compact-heading"><div><span className="section-kicker">Быстрые действия</span><h2>Управление</h2></div></div>
            <button type="button"><span>＋</span><div><strong>Создать пользователя</strong><small>Ручная регистрация и пробный период</small></div></button>
            <button type="button"><span>▱</span><div><strong>Найти платёж</strong><small>По пользователю или номеру операции</small></div></button>
            <button type="button"><span>◖</span><div><strong>Открыть обращения</strong><small>Очередь поддержки и история диалогов</small></div></button>
            <button type="button"><span>⌁</span><div><strong>Состояние Remnawave</strong><small>Проверка API и синхронизации</small></div></button>
          </article>
        </section>
      </main>
    </div>
  );
}
