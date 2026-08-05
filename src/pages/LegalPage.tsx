import { navigate, routes } from "../app/navigation";
import { Brand } from "../components/Brand";
import { Mascot } from "../components/Mascot";
import { ThemeToggle, type Theme } from "../components/ThemeToggle";
import { telegramSupportUrl } from "../config";
import { legalDocuments, legalPath, requisites } from "../legal";

/*
 * Страница открыта без входа: её читают до регистрации и до оплаты, а
 * платёжный провайдер проверяет ещё до появления аккаунта.
 */
export function LegalPage({
  theme,
  onToggleTheme,
}: {
  theme: Theme;
  onToggleTheme: () => void;
}) {
  return (
    <>
      <header className="site-header shell">
        <Brand />
        <div className="header-actions">
          <ThemeToggle theme={theme} onToggle={onToggleTheme} />
          <button
            className="button button-ghost"
            type="button"
            onClick={() => navigate(routes.landing)}
          >
            На главную
          </button>
        </div>
      </header>

      <main className="legal-page shell">
        <section className="legal-intro">
          <div>
            <span className="eyebrow-plain">Документы</span>
            <h1>Условия использования VPaNfi</h1>
            <p className="muted">
              Здесь собрано всё, что определяет отношения между Вами и
              сервисом. Оплата подписки означает согласие с этими
              документами, поэтому прочитайте их заранее.
            </p>
          </div>
          <Mascot variant="support" className="legal-mascot" decorative />
        </section>

        <section className="legal-docs">
          {legalDocuments.map((item) => (
            <a
              className="legal-doc-card"
              key={item.slug}
              href={legalPath(item.slug)}
              onClick={(event) => {
                event.preventDefault();
                navigate(legalPath(item.slug));
              }}
            >
              <strong>{item.title}</strong>
              <p>{item.summary}</p>
              <span className="legal-doc-link">
                Читать · редакция от {item.updatedAt}
              </span>
            </a>
          ))}
        </section>

        <section className="legal-requisites">
          <h2>Сведения об исполнителе</h2>
          <dl>
            <div>
              <dt>Исполнитель</dt>
              <dd>{requisites.legalName}</dd>
            </div>
            <div>
              <dt>ОГРНИП</dt>
              <dd>{requisites.ogrnip}</dd>
            </div>
            <div>
              <dt>ИНН</dt>
              <dd>{requisites.inn}</dd>
            </div>
            <div>
              <dt>Дата регистрации</dt>
              <dd>{requisites.registeredAt}</dd>
            </div>
            <div>
              <dt>Регистрирующий орган</dt>
              <dd>{requisites.registrar}</dd>
            </div>
            <div>
              <dt>Электронная почта</dt>
              <dd>
                <a href={`mailto:${requisites.email}`}>{requisites.email}</a>
              </dd>
            </div>
          </dl>
          <p className="muted legal-support-note">
            По вопросам работы сервиса — техническая поддержка:{" "}
            <a href={telegramSupportUrl} target="_blank" rel="noreferrer noopener">
              написать в Telegram
            </a>
            .
          </p>
        </section>
      </main>

      <footer className="footer shell">
        <div className="footer-brand">
          <Brand />
          <p>Простой доступ в интернет без лишней путаницы.</p>
        </div>
        <div className="footer-note">© VPaNfi, 2026</div>
      </footer>
    </>
  );
}
