import { navigate, routes } from "../app/navigation";
import { Brand } from "../components/Brand";
import { Mascot } from "../components/Mascot";
import { ThemeToggle, type Theme } from "../components/ThemeToggle";

export function SignInRequiredPage({
  theme,
  onToggleTheme,
  onOpenAuth,
}: {
  theme: Theme;
  onToggleTheme: () => void;
  onOpenAuth: () => void;
}) {
  return (
    <>
      <header className="site-header shell">
        <Brand />
        <div className="header-actions">
          <ThemeToggle theme={theme} onToggle={onToggleTheme} />
          <button className="button button-primary" type="button" onClick={onOpenAuth}>
            Войти
          </button>
        </div>
      </header>

      <main className="sign-in-required shell">
        <Mascot variant="greeting" className="resource-mascot" loading="eager" decorative />
        <span className="section-kicker">Кабинет ждёт Вас</span>
        <h1>Сначала войдите</h1>
        <p className="muted">
          Здесь Ваша подписка, устройства и платежи, поэтому кабинет
          открывается только после входа.
        </p>
        <div className="hero-actions">
          <button
            className="button button-primary button-large"
            type="button"
            onClick={onOpenAuth}
          >
            Войти или зарегистрироваться
          </button>
          <button
            className="button button-secondary button-large"
            type="button"
            onClick={() => navigate(routes.landing)}
          >
            На главную
          </button>
        </div>
      </main>
    </>
  );
}
