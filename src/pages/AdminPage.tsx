import { navigate, routes } from "../app/navigation";
import { Brand } from "../components/Brand";
import { useDemoNotice } from "../components/DemoNotice";
import { Icon, type IconName } from "../components/Icon";
import { Mascot } from "../components/Mascot";

const PENDING_ADMIN_API = "Раздел откроется вместе с административным API на сервере.";

const adminStats = [
  { label: "Пользователи", value: "128", note: "+9 за 30 дней" },
  { label: "Активные подписки", value: "76", note: "59% пользователей" },
  { label: "Пробный период", value: "11", note: "Нужен онбординг" },
  { label: "Обращения", value: "4", note: "2 ждут ответа" },
];

const adminActions: Array<{ icon: IconName; title: string; note: string }> = [
  {
    icon: "plus",
    title: "Создать пользователя",
    note: "Ручная регистрация и пробный период",
  },
  { icon: "payments", title: "Найти платёж", note: "По пользователю или номеру операции" },
  { icon: "support", title: "Открыть обращения", note: "Очередь поддержки и история диалогов" },
  { icon: "connect", title: "Состояние Remnawave", note: "Проверка API и синхронизации" },
];

const recentUsers = [
  { name: "Марина С.", source: "Telegram · сегодня, 10:24", status: "Пробный период" },
  { name: "Илья К.", source: "Яндекс · вчера, 19:11", status: "Активна" },
  { name: "Светлана П.", source: "Логин · вчера, 17:42", status: "Закончилась" },
];

export function AdminPage() {
  const { explain } = useDemoNotice();

  return (
    <div className="admin-layout">
      <header className="admin-header shell">
        <Brand />
        <div>
          <span className="admin-badge">Админка</span>
          <button
            className="button button-secondary"
            type="button"
            onClick={() => navigate(routes.dashboard)}
          >
            Открыть кабинет
          </button>
        </div>
      </header>

      <main className="admin-main shell">
        <section className="page-intro cabinet-card">
          <div>
            <span className="cabinet-kicker">Управление сервисом</span>
            <h1>Добрый день, Анфиса</h1>
            <p className="muted">
              Главные показатели, пользователи, платежи и обращения без перегруженной панели.
            </p>
          </div>
          <Mascot variant="laptop" className="page-intro-mascot" decorative />
        </section>

        <section className="admin-stat-grid">
          {adminStats.map((stat) => (
            <article className="cabinet-card admin-stat" key={stat.label}>
              <span>{stat.label}</span>
              <strong>{stat.value}</strong>
              <small>{stat.note}</small>
            </article>
          ))}
        </section>

        <section className="admin-content-grid">
          <article className="cabinet-card">
            <div className="section-heading compact-heading">
              <div>
                <span className="section-kicker">Последняя активность</span>
                <h2>Новые пользователи</h2>
              </div>
              <button
                className="text-action"
                type="button"
                onClick={() => explain(PENDING_ADMIN_API)}
              >
                Все пользователи
              </button>
            </div>
            <div className="admin-table">
              {recentUsers.map((user) => (
                <div className="admin-table-row" key={user.name}>
                  <div>
                    <strong>{user.name}</strong>
                    <small>{user.source}</small>
                  </div>
                  <span
                    className={
                      user.status === "Закончилась" ? "connection-status" : "status-pill"
                    }
                  >
                    {user.status}
                  </span>
                  <button
                    className="button button-ghost"
                    type="button"
                    onClick={() => explain(PENDING_ADMIN_API)}
                  >
                    Открыть
                  </button>
                </div>
              ))}
            </div>
          </article>

          <article className="cabinet-card admin-actions">
            <div className="section-heading compact-heading">
              <div>
                <span className="section-kicker">Быстрые действия</span>
                <h2>Управление</h2>
              </div>
            </div>
            {adminActions.map((action) => (
              <button
                type="button"
                key={action.title}
                onClick={() => explain(PENDING_ADMIN_API)}
              >
                <Icon name={action.icon} />
                <div>
                  <strong>{action.title}</strong>
                  <small>{action.note}</small>
                </div>
              </button>
            ))}
          </article>
        </section>
      </main>
    </div>
  );
}
