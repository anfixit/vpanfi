import { useEffect, useMemo, useState } from "react";
import { cabinetStats, countries, platforms, tariffs } from "./data";

type Theme = "light" | "dark";
type Screen = "landing" | "cabinet";

const Icon = ({ children }: { children: string }) => (
  <span className="icon" aria-hidden="true">
    {children}
  </span>
);

function Brand({ compact = false }: { compact?: boolean }) {
  return (
    <button className="brand" type="button" onClick={() => window.scrollTo({ top: 0, behavior: "smooth" })}>
      <span className="brand-mark" aria-hidden="true">
        <span className="brand-ear brand-ear-left" />
        <span className="brand-ear brand-ear-right" />
        <span className="brand-face">•ᴗ•</span>
      </span>
      {!compact && <span>VPaNfi</span>}
    </button>
  );
}

function ThemeToggle({ theme, onToggle }: { theme: Theme; onToggle: () => void }) {
  return (
    <button
      className="theme-toggle"
      type="button"
      onClick={onToggle}
      aria-label={theme === "light" ? "Включить тёмную тему" : "Включить светлую тему"}
    >
      <span aria-hidden="true">☀</span>
      <span className={`theme-toggle-knob ${theme === "dark" ? "is-dark" : ""}`} />
      <span aria-hidden="true">☾</span>
    </button>
  );
}

function Header({
  theme,
  onToggleTheme,
  onOpenAuth,
  onStart,
}: {
  theme: Theme;
  onToggleTheme: () => void;
  onOpenAuth: () => void;
  onStart: () => void;
}) {
  return (
    <header className="site-header shell">
      <Brand />
      <nav className="desktop-nav" aria-label="Основная навигация">
        <a href="#how">Как это работает</a>
        <a href="#devices">Устройства</a>
        <a href="#tariffs">Тарифы</a>
        <a href="#countries">Страны</a>
        <a href="#support">Поддержка</a>
      </nav>
      <div className="header-actions">
        <ThemeToggle theme={theme} onToggle={onToggleTheme} />
        <button className="button button-ghost header-login" type="button" onClick={onOpenAuth}>
          Войти
        </button>
        <button className="button button-primary" type="button" onClick={onStart}>
          Начать
        </button>
      </div>
    </header>
  );
}

