import { useState } from "react";
import { isCabinetRoute, navigate, routes, usePathname } from "./app/navigation";
import { AuthModal } from "./components/AuthModal";
import { CabinetShell } from "./components/CabinetShell";
import { useTheme } from "./hooks/useTheme";
import { AdminPage } from "./pages/AdminPage";
import { ConnectPage } from "./pages/ConnectPage";
import { DashboardPage } from "./pages/DashboardPage";
import { DevicesPage } from "./pages/DevicesPage";
import { LandingPage } from "./pages/LandingPage";
import { NotFoundPage } from "./pages/NotFoundPage";
import { PaymentsPage } from "./pages/PaymentsPage";
import { ProfilePage } from "./pages/ProfilePage";
import { SupportPage } from "./pages/SupportPage";

function CabinetRoute({ pathname, theme, onToggleTheme }: { pathname: string; theme: "light" | "dark"; onToggleTheme: () => void }) {
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
    <CabinetShell pathname={pathname} theme={theme} onToggleTheme={onToggleTheme} displayName="Алексей">
      {content}
    </CabinetShell>
  );
}

export function App() {
  const pathname = usePathname();
  const { theme, toggleTheme } = useTheme();
  const [authOpen, setAuthOpen] = useState(false);

  const finishDemoAuth = () => {
    setAuthOpen(false);
    navigate(routes.dashboard);
  };

  let page;

  if (pathname === routes.landing) {
    page = <LandingPage theme={theme} onToggleTheme={toggleTheme} onOpenAuth={() => setAuthOpen(true)} />;
  } else if (pathname === routes.admin) {
    page = <AdminPage />;
  } else if (isCabinetRoute(pathname)) {
    page = <CabinetRoute pathname={pathname} theme={theme} onToggleTheme={toggleTheme} />;
  } else {
    page = <NotFoundPage />;
  }

  return (
    <div className="app">
      {page}
      {authOpen && <AuthModal onClose={() => setAuthOpen(false)} onContinue={finishDemoAuth} />}
    </div>
  );
}
