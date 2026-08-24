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
const DEFAULT_MAX_URL =
  "https://max.ru/u/f9LHodD0cOJIWTlbUHU-46ujRE3vHfFd5g5TwqeeHCpHpjK4tq5DJ1joVkM";
const DEFAULT_SUPPORT_EMAIL = "anfisa.kovganyuk@gmail.com";

export const telegramBotUrl =
  import.meta.env.VITE_TELEGRAM_BOT_URL ?? DEFAULT_BOT_URL;

export const telegramSupportUrl =
  import.meta.env.VITE_TELEGRAM_SUPPORT_URL ?? DEFAULT_SUPPORT_URL;

/*
 * Почта и MAX открываются без VPN, а телеграм — нет. До поддержки
 * доходит тот, у кого что-то сломалось, и чаще всего сломался как раз
 * VPN: телеграм в одиночку оставляет такого человека без связи.
 */
export const maxSupportUrl =
  import.meta.env.VITE_MAX_SUPPORT_URL ?? DEFAULT_MAX_URL;

export const supportEmail =
  import.meta.env.VITE_SUPPORT_EMAIL ?? DEFAULT_SUPPORT_EMAIL;
