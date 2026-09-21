/*
 * Код приглашения из ссылки ?ref=.
 *
 * Код это имя учётки пригласившего в панели, и приходит он в адресе
 * при первом заходе по ссылке. Дальше он должен дожить до покупки на
 * странице оплаты, даже если человек уйдёт с сайта и вернётся позже,
 * поэтому хранится в localStorage, а не в состоянии страницы.
 *
 * Первый пригласивший выигрывает: если код уже сохранён и ещё не
 * истёк, новый код из адреса его не перезапишет. Все обращения к
 * хранилищу идут в try/catch: приватный режим браузера и
 * заблокированное хранилище не должны ронять сайт.
 */

const STORAGE_KEY = "vpanfi.ref";
const TTL_MS = 30 * 24 * 60 * 60 * 1000;
const CODE_RE = /^[A-Za-z0-9_.-]{3,64}$/;

type StoredReferral = {
  code: string;
  savedAt: number;
};

function readStored(): StoredReferral | null {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;

    const parsed = JSON.parse(raw) as Partial<StoredReferral>;
    if (
      typeof parsed.code !== "string" ||
      typeof parsed.savedAt !== "number"
    ) {
      return null;
    }
    if (Date.now() - parsed.savedAt > TTL_MS) return null;

    return { code: parsed.code, savedAt: parsed.savedAt };
  } catch {
    return null;
  }
}

/**
 * Забрать код из ?ref= и запомнить его, если места ещё нет.
 *
 * Вызывается один раз при загрузке любой страницы, до отрисовки:
 * иначе первый переход по чужой ссылке после уже сохранённого кода
 * тихо подменил бы пригласившего.
 */
export function captureReferral(): void {
  try {
    const raw = new URLSearchParams(window.location.search).get("ref");
    if (!raw || !CODE_RE.test(raw)) return;
    if (readStored()) return;

    const value: StoredReferral = { code: raw, savedAt: Date.now() };
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(value));
  } catch {
    /* Приватный режим или заблокированное хранилище: без приглашения. */
  }
}

/** Действующий код приглашения, если он есть и не истёк. */
export function currentReferral(): string | null {
  return readStored()?.code ?? null;
}

/** Стереть код: вызывается после первой успешной оплаты по нему. */
export function clearReferral(): void {
  try {
    window.localStorage.removeItem(STORAGE_KEY);
  } catch {
    /* Нечего стирать, если хранилище недоступно. */
  }
}

/*
 * Имя учётки из адреса страницы поддержки. Приложение открывает её по
 * кнопке поддержки, а панель подставляет в адрес имя владельца подписки:
 * так человек получает свою ссылку приглашения нажимаемой, а не строкой
 * в приложении, которую нельзя ни нажать, ни скопировать.
 */
export function inviterFromUrl(): string | null {
  try {
    const raw = new URLSearchParams(window.location.search).get("u");
    return raw && CODE_RE.test(raw) ? raw : null;
  } catch {
    return null;
  }
}

export function inviteLink(username: string): string {
  return `${window.location.origin}/?ref=${encodeURIComponent(username)}`;
}
