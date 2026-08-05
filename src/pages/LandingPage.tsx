import { api } from "../api/client";
import { navigate, routes } from "../app/navigation";
import { useAuth } from "../auth/AuthContext";
import { useAsyncResource } from "../hooks/useAsyncResource";
import { telegramSupportUrl } from "../config";
import { legalDocuments, legalPath } from "../legal";
import { Brand } from "../components/Brand";
import { Icon } from "../components/Icon";
import { Mascot, type MascotVariant } from "../components/Mascot";
import { ThemeToggle, type Theme } from "../components/ThemeToggle";
import { platforms, tariffs } from "../data";

const advantages = ["Надёжное подключение", "Без лимита трафика", "Помощь рядом"];

/*
 * Шаги идут сверху вниз, один за другим: в три колонки на каждую
 * приходилось около ста пикселей, и подпись ломалась на четыре строки.
 */
const steps = [
  {
    mascot: "greeting",
    title: "Зарегистрируйтесь",
    text: "Создайте аккаунт за пару минут — понадобится только почта.",
  },
  {
    mascot: "phone",
    title: "Выберите устройство",
    text: "Мы сами покажем нужное приложение и дадим короткую инструкцию.",
  },
  {
    mascot: "connected",
    title: "Подключитесь",
    text: "Одна кнопка — и интернет работает как обычно, без настроек.",
  },
] as const satisfies ReadonlyArray<{
  mascot: MascotVariant;
  title: string;
  text: string;
}>;

