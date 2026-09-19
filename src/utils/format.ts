const rubFormatter = new Intl.NumberFormat("ru-RU", {
  style: "currency",
  currency: "RUB",
  maximumFractionDigits: 0,
});

export function formatRubles(amount: number): string {
  return rubFormatter.format(amount);
}

const dateFormatter = new Intl.DateTimeFormat("ru-RU", {
  day: "numeric",
  month: "long",
  year: "numeric",
});

const dateTimeFormatter = new Intl.DateTimeFormat("ru-RU", {
  day: "numeric",
  month: "long",
  hour: "2-digit",
  minute: "2-digit",
});

/*
 * Панель отдаёт метки времени в ISO. Показывать их пользователю как есть
 * значит показывать строку вида 2026-07-27T19:04:36.797000Z.
 */
export function formatDate(value: string | null | undefined): string {
  if (!value) return "нет данных";

  const moment = new Date(value);
  if (Number.isNaN(moment.getTime())) return value;

  return dateFormatter.format(moment);
}

export function formatDateTime(value: string | null | undefined): string {
  if (!value) return "нет данных";

  const moment = new Date(value);
  if (Number.isNaN(moment.getTime())) return value;

  return dateTimeFormatter.format(moment);
}

/*
 * Русское склонение по числу: «1 друг», «2 друга», «5 друзей». Числа,
 * заканчивающиеся на 11-14, всегда берут форму «many» независимо от
 * последней цифры: иначе «11 друг» вместо «11 друзей».
 */
export function pluralizeRu(
  count: number,
  one: string,
  few: string,
  many: string,
): string {
  const mod10 = count % 10;
  const mod100 = count % 100;

  if (mod100 >= 11 && mod100 <= 14) return many;
  if (mod10 === 1) return one;
  if (mod10 >= 2 && mod10 <= 4) return few;
  return many;
}