function Hero({ onStart, onCabinet }: { onStart: () => void; onCabinet: () => void }) {
  return (
    <main>
      <section className="hero shell">
        <div className="hero-copy">
          <div className="eyebrow">
            <span>🌿</span>
            Анфиса проведёт через интернет-джунгли
          </div>
          <h1>
            Простой доступ в интернет
            <span>без лишней путаницы</span>
          </h1>
          <p className="hero-text">
            Подключайтесь на телефоне, компьютере или телевизоре. Всё объясним обычными словами и
            покажем, куда нажать.
          </p>
          <div className="hero-actions">
            <button className="button button-primary button-large" type="button" onClick={onStart}>
              Получить 7 дней бесплатно <span aria-hidden="true">✦</span>
            </button>
            <button className="button button-secondary button-large" type="button" onClick={onCabinet}>
              Посмотреть кабинет
            </button>
          </div>
          <div className="trust-row" aria-label="Преимущества">
            <span><Icon>◇</Icon> Надёжное подключение</span>
            <span><Icon>⌁</Icon> Без лишних данных</span>
            <span><Icon>☺</Icon> Помощь рядом</span>
          </div>
        </div>
        <div className="hero-art" aria-label="Анфиса исследует интернет-джунгли">
          <div className="hero-orbit hero-orbit-one">⌁</div>
          <div className="hero-orbit hero-orbit-two">◉</div>
          <div className="hero-orbit hero-orbit-three">▢</div>
          <img src="/anfisa-explorer.svg" alt="Анфиса держится за лиану среди интернет-джунглей" />
        </div>
      </section>

      <section className="product-grid shell" id="how">
        <article className="panel panel-how">
          <div className="section-heading compact-heading">
            <div>
              <span className="section-kicker">Три простых шага</span>
              <h2>Как это работает</h2>
            </div>
            <span className="leaf-mark" aria-hidden="true">🌿</span>
          </div>
          <div className="steps">
            <div className="step">
              <span className="step-number">1</span>
              <div className="mini-mascot">👋</div>
              <strong>Зарегистрируйтесь</strong>
              <p>Создайте аккаунт за пару минут.</p>
            </div>
            <div className="step-line" aria-hidden="true" />
            <div className="step">
              <span className="step-number">2</span>
              <div className="mini-mascot">📱</div>
              <strong>Выберите устройство</strong>
              <p>Мы сами покажем нужное приложение.</p>
            </div>
            <div className="step-line" aria-hidden="true" />
            <div className="step">
              <span className="step-number">3</span>
              <div className="mini-mascot">✨</div>
              <strong>Подключитесь</strong>
              <p>Одна кнопка, и всё готово.</p>
            </div>
          </div>
        </article>

        <article className="panel panel-devices" id="devices">
          <div className="section-heading compact-heading">
            <div>
              <span className="section-kicker">На любом экране</span>
              <h2>Все Ваши устройства</h2>
            </div>
            <span className="leaf-mark" aria-hidden="true">🌱</span>
          </div>
          <div className="platform-grid">
            {platforms.map((platform) => (
              <div className="platform" key={platform.name}>
                <span className="platform-icon">{platform.icon}</span>
                <span>{platform.name}</span>
              </div>
            ))}
          </div>
        </article>

        <article className="panel panel-tariffs" id="tariffs">
          <div className="section-heading compact-heading">
            <div>
              <span className="section-kicker">Без сложных условий</span>
              <h2>Простые тарифы</h2>
            </div>
            <span className="leaf-mark" aria-hidden="true">🍃</span>
          </div>
          <div className="tariff-grid">
            {tariffs.map((tariff) => (
              <button
                className={`tariff ${tariff.popular ? "is-popular" : ""}`}
                type="button"
                key={tariff.period}
                onClick={onStart}
              >
                {tariff.popular && <span className="popular-label">выгодно</span>}
                <span>{tariff.period}</span>
                <strong>{tariff.price}</strong>
                {tariff.saving && <small>{tariff.saving}</small>}
              </button>
            ))}
          </div>
          <div className="tariff-features">
            <span>✓ 3 устройства</span>
            <span>✓ без лимита</span>
          </div>
          <button className="add-device" type="button" onClick={onStart}>
            +1 устройство за 100 ₽
          </button>
        </article>
      </section>

      <section className="lower-grid shell">
        <article className="panel countries-panel" id="countries">
          <div className="section-heading compact-heading">
            <div>
              <span className="section-kicker">Выбор внутри приложения</span>
              <h2>Страны на каждый день</h2>
            </div>
            <span className="leaf-mark" aria-hidden="true">🌍</span>
          </div>
          <div className="country-list">
            {countries.map((country) => (
              <span className="country-chip" key={country.name}>
                <span>{country.flag}</span> {country.name}
              </span>
            ))}
          </div>
          <p className="muted">Полный список будет доступен после подключения.</p>
        </article>

        <article className="panel support-panel" id="support">
          <div>
            <span className="section-kicker">Отвечаем по-человечески</span>
            <h2>Поддержка, которая помогает</h2>
            <p>Анфиса рядом, когда что-то непонятно. Начнём с Telegram и формы, затем добавим умный чат.</p>
            <div className="support-actions">
              <button className="support-button support-main" type="button">➤ Telegram</button>
              <button className="support-button" type="button">✉ Форма</button>
              <button className="support-button" type="button">☵ Чат</button>
            </div>
          </div>
          <div className="support-mascot" aria-hidden="true">
            <div className="headset">◖🎧◗</div>
            <div className="support-face">•ᴗ•</div>
            <div className="support-body">V</div>
          </div>
        </article>

        <article className="panel auth-panel">
          <span className="section-kicker">Как Вам удобно</span>
          <h2>Вход без лишних препятствий</h2>
          <p>Используйте логин и пароль или войдите через знакомый сервис.</p>
          <div className="auth-options">
            <button type="button" onClick={onStart}><span>⌑</span> Логин</button>
            <button type="button" onClick={onStart}><span className="ya">Я</span> Яндекс</button>
            <button type="button" onClick={onStart}><span className="vk">VK</span> VK</button>
            <button type="button" onClick={onStart}><span className="tg">➤</span> Telegram</button>
          </div>
        </article>
      </section>

      <section className="final-cta shell">
        <div>
          <span className="section-kicker">Первую неделю оплачивать не нужно</span>
          <h2>Попробуйте спокойно, без обязательств</h2>
          <p>Анфиса всё покажет. Если не подойдёт, ничего отменять не придётся.</p>
        </div>
        <button className="button button-primary button-large" type="button" onClick={onStart}>
          Начать бесплатно
        </button>
      </section>
    </main>
  );
}

