/*
 * Пререндер юридических страниц.
 *
 * Документы читает не только человек в браузере. Их открывает платёжный
 * провайдер, их забирает Telegram, когда строит превью ссылки, их
 * индексируют поисковики. Все они читают HTML, пришедший с сервера, и не
 * выполняют JavaScript — а страница собиралась целиком на клиенте, и
 * наружу уходил пустой <div id="root">. Снаружи документы выглядели
 * несуществующими: Telegram потерял Instant View, который был у прежних
 * страниц на telegra.ph.
 *
 * Поэтому после сборки рядом с приложением кладутся готовые страницы с
 * полным текстом. Браузер поверх них поднимает обычное приложение и
 * заменяет разметку своей, а всем остальным достаётся текст.
 */

import { mkdir, readFile, rm, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { build } from "vite";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const dist = path.join(root, "dist");
const ssrDir = path.join(root, ".prerender");

/*
 * Документы лежат в TypeScript, а Node их напрямую не читает. Собираем
 * их тем же Vite, что и остальное приложение: отдельный инструмент для
 * этого заводить незачем, и версия транспайлера гарантированно совпадёт
 * со сборкой сайта.
 */
await build({
  root,
  logLevel: "warn",
  build: {
    ssr: path.join(root, "src/legal/index.ts"),
    outDir: ssrDir,
    emptyOutDir: true,
    rollupOptions: { output: { entryFileNames: "legal.mjs" } },
  },
});

const { legalDocuments, legalPath, requisites } = await import(
  path.join(ssrDir, "legal.mjs")
);

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

/* Разметка повторяет LegalDocumentPage: те же классы и та же нумерация. */
function renderDocument(document) {
  const preamble = document.preamble
    .map((paragraph) => `<p class="legal-preamble">${escapeHtml(paragraph)}</p>`)
    .join("");

  const sections = document.sections
    .map((section, sectionIndex) => {
      const items = section.items
        .map(
          (item, itemIndex) =>
            `<li><span class="legal-number" aria-hidden="true">` +
            `${sectionIndex + 1}.${itemIndex + 1}</span>` +
            `<span>${escapeHtml(item)}</span></li>`,
        )
        .join("");
      return (
        `<section class="legal-section"><h2>` +
        `${sectionIndex + 1}. ${escapeHtml(section.title)}</h2>` +
        `<ul>${items}</ul></section>`
      );
    })
    .join("");

  return (
    `<main class="legal-page legal-document shell"><article class="legal-body">` +
    `<h1>${escapeHtml(document.title)}</h1>` +
    `<p class="legal-updated">Редакция от ${escapeHtml(document.updatedAt)}. ` +
    `Постоянный адрес документа: <code>vpanfi.su${legalPath(document.slug)}</code></p>` +
    `${preamble}${sections}</article></main>`
  );
}

function renderIndex() {
  const items = legalDocuments
    .map(
      (document) =>
        `<li><h2><a href="${legalPath(document.slug)}">` +
        `${escapeHtml(document.title)}</a></h2>` +
        `<p>${escapeHtml(document.summary)}</p>` +
        `<p class="legal-updated">Редакция от ${escapeHtml(document.updatedAt)}.</p></li>`,
    )
    .join("");

  return (
    `<main class="legal-page shell"><article class="legal-body">` +
    `<h1>Условия использования VPaNfi</h1>` +
    `<p>Здесь собрано всё, что определяет отношения между Вами и сервисом. ` +
    `Оплата подписки означает согласие с этими документами.</p>` +
    `<ul>${items}</ul>` +
    `<p>${escapeHtml(requisites.legalName)}, ОГРНИП ${escapeHtml(requisites.ogrnip)}, ` +
    `ИНН ${escapeHtml(requisites.inn)}.</p>` +
    `</article></main>`
  );
}

const shell = await readFile(path.join(dist, "index.html"), "utf8");

function withShell(body, title, description) {
  const filled = shell
    .replace(/<title>[\s\S]*?<\/title>/, `<title>${escapeHtml(title)}</title>`)
    .replace(
      /(<meta\s+name="description"\s+content=")[\s\S]*?(")/,
      `$1${escapeHtml(description)}$2`,
    )
    .replace('<div id="root"></div>', `<div id="root">${body}</div>`);

  /* Пустой #root означает, что разметка сборщика изменилась и текст никуда не попал. */
  if (!filled.includes('<div id="root">' + body.slice(0, 40))) {
    throw new Error("Пререндер не смог вставить текст в оболочку страницы");
  }
  return filled;
}

const pages = [
  {
    file: path.join(dist, "legal", "index.html"),
    html: withShell(
      renderIndex(),
      "Документы VPaNfi",
      "Оферта, политика конфиденциальности и правила использования сервиса VPaNfi.",
    ),
  },
  ...legalDocuments.map((document) => ({
    file: path.join(dist, "legal", document.slug, "index.html"),
    html: withShell(
      renderDocument(document),
      `${document.title} — VPaNfi`,
      document.summary,
    ),
  })),
];

for (const page of pages) {
  await mkdir(path.dirname(page.file), { recursive: true });
  await writeFile(page.file, page.html, "utf8");
}

await rm(ssrDir, { recursive: true, force: true });

console.log(`Пререндер: подготовлено страниц — ${pages.length}`);
