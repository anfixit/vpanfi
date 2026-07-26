import { navigate, routes } from "../app/navigation";
import { Brand } from "../components/Brand";
import { Mascot } from "../components/Mascot";
import { ThemeToggle, type Theme } from "../components/ThemeToggle";
import { countries, platforms, tariffs } from "../data";

export function LandingPage({
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
          <button className="button button-primary" type="button" onClick={onOpenAuth}>
            Начать
          </button>
        </div>
      </header>

      <main>
        <section className="hero shell">
          <div className="hero-copy">
            <div className="eyebrow"><span aria-hidden="true">🌿</span> Анфиса проведёт через интернет-джунгли</div>
            <h1>Простой доступ в интернет <span>без лишней путаницы</span></h1>
            <p className="hero-text">
              Подключайтесь на телефоне, компьютере или телевизоре. Всё объясним обычными словами и
              покажем, куда нажать.
            </p>
            <div className="hero-actions">
              <button className="button button-primary button-large" type="button" onClick={onOpenAuth}>
                Получить 7 дней бесплатно
              </button>
              <button className="button button-secondary button-large" type="button" onClick={() => navigate(routes.dashboard)}>
                Посмотреть кабинет
              </button>
            </div>
            <div className="trust-row" aria-label="Преимущества">
              <span>✓ Надёжное подключение</span>
              <span>✓ Без лимита трафика</span>
              <span>✓ Помощь рядом</span>
            </div>
          </div>
          <div className="hero-art">
            <div className="hero-orbit hero-orbit-one">⌁</div>
            <div className="hero-orbit hero-orbit-two">◉</div>
            <div className="hero-orbit hero-orbit-three">▢</div>
            <Mascot variant="explorer" />
          </div>
        </section>

        <section className="product-grid shell" id="how">
          <article className="panel panel-how">
            <div className="section-heading compact-heading">
              <div><span className="section-kicker">Три простых шага</span><h2>Как это работает</h2></div>
              <span className="leaf-mark" aria-hidden="true">🌿</span>
            </div>
            <div className="steps">
              <div className="step">
                <span className="step-number">1</span>
                <Mascot variant="greeting" className="card-mascot-small" decorative />
                <strong>Зарегистрируйтесь</strong><p>Создайте аккаунт за пару минут.</p>
              </div>
              <div className="step-line" aria-hidden="true" />
              <div className="step">
                <span className="step-number">2</span>
                <Mascot variant="checking" className="card-mascot-small" decorative />
                <strong>Выберите устройство</strong><p>Мы сами покажем нужное приложение.</p>
              </div>
              <div className="step-line" aria-hidden="true" />
              <div className="step">
                <span className="step-number">3</span>
                <Mascot variant="success" className="card-mascot-small" decorative />
                <strong>Подключитесь</strong><p>Одна кнопка, и всё готово.</p>
              </div>
            </div>
          </article>

          <article className="panel panel-devices" id="devices">
            <div className="section-heading compact-heading">
              <div><span className="section-kicker">На любом экране</span><h2>Все Ваши устройства</h2></div>
              <span className="leaf-mark" aria-hidden="true">🌱</span>
            </div>
            <div className="platform-grid">
              {platforms.map((platform) => (
                <div className="platform" key={platform.name}>
                  <span className="platform-icon" aria-hidden="true">{platform.icon}</span>
                  <span>{platform.name}</span>
                </div>
              ))}
            </div>
          </article>

          <article className="panel panel-tariffs" id="tariffs">
            <div className="section-heading compact-heading">
              <div><span className="section-kicker">Без сложных условий</span><h2>Простые тарифы</h2></div>
              <span className="leaf-mark" aria-hidden="true">🍃</span>
            </div>
            <div className="tariff-grid">
              {tariffs.map((tariff) => (
                <button className={`tariff ${tariff.popular ? "is-popular" : ""}`} type="button" key={tariff.period} onClick={onOpenAuth}>
                  {tariff.popular && <span className="popular-label">выгодно</span>}
                  <span>{tariff.period}</span><strong>{tariff.price}</strong>
                  {tariff.saving && <small>{tariff.saving}</small>}
                </button>
              ))}
            </div>
            <div className="tariff-features"><span>✓ 3 устройства</span><span>✓ без лимита</span></div>
            <button className="add-device" type="button" onClick={onOpenAuth}>+1 устройство за 100 ₽</button>
          </article>
        </section>

        <section className="lower-grid shell">
          <article className="panel countries-panel" id="countries">
            <div className="section-heading compact-heading">
              <div><span className="section-kicker">Выбор внутри приложения</span><h2>Страны на каждый день</h2></div>
              <span className="leaf-mark" aria-hidden="true">🌍</span>
            </div>
            <div className="country-list">
              {countries.map((country) => <span className="country-chip" key={country.name}><span>{country.flag}</span> {country.name}</span>)}
            </div>
            <p className="muted">Полный список будет доступен после подключения.</p>
          </article>

          <article className="panel support-panel" id="support">
            <div>
              <span className="section-kicker">Отвечаем по-человечески</span>
              <h2>Поддержка, которая помогает</h2>
              <p>Напишите в Telegram или оставьте обращение. Позже здесь появится умный помощник Анфиса.</p>
              <div className="support-actions">
                <button className="support-button support-main" type="button">Telegram</button>
                <button className="support-button" type="button">Форма</button>
                <button className="support-button" type="button">Чат</button>
              </div>
            </div>
            <Mascot variant="support" className="support-mascot-image" decorative />
          </article>
        </section>

        <section className="final-cta shell">
          <div>
            <span className="section-kicker">Первую неделю оплачивать не нужно</span>
            <h2>Попробуйте спокойно, без обязательств</h2>
            <p>Анфиса всё покажет. Если не подойдёт, ничего отменять не придётся.</p>
          </div>
          <button className="button button-primary button-large" type="button" onClick={onOpenAuth}>Начать бесплатно</button>
        </section>
      </main>

      <footer className="footer shell">
        <div className="footer-brand"><Brand /><p>Простой доступ в интернет без лишней путаницы.</p></div>
        <div className="footer-links"><a href="#tariffs">Тарифы</a><a href="#devices">Устройства</a><a href="#support">Поддержка</a></div>
        <div className="footer-note">© VPaNfi, 2026</div>
      </footer>
    </>
  );
}
