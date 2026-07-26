import type { ReactNode } from "react";
import { navigate, routes, type AppRoute } from "../app/navigation";
import { Brand } from "./Brand";
import { ThemeToggle, type Theme } from "./ThemeToggle";

const navigationItems: Array<{ path: AppRoute; label: string; icon: string }> = [
  { path: routes.dashboard, label: "Главная", icon: "⌂" },
  { path: routes.connect, label: "Подключение", icon: "⌁" },
  { path: routes.devices, label: "Устройства", icon: "▣" },
  { path: routes.payments, label: "Платежи", icon: "▱" },
  { path: routes.support, label: "Поддержка", icon: "◖" },
  { path: routes.profile, label: "Профиль", icon: "○" },
];

export function CabinetShell({
  pathname,
  theme,
  onToggleTheme,
  displayName,
  children,
}: {
  pathname: string;
  theme: Theme;
  onToggleTheme: () => void;
  displayName: string;
  children: ReactNode;
}) {
  return (
    <div className="cabinet-layout">
      <aside className="cabinet-sidebar">
        <Brand />
        <nav aria-label="Разделы личного кабинета">
          {navigationItems.map((item) => (
            <button
              className={pathname === item.path ? "is-active" : ""}
              type="button"
              key={item.path}
              onClick={() => navigate(item.path)}
            >
              <span aria-hidden="true">{item.icon}</span>
              {item.label}
            </button>
          ))}
        </nav>
        <div className="sidebar-mascot">
          <div className="sidebar-monkey" aria-hidden="true">•ᴗ•</div>
          <strong>Привет! Я Анфиса 👋</strong>
          <p>Покажу следующий шаг и помогу, если что-то непонятно.</p>
        </div>
        <button className="back-to-site" type="button" onClick={() => navigate(routes.landing)}>
          ← Вернуться на сайт
        </button>
      </aside>

      <section className="cabinet-main">
        <header className="cabinet-topbar">
          <div>
            <span className="cabinet-kicker">Личный кабинет</span>
            <h1>Привет, {displayName}! 👋</h1>
          </div>
          <div className="cabinet-top-actions">
            <ThemeToggle theme={theme} onToggle={onToggleTheme} />
            <button className="notification" type="button" aria-label="Уведомления">♢</button>
            <button className="profile-chip" type="button" onClick={() => navigate(routes.profile)}>
              <span aria-hidden="true">🐵</span> {displayName}<span aria-hidden="true">⌄</span>
            </button>
          </div>
        </header>

        <nav className="cabinet-mobile-nav" aria-label="Разделы личного кабинета">
          {navigationItems.map((item) => (
            <button
              className={pathname === item.path ? "is-active" : ""}
              type="button"
              key={item.path}
              onClick={() => navigate(item.path)}
            >
              <span aria-hidden="true">{item.icon}</span>
              <small>{item.label}</small>
            </button>
          ))}
        </nav>

        {children}
      </section>
    </div>
  );
}