function Landing({
  theme,
  onToggleTheme,
  onOpenAuth,
  onOpenCabinet,
}: {
  theme: Theme;
  onToggleTheme: () => void;
  onOpenAuth: () => void;
  onOpenCabinet: () => void;
}) {
  return (
    <>
      <Header
        theme={theme}
        onToggleTheme={onToggleTheme}
        onOpenAuth={onOpenAuth}
        onStart={onOpenAuth}
      />
      <Hero onStart={onOpenAuth} onCabinet={onOpenCabinet} />
      <footer className="footer shell">
        <div className="footer-brand">
          <Brand />
          <p>Простой доступ в интернет без лишней путаницы.</p>
        </div>
        <div className="footer-links">
          <a href="#tariffs">Тарифы</a>
          <a href="#devices">Устройства</a>
          <a href="#countries">Страны</a>
          <a href="#support">Поддержка</a>
        </div>
        <div className="footer-note">© VPaNfi, 2026</div>
      </footer>
    </>
  );
}

function CabinetCard({
  title,
  icon,
  children,
  className = "",
}: {
  title: string;
  icon: string;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <article className={`cabinet-card ${className}`}>
      <header>
        <span>{icon}</span>
        <h3>{title}</h3>
      </header>
      {children}
    </article>
  );
}

