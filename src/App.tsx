import { useState } from "react";
import { api } from "./api/client";
import { isCabinetRoute, navigate, routes, usePathname } from "./app/navigation";
import { useAuth } from "./auth/AuthContext";
import { findLegalDocument } from "./legal";
import { AuthModal } from "./components/AuthModal";
import { CabinetShell } from "./components/CabinetShell";
import { LoadingState } from "./components/ResourceState";
import { type Theme } from "./components/ThemeToggle";
import { useTheme } from "./hooks/useTheme";
import { AdminPage } from "./pages/AdminPage";
import { AuthCallbackPage } from "./pages/AuthCallbackPage";
import { BuyPage } from "./pages/BuyPage";
import { ConnectPage } from "./pages/ConnectPage";
import { DashboardPage } from "./pages/DashboardPage";
import { DevicesPage } from "./pages/DevicesPage";
import { LandingPage } from "./pages/LandingPage";
import { LegalDocumentPage } from "./pages/LegalDocumentPage";
import { LegalPage } from "./pages/LegalPage";
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
          displayName={profile?.displayName ?? DEMO_DISPLAY_NAME}
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

  // Админка была открыта любому, кто знал адрес. Теперь она требует
  // и входа, и прав администратора.
  const renderAdmin = () => {
    if (api.isDemoMode) return <AdminPage />;

    if (status === "loading") {
      return <LoadingState label="Анфиса проверяет доступ…" />;
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

    if (profile && !profile.isAdmin) return <NotFoundPage />;

    return <AdminPage />;
  };

  const legalDocument = findLegalDocument(pathname);
  let page;

  if (pathname === routes.landing) {
    page = (
      <LandingPage theme={theme} onToggleTheme={toggleTheme} onOpenAuth={openAuth} />
    );
  } else if (pathname === routes.authCallback) {
    page = <AuthCallbackPage />;
  } else if (pathname === routes.buy) {
    // Покупка открыта без входа: у покупателя ещё нет аккаунта.
    page = <BuyPage theme={theme} onToggleTheme={toggleTheme} />;
  } else if (pathname === routes.legal) {
    // Документы открыты всем: их читают до регистрации и до оплаты.
    page = <LegalPage theme={theme} onToggleTheme={toggleTheme} />;
  } else if (legalDocument) {
    page = (
      <LegalDocumentPage
        document={legalDocument}
        theme={theme}
        onToggleTheme={toggleTheme}
      />
    );
  } else if (pathname === routes.admin) {
    page = renderAdmin();
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
