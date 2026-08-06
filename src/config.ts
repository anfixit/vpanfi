/*
 * Ссылки на внешние каналы в одном месте: раньше одна и та же строка
 * повторялась в трёх файлах, и они разъехались бы при первой же правке.
 *
 * Бот и поддержка — разные адресаты: бот оформляет подписку, а в
 * поддержку пишут человеку. Подстановка бота вместо контакта уводила
 * людей с вопросом в меню оформления, где отвечать некому.
 */

const DEFAULT_BOT_URL = "https://t.me/VPaNfi_bot";
const DEFAULT_SUPPORT_URL = "https://t.me/Anfikus";

export const telegramBotUrl =
  import.meta.env.VITE_TELEGRAM_BOT_URL ?? DEFAULT_BOT_URL;

export const telegramSupportUrl =
  import.meta.env.VITE_TELEGRAM_SUPPORT_URL ?? DEFAULT_SUPPORT_URL;
