/*
 * Документы сервиса.
 *
 * Раньше они лежали на telegra.ph и подставлялись ссылками из
 * переменных окружения. Теперь они живут на собственном домене: адрес
 * вида vpanfi.su/legal/offer выглядит для платёжного провайдера как
 * документ продавца, а не как чужая публикация, и не может исчезнуть
 * вместе со сторонним сервисом.
 */

import { offer } from "./offer";
import { privacy } from "./privacy";
import { rules } from "./rules";
import type { LegalDocument } from "./types";

export { requisites } from "./requisites";
export type { LegalDocument, LegalSection } from "./types";

/** Порядок важен: он же используется в футере и при регистрации. */
export const legalDocuments: readonly LegalDocument[] = [
  offer,
  privacy,
  rules,
];

export function legalPath(
  slug: LegalDocument["slug"],
): `/legal/${LegalDocument["slug"]}` {
  return `/legal/${slug}`;
}

export function findLegalDocument(
  pathname: string,
): LegalDocument | undefined {
  return legalDocuments.find((item) => legalPath(item.slug) === pathname);
}
