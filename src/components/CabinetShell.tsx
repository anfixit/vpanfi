import type { ReactNode } from "react";
import { navigate, routes, type AppRoute } from "../app/navigation";
import { Brand } from "./Brand";
import { useDemoNotice } from "./DemoNotice";
import { Icon, type IconName } from "./Icon";
import { Mascot } from "./Mascot";
import { ThemeToggle, type Theme } from "./ThemeToggle";

const navigationItems: Array<{
  path: AppRoute;
  label: string;
  icon: IconName;
}> = [
  { path: routes.dashboard, label: "Главная", icon: "home" },
  { path: routes.connect, label: "Подключение", icon: "connect" },
  { path: routes.devices, label: "Устройства", icon: "devices" },
  { path: routes.payments, label: "Платежи", icon: "payments" },
  { path: routes.support, label: "Поддержка", icon: "support" },
  { path: routes.profile, label: "Профиль", icon: "profile" },
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
  const { isDemoMode, explain } = useDemoNotice();

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
              aria-current={pathname === item.path ? "page" : undefined}
              aria-label={item.label}
              onClick={() => navigate(item.path)}
            >
              <Icon name={item.icon} />
              <span className="nav-label">{item.label}</span>
            </button>
          ))}
        </nav>
        <div className="sidebar-mascot">
          <Mascot variant="support" className="sidebar-mascot-image" decorative />
          <strong>Привет! Я Анфиса</strong>
          <p>Покажу следующий шаг и помогу, если что-то непонятно.</p>
        </div>
        <button className="back-to-site" type="button" onClick={() => navigate(routes.landing)}>
          <Icon name="arrow-right" className="icon-flip" />
          Вернуться на сайт
        </button>
      </aside>

      <section className="cabinet-main">
        <header className="cabinet-topbar">
          <div>
            <span className="cabinet-kicker">Личный кабинет</span>
            <h1>Привет, {displayName}!</h1>
          </div>
          <div className="cabinet-top-actions">
            {isDemoMode && <span className="demo-badge">Демо-режим</span>}
            <ThemeToggle theme={theme} onToggle={onToggleTheme} />
            <button
              className="notification"
              type="button"
              aria-label="Уведомления"
              onClick={() =>
                explain("Уведомления появятся, когда кабинет начнёт получать события от сервера.")
              }
            >
              <Icon name="bell" />
            </button>
            <button
              className="profile-chip"
              type="button"
              aria-label={`Профиль: ${displayName}`}
              onClick={() => navigate(routes.profile)}
            >
              <Mascot variant="greeting" className="profile-mascot" decorative />
              {displayName}
              <Icon name="chevron-down" />
            </button>
          </div>
        </header>

        {children}
      </section>
    </div>
  );
}
