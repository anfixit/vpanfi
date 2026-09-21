/*
 * Определение устройства и ссылки «открыть в приложении».
 *
 * 21.09.2026: из десяти человек, получивших пробный период на сайте,
 * семеро не подключились ни разу. Страница подключения всегда открывалась
 * на Android, даже на айфоне, а кнопки «Открыть в приложении» вне
 * демо-режима не было вовсе: сервер не присылал для неё ссылку. Человек
 * с айфона видел Google Play и кнопку «Скопировать ключ» без объяснения,
 * куда этот ключ вставлять.
 */

export function detectPlatform(): string | null {
  try {
    const ua = navigator.userAgent;
    // iPadOS представляется как Mac, отличить его можно только по касаниям.
    const touchMac = /Macintosh/.test(ua) && navigator.maxTouchPoints > 1;
    if (/iPhone|iPad|iPod/.test(ua) || touchMac) return "iPhone / iPad";
    if (/Android/.test(ua)) {
      return /TV|AFT|BRAVIA|SmartTV/i.test(ua) ? "Android TV" : "Android";
    }
    if (/Windows/.test(ua)) return "Windows";
    if (/Macintosh|Mac OS X/.test(ua)) return "macOS";
    if (/Linux|X11/.test(ua)) return "Linux";
    return null;
  } catch {
    return null;
  }
}

/*
 * Оба приложения принимают адрес подписки как есть, без кодирования:
 * happ://add/<адрес> и incy://add/<адрес>. Для остальных приложений
 * общей схемы нет, там остаётся ключ и QR-код.
 */
export function appDeepLink(clientId: string, subscriptionUrl: string | null): string | null {
  if (!subscriptionUrl) return null;
  if (clientId.startsWith("happ")) return `happ://add/${subscriptionUrl}`;
  if (clientId.startsWith("incy")) return `incy://add/${subscriptionUrl}`;
  return null;
}
