import { navigate, routes } from "../app/navigation";
import { Brand } from "../components/Brand";
import { Mascot } from "../components/Mascot";
import { ThemeToggle, type Theme } from "../components/ThemeToggle";
import { telegramSupportUrl } from "../config";
import { offerUrl, privacyPolicyUrl, serviceRules } from "../legal";

/*
 * Страница открыта без входа: платёжный провайдер проверяет документы до
 * того, как у него появится аккаунт, и человек читает их до оплаты, а не
 * после. Всё, что здесь есть, ведёт наружу на подписанные документы —
 * пересказывать их своими словами нельзя, разойдутся.
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
          <a
            className="legal-doc-card"
            href={offerUrl}
            target="_blank"
            rel="noreferrer noopener"
          >
            <strong>Публичная оферта</strong>
            <p>
              Договор между Вами и сервисом: тарифы, порядок оплаты,
              сроки и условия возврата средств.
            </p>
            <span className="legal-doc-link">Открыть документ</span>
          </a>
          <a
            className="legal-doc-card"
            href={privacyPolicyUrl}
            target="_blank"
            rel="noreferrer noopener"
          >
            <strong>Политика конфиденциальности</strong>
            <p>
              Какие данные сервис собирает, зачем, сколько хранит и как
              их удалить по Вашему требованию.
            </p>
            <span className="legal-doc-link">Открыть документ</span>
          </a>
        </section>

        <section className="legal-rules" id="rules">
          <h2>Правила использования сервиса</h2>
          <ol className="legal-rule-list">
            {serviceRules.map((rule) => (
              <li key={rule}>{rule}</li>
            ))}
          </ol>
          <p className="muted legal-support-note">
            По всем вопросам — техническая поддержка:{" "}
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
