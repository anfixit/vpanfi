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
