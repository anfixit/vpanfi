import { useState } from "react";
import { api } from "./api/client";
import { isCabinetRoute, navigate, routes, usePathname } from "./app/navigation";
import { useAuth } from "./auth/AuthContext";
import { AuthModal } from "./components/AuthModal";
import { CabinetShell } from "./components/CabinetShell";
import { LoadingState } from "./components/ResourceState";
import { type Theme } from "./components/ThemeToggle";
import { useTheme } from "./hooks/useTheme";
import { AdminPage } from "./pages/AdminPage";
import { ConnectPage } from "./pages/ConnectPage";
import { DashboardPage } from "./pages/DashboardPage";
import { DevicesPage } from "./pages/DevicesPage";
import { LandingPage } from "./pages/LandingPage";
import { NotFoundPage } from "./pages/NotFoundPage";
import { PaymentsPage } from "./pages/PaymentsPage";
import { ProfilePage } from "./pages/ProfilePage";
import { SignInRequiredPage } from "./pages/SignInRequiredPage";
import { SupportPage } from "./pages/SupportPage";

const DEMO_DISPLAY_NAME = "Алексей";
const FALLBACK_DISPLAY_NAME = "друг";

function CabinetRoute({
  pathname,
  theme,
  onToggleTheme,
  displayName,
}: {
  pathname: string;
  theme: Theme;
  onToggleTheme: () => void;
  displayName: string;
}) {
  let content;

  switch (pathname) {
    case routes.dashboard:
      content = <DashboardPage />;
      break;
    case routes.connect:
      content = <ConnectPage />;
      break;
    case routes.devices:
      content = <DevicesPage />;
      break;
    case routes.payments:
      content = <PaymentsPage />;
      break;
    case routes.support:
      content = <SupportPage />;
      break;
    case routes.profile:
      content = <ProfilePage />;
      break;
    default:
      content = <NotFoundPage />;
  }

  return (
    <CabinetShell
      pathname={pathname}
      theme={theme}
      onToggleTheme={onToggleTheme}
      displayName={displayName}
    >
      {content}
    </CabinetShell>
  );
}

export function App() {
  const pathname = usePathname();
  const { theme, toggleTheme } = useTheme();
  const { status, profile } = useAuth();
  const [authOpen, setAuthOpen] = useState(false);

  const openAuth = () => setAuthOpen(true);
  const handleAuthenticated = () => {
    setAuthOpen(false);
    navigate(routes.dashboard);
  };

  const renderCabinet = () => {
    // Демо-режим показывает кабинет всем: он для того и нужен, чтобы
    // посмотреть сервис до регистрации.
    if (api.isDemoMode) {
      return (
        <CabinetRoute
          pathname={pathname}
          theme={theme}
          onToggleTheme={toggleTheme}
          displayName={DEMO_DISPLAY_NAME}
        />
      );
    }

    if (status === "loading") {
      return <LoadingState label="Анфиса проверяет сеанс…" />;
    }

    if (status === "anonymous") {
      return (
        <SignInRequiredPage
          theme={theme}
          onToggleTheme={toggleTheme}
          onOpenAuth={openAuth}
        />
      );
    }

    return (
      <CabinetRoute
        pathname={pathname}
        theme={theme}
        onToggleTheme={toggleTheme}
        displayName={profile?.displayName ?? FALLBACK_DISPLAY_NAME}
      />
    );
  };

  let page;

  if (pathname === routes.landing) {
    page = (
      <LandingPage theme={theme} onToggleTheme={toggleTheme} onOpenAuth={openAuth} />
    );
  } else if (pathname === routes.admin) {
    page = <AdminPage />;
  } else if (isCabinetRoute(pathname)) {
    page = renderCabinet();
  } else {
    page = <NotFoundPage />;
  }

  return (
    <div className="app">
      {page}
      {authOpen && (
        <AuthModal onClose={() => setAuthOpen(false)} onAuthenticated={handleAuthenticated} />
      )}
    </div>
  );
}
