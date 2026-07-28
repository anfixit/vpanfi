/*
 * Ссылки на внешние каналы в одном месте: раньше одна и та же строка
 * повторялась в трёх файлах, и они разъехались бы при первой же правке.
 *
 * Бот и поддержка — разные адресаты: бот оформляет подписку, а в
 * поддержку пишут человеку. По умолчанию оба ведут в бота, пока
 * отдельный контакт не задан.
 */

const DEFAULT_BOT_URL = "https://t.me/VPaNfi_bot";

export const telegramBotUrl =
  import.meta.env.VITE_TELEGRAM_BOT_URL ?? DEFAULT_BOT_URL;

export const telegramSupportUrl =
  import.meta.env.VITE_TELEGRAM_SUPPORT_URL ?? telegramBotUrl;