function Cabinet({ theme, onToggleTheme, onBack }: { theme: Theme; onToggleTheme: () => void; onBack: () => void }) {
  const [copied, setCopied] = useState(false);

  const copyDemo = async () => {
    try {
      await navigator.clipboard.writeText("demo-vpanfi-connection-key");
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1800);
    } catch {
      setCopied(false);
    }
  };

  return (
    <div className="cabinet-layout">
      <aside className="cabinet-sidebar">
        <Brand />
        <nav>
          <button className="is-active" type="button"><span>⌂</span> Главная</button>
          <button type="button"><span>⌁</span> Подключение</button>
          <button type="button"><span>▣</span> Устройства</button>
          <button type="button"><span>☆</span> Тарифы</button>
          <button type="button"><span>▱</span> Платежи</button>
          <button type="button"><span>◖</span> Поддержка</button>
          <button type="button"><span>○</span> Профиль</button>
        </nav>
        <div className="sidebar-mascot">
          <div className="sidebar-monkey">•ᴗ•</div>
          <strong>Привет! Я Анфиса 👋</strong>
          <p>Всегда рада помочь с подключением.</p>
        </div>
        <button className="back-to-site" type="button" onClick={onBack}>← Вернуться на сайт</button>
      </aside>

      <section className="cabinet-main">
        <header className="cabinet-topbar">
          <div>
            <span className="cabinet-kicker">Личный кабинет</span>
            <h1>Привет, Алексей! 👋</h1>
          </div>
          <div className="cabinet-top-actions">
            <ThemeToggle theme={theme} onToggle={onToggleTheme} />
            <button className="notification" type="button" aria-label="Уведомления">♢</button>
            <button className="profile-chip" type="button"><span>🐵</span> Алексей⌄</button>
          </div>
        </header>

        <div className="cabinet-grid cabinet-grid-top">
          <CabinetCard title="Подписка активна" icon="✓" className="subscription-card">
            <div className="subscription-main">
              <div>
                <span className="muted">Дней осталось</span>
                <strong className="days-left">{cabinetStats.daysLeft} дней</strong>
                <span className="muted">до {cabinetStats.expiresAt}</span>
              </div>
              <div className="happy-monkey" aria-hidden="true">🙌🐵</div>
            </div>
            <div className="subscription-meta">
              <span><small>Тариф</small><strong>6 месяцев</strong></span>
              <span><small>Продление</small><strong>Дни суммируются</strong></span>
            </div>
            <button className="button button-primary full-button" type="button">Продлить</button>
          </CabinetCard>

          <CabinetCard title="Трафик" icon="⌁">
            <strong className="big-stat">{cabinetStats.traffic}</strong>
            <p className="muted">Пользуйтесь спокойно, считать гигабайты не нужно.</p>
            <div className="card-decoration">🌿</div>
          </CabinetCard>

          <CabinetCard title="Устройства" icon="▣">
            <strong className="big-stat">{cabinetStats.devicesUsed} / {cabinetStats.devicesLimit}</strong>
            <p className="muted">Все доступные места сейчас заняты.</p>
            <button className="small-action" type="button">Добавить за 100 ₽</button>
          </CabinetCard>

          <CabinetCard title="Страны" icon="🌱">
            <div className="cabinet-flags">
              {countries.slice(0, 5).map((country) => <span key={country.name}>{country.flag}</span>)}
            </div>
            <p className="muted">Выбор страны появится внутри приложения.</p>
            <button className="text-action" type="button">Посмотреть все</button>
          </CabinetCard>
        </div>

        <div className="quick-actions">
          <button type="button"><span>⌁</span><strong>Подключить устройство</strong></button>
          <button type="button"><span>▦</span><strong>Показать QR-код</strong></button>
          <button type="button"><span>♕</span><strong>Продлить подписку</strong></button>
          <button type="button"><span>▣</span><strong>Устройства</strong></button>
        </div>

        <div className="cabinet-content-grid">
          <section className="connection-panel cabinet-card">
            <div className="connection-heading">
              <div>
                <span className="cabinet-kicker">Рекомендуем</span>
                <h2>Подключение</h2>
                <p className="muted">Выберите устройство, остальное Анфиса покажет по шагам.</p>
              </div>
              <div className="laptop-monkey">🐵💻</div>
            </div>
            <div className="recommended-app">
              <div className="happ-logo">HAPP</div>
              <div>
                <strong>HAPP</strong>
                <p>Самый простой вариант для начала.</p>
              </div>
              <button className="button button-primary" type="button">Открыть / установить</button>
            </div>
            <button className="alternative-apps" type="button">
              <span><strong>Другие приложения</strong><small>Для тех, кто уже знает, что ему нужно</small></span>
              <span>⌄</span>
            </button>
            <div className="connection-key">
              <div>
                <strong>Ключ подключения</strong>
                <p>Технические детали можно не открывать.</p>
              </div>
              <button type="button" onClick={copyDemo}>{copied ? "Скопировано ✓" : "Скопировать"}</button>
            </div>
          </section>

          <aside className="cabinet-side-column">
            <CabinetCard title="Поддержка" icon="🎧" className="cabinet-support">
              <div className="support-avatar">🐵</div>
              <strong>Мы на связи</strong>
              <p className="muted">Напишите, если что-то не получается.</p>
              <button className="button button-primary full-button" type="button">Написать в Telegram</button>
              <button className="small-action" type="button">Открыть чат</button>
              <button className="small-action" type="button">Форма обращения</button>
            </CabinetCard>
          </aside>
        </div>

        <div className="cabinet-grid cabinet-grid-bottom">
          <CabinetCard title="История платежей" icon="▱">
            <div className="payment-list">
              <span><div><strong>11 мая 2026</strong><small>6 месяцев</small></div><b>1500 ₽</b></span>
              <span><div><strong>11 ноября 2025</strong><small>3 месяца</small></div><b>800 ₽</b></span>
              <span><div><strong>11 августа 2025</strong><small>1 месяц</small></div><b>300 ₽</b></span>
            </div>
            <button className="text-action" type="button">Вся история</button>
          </CabinetCard>

          <CabinetCard title="Автопродление и баланс" icon="↻">
            <div className="renewal-status"><span>Автопродление</span><strong>Включено</strong></div>
            <p className="muted">При наличии средств следующий период оплатится автоматически.</p>
            <div className="balance-row"><span>Баланс</span><strong>0 ₽</strong></div>
            <button className="small-action" type="button">Пополнить баланс</button>
          </CabinetCard>

          <CabinetCard title="Состояние" icon="✓" className="status-card">
            <div className="status-monkey">🐵🌿</div>
            <strong>Всё работает отлично!</strong>
            <p className="muted">Подключение активно и готово к работе.</p>
            <span className="status-pill">Подключено</span>
          </CabinetCard>
        </div>
      </section>
    </div>
  );
}