export function LandingPage({
  theme,
  onToggleTheme,
  onOpenAuth,
}: {
  theme: Theme;
  onToggleTheme: () => void;
  onOpenAuth: () => void;
}) {
  const { status } = useAuth();
  // Список стран приходит с сервера: та же ручка кормит кабинет, так
  // что витрина не может пообещать страну, которой нет.
  const countries = useAsyncResource(api.getCountries);
  const canOpenCabinet = api.isDemoMode || status === "authenticated";

  // Форма обращения живёт в кабинете, а кабинет закрыт. Отправлять туда
  // человека без аккаунта значило упереть его в стену входа без
  // объяснений — поэтому сначала предлагаем войти.
  const openRequestForm = () => {
    if (canOpenCabinet) {
      navigate(routes.support);
      return;
    }
    onOpenAuth();
  };

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
          <a href="#documents">Документы</a>
        </nav>
        <div className="header-actions">
          <ThemeToggle theme={theme} onToggle={onToggleTheme} />
          <button
            className="button button-ghost header-login"
            type="button"
            onClick={onOpenAuth}
          >
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
            <div className="eyebrow">
              <Icon name="leaf" />
              Анфиса проведёт через интернет-джунгли
            </div>
            <h1>
              Простой доступ в интернет <span>без лишней путаницы</span>
            </h1>
            <p className="hero-text">
              Подключайтесь на телефоне, компьютере или телевизоре. Всё объясним обычными словами
              и покажем, куда нажать.
            </p>
            <div className="hero-actions">
              <button
                className="button button-primary button-large"
                type="button"
                onClick={onOpenAuth}
              >
                Получить 7 дней бесплатно
              </button>
              {api.isDemoMode ? (
                <button
                  className="button button-secondary button-large"
                  type="button"
                  onClick={() => navigate(routes.dashboard)}
                >
                  Посмотреть кабинет
                </button>
              ) : (
                <a className="button button-secondary button-large" href="#how">
                  Как это работает
                </a>
              )}
            </div>
            <ul className="trust-row" aria-label="Преимущества">
              {advantages.map((advantage) => (
                <li key={advantage}>
                  <Icon name="check" />
                  {advantage}
                </li>
              ))}
            </ul>
          </div>
          <div className="hero-art">
            <Mascot variant="explorer" loading="eager" />
          </div>
        </section>

        <section className="product-grid shell" id="how">
          <article className="panel panel-how">
            <div className="section-heading compact-heading">
              <div>
                <span className="section-kicker">Три простых шага</span>
                <h2>Как это работает</h2>
              </div>
              <span className="leaf-mark">
                <Icon name="leaf" />
              </span>
            </div>
            <ol className="steps">
              {steps.map((step, index) => (
                <li className="step" key={step.title}>
                  <Mascot variant={step.mascot} className="step-mascot" decorative />
                  <div className="step-copy">
                    <span className="step-number">{index + 1}</span>
                    <strong>{step.title}</strong>
                    <p>{step.text}</p>
                  </div>
                </li>
              ))}
            </ol>
          </article>

          <article className="panel panel-tariffs" id="tariffs">
            <div className="section-heading compact-heading">
              <div>
                <span className="section-kicker">Без сложных условий</span>
                <h2>Простые тарифы</h2>
              </div>
              <span className="leaf-mark">
                <Icon name="payments" />
              </span>
            </div>
            <div className="tariff-grid">
              {tariffs.map((tariff) => (
                <button
                  className={`tariff ${tariff.popular ? "is-popular" : ""}`}
                  type="button"
                  key={tariff.period}
                  onClick={onOpenAuth}
                >
                  {tariff.popular && <span className="popular-label">выгодно</span>}
                  <span>{tariff.period}</span>
                  <strong>{tariff.price}</strong>
                  {tariff.saving && <small>{tariff.saving}</small>}
                </button>
              ))}
            </div>
            <ul className="tariff-features">
              <li>
                <Icon name="check" />3 устройства
              </li>
              <li>
                <Icon name="check" />
                без лимита
              </li>
            </ul>
            <button className="add-device" type="button" onClick={onOpenAuth}>
              <Icon name="plus" />
              Дополнительное устройство за 100 ₽
            </button>
          </article>
          <article className="panel panel-devices" id="devices">
            <div className="section-heading compact-heading">
              <div>
                <span className="section-kicker">На любом экране</span>
                <h2>Все Ваши устройства</h2>
              </div>
              <span className="leaf-mark">
                <Icon name="devices" />
              </span>
            </div>
            <div className="platform-grid">
              {platforms.map((platform) => (
                <div className="platform" key={platform.name}>
                  <span className="platform-icon">
                    <Icon name={platform.icon} />
                  </span>
                  <span>{platform.name}</span>
                </div>
              ))}
            </div>
          </article>


          <article className="panel countries-panel" id="countries">
            <div className="section-heading compact-heading">
              <div>
                <span className="section-kicker">Выбор внутри приложения</span>
                <h2>Страны на каждый день</h2>
              </div>
              <span className="leaf-mark">
                <Icon name="globe" />
              </span>
            </div>
            <div className="country-list">
              {(countries.data ?? []).map((country) => (
                <span className="country-chip" key={country.code}>
                  <span aria-hidden="true">{country.flag}</span> {country.name}
                </span>
              ))}
            </div>
            <p className="muted">
              {countries.loading && !countries.data
                ? "Загружаем список…"
                : "Страна выбирается внутри приложения в один тап."}
            </p>
          </article>

          <article className="panel support-panel" id="support">
            <div className="support-heading">
              <div>
                <span className="section-kicker">Отвечаем по-человечески</span>
                <h2>Поддержка, которая помогает</h2>
                <p>
                Telegram работает без регистрации — если войти не получается,
                пишите туда.
              </p>
              </div>
              <Mascot variant="support" className="support-mascot-image" decorative />
            </div>
            <div className="support-choice">
                <a
                  className="support-option"
                  href={telegramSupportUrl}
                  target="_blank"
                  rel="noreferrer"
                >
                  <span className="support-option-icon">
                    <Icon name="telegram" />
                  </span>
                  <span className="support-option-copy">
                    <strong>Написать в Telegram</strong>
                    <small>Живой человек ответит в мессенджере</small>
                  </span>
                  <Icon name="arrow-right" />
                </a>
                <button className="support-option" type="button" onClick={openRequestForm}>
                  <span className="support-option-icon">
                    <Icon name="support" />
                  </span>
                  <span className="support-option-copy">
                    <strong>Оставить обращение</strong>
                    <small>
                      {canOpenCabinet
                        ? "Форма в кабинете — переписка сохранится"
                        : "Форма в кабинете: понадобится вход"}
                    </small>
                  </span>
                  <Icon name="arrow-right" />
                </button>
            </div>
          </article>
        </section>

        {/*
          Документы стоят перед призывом оплатить, а не после него:
          человек должен успеть их прочитать до того, как нажмёт кнопку.
        */}
        <section className="documents-section shell" id="documents">
          <div className="section-heading compact-heading">
            <div>
              <span className="section-kicker">Всё честно и заранее</span>
              <h2>Документы</h2>
              <p className="muted">
                Условия, на которых работает сервис. Открываются без
                регистрации — прочитайте до оплаты.
              </p>
            </div>
          </div>
          <div className="documents-grid">
            {legalDocuments.map((item) => (
              <a
                className="document-card"
                key={item.slug}
                href={legalPath(item.slug)}
                onClick={(event) => {
                  event.preventDefault();
                  navigate(legalPath(item.slug));
                }}
              >
                <span className="document-card-icon">
                  <Icon name="shield" />
                </span>
                <strong>{item.title}</strong>
                <p>{item.summary}</p>
                <span className="document-card-link">
                  Читать
                  <Icon name="arrow-right" />
                </span>
              </a>
            ))}
          </div>
        </section>

        <section className="final-cta shell">
          <div>
            <span className="section-kicker">Первую неделю оплачивать не нужно</span>
            <h2>Попробуйте спокойно, без обязательств</h2>
            <p>Анфиса всё покажет. Если не подойдёт, ничего отменять не придётся.</p>
          </div>
          <button
            className="button button-primary button-large"
            type="button"
            onClick={onOpenAuth}
          >
            Начать бесплатно
          </button>
        </section>
      </main>

      <footer className="footer shell">
        <div className="footer-brand">
          <Brand />
          <p>Простой доступ в интернет без лишней путаницы.</p>
        </div>
        <div className="footer-links">
          <a href="#tariffs">Тарифы</a>
          <a href="#devices">Устройства</a>
          <a href="#support">Поддержка</a>
        </div>
        {/*
          Документы отдельной группой, а не вперемешку с разделами
          страницы: их ищут глазами внизу сайта, и платёжный провайдер
          проверяет, что они доступны с любой страницы.
        */}
        <div className="footer-links footer-legal">
          {legalDocuments.map((item) => (
            <a
              key={item.slug}
              href={legalPath(item.slug)}
              onClick={(event) => {
                event.preventDefault();
                navigate(legalPath(item.slug));
              }}
            >
              {item.title}
            </a>
          ))}
        </div>
        <div className="footer-note">© VPaNfi, 2026</div>
      </footer>
    </>
  );
}
