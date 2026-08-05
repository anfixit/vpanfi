import { navigate, routes } from "../app/navigation";
import { Brand } from "../components/Brand";
import { ThemeToggle, type Theme } from "../components/ThemeToggle";
import { legalPath, type LegalDocument } from "../legal";

/*
 * Каждый документ живёт по собственному адресу: платёжному провайдеру
 * даётся прямая ссылка на оферту, а не «зайдите в раздел и найдите».
 */
export function LegalDocumentPage({
  document,
  theme,
  onToggleTheme,
}: {
  document: LegalDocument;
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
            onClick={() => navigate(routes.legal)}
          >
            Все документы
          </button>
        </div>
      </header>

      <main className="legal-page legal-document shell">
        <nav aria-label="Хлебные крошки" className="legal-breadcrumbs">
          <a
            href={routes.legal}
            onClick={(event) => {
              event.preventDefault();
              navigate(routes.legal);
            }}
          >
            Документы
          </a>
          <span aria-hidden="true">/</span>
          <span>{document.title}</span>
        </nav>

        <article className="legal-body">
          <h1>{document.title}</h1>
          <p className="legal-updated">
            Редакция от {document.updatedAt}. Постоянный адрес документа:{" "}
            <code>vpanfi.su{legalPath(document.slug)}</code>
          </p>

          {document.preamble.map((paragraph) => (
            <p className="legal-preamble" key={paragraph}>
              {paragraph}
            </p>
          ))}

          {document.sections.map((section, sectionIndex) => (
            <section className="legal-section" key={section.title}>
              <h2>
                {sectionIndex + 1}. {section.title}
              </h2>
              <ul>
                {section.items.map((item, itemIndex) => (
                  <li key={item}>
                    <span className="legal-number" aria-hidden="true">
                      {sectionIndex + 1}.{itemIndex + 1}
                    </span>
                    <span>{item}</span>
                  </li>
                ))}
              </ul>
            </section>
          ))}
        </article>
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