function AuthModal({ onClose, onContinue }: { onClose: () => void; onContinue: () => void }) {
  const [mode, setMode] = useState<"login" | "register">("register");

  return (
    <div className="modal-backdrop" role="presentation" onMouseDown={onClose}>
      <section className="auth-modal" role="dialog" aria-modal="true" aria-labelledby="auth-title" onMouseDown={(event) => event.stopPropagation()}>
        <button className="modal-close" type="button" onClick={onClose} aria-label="Закрыть">×</button>
        <div className="auth-monkey">🐵</div>
        <span className="section-kicker">Анфиса уже приготовила всё нужное</span>
        <h2 id="auth-title">{mode === "register" ? "Начнём знакомство" : "С возвращением"}</h2>
        <p>Сейчас это демонстрационный экран. Подключение реальных способов входа появится вместе с backend.</p>
        <div className="modal-tabs">
          <button className={mode === "register" ? "is-active" : ""} type="button" onClick={() => setMode("register")}>Регистрация</button>
          <button className={mode === "login" ? "is-active" : ""} type="button" onClick={() => setMode("login")}>Вход</button>
        </div>
        <label>
          Email
          <input type="email" placeholder="you@example.com" />
        </label>
        <label>
          Пароль
          <input type="password" placeholder="Не короче 8 символов" />
        </label>
        <button className="button button-primary full-button" type="button" onClick={onContinue}>
          {mode === "register" ? "Получить 7 дней бесплатно" : "Войти"}
        </button>
        <div className="modal-divider"><span>или</span></div>
        <div className="social-login">
          <button type="button"><span className="ya">Я</span> Яндекс</button>
          <button type="button"><span className="vk">VK</span> VK</button>
          <button type="button"><span className="tg">➤</span> Telegram</button>
        </div>
      </section>
    </div>
  );
}

export function App() {
  const preferredTheme = useMemo<Theme>(() => {
    const saved = window.localStorage.getItem("vpanfi-theme");
    if (saved === "light" || saved === "dark") return saved;
    return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  }, []);

  const [theme, setTheme] = useState<Theme>(preferredTheme);
  const [screen, setScreen] = useState<Screen>("landing");
  const [authOpen, setAuthOpen] = useState(false);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    window.localStorage.setItem("vpanfi-theme", theme);
  }, [theme]);

  const toggleTheme = () => setTheme((current) => (current === "light" ? "dark" : "light"));
  const openCabinet = () => {
    setAuthOpen(false);
    setScreen("cabinet");
    window.scrollTo({ top: 0 });
  };

  return (
    <div className="app">
      {screen === "landing" ? (
        <Landing
          theme={theme}
          onToggleTheme={toggleTheme}
          onOpenAuth={() => setAuthOpen(true)}
          onOpenCabinet={openCabinet}
        />
      ) : (
        <Cabinet theme={theme} onToggleTheme={toggleTheme} onBack={() => setScreen("landing")} />
      )}
      {authOpen && <AuthModal onClose={() => setAuthOpen(false)} onContinue={openCabinet} />}
    </div>
  );
}
