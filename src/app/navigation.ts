import { useEffect, useState } from "react";

export const routes = {
  landing: "/",
  /*
   * Покупка живёт отдельной страницей, а не окном: платёжная система
   * возвращает человека по адресу, и возвращать его нужно туда, где
   * видно результат, а не на главную с потерянным состоянием.
   */
  buy: "/buy",
  dashboard: "/app",
  connect: "/app/connect",
  devices: "/app/devices",
  payments: "/app/payments",
  support: "/app/support",
  profile: "/app/profile",
  admin: "/admin",
  authCallback: "/auth/callback",
  /*
   * Смена пароля по ссылке из письма. Отдельный адрес, потому что
   * человек приходит сюда из почтового ящика, а не из кабинета.
   */
  passwordReset: "/password/reset",
  legal: "/legal",
  /*
   * Помощь открыта без входа: сюда идёт тот, у кого ничего не работает,
   * и заставлять его сначала войти в кабинет нельзя.
   */
  help: "/help",
} as const;

export type AppRoute = (typeof routes)[keyof typeof routes];

/*
 * Каждый документ живёт по собственному адресу, поэтому список маршрутов
 * не может быть закрытым. Шаблонный тип оставляет проверку на месте:
 * опечатка вроде "/lega/offer" по-прежнему не пройдёт компиляцию.
 */
export type NavigablePath = AppRoute | `${typeof routes.legal}/${string}`;

function normalizePathname(pathname: string): string {
  if (pathname.length > 1 && pathname.endsWith("/")) {
    return pathname.slice(0, -1);
  }

  return pathname || routes.landing;
}

export function usePathname(): string {
  const [pathname, setPathname] = useState(() => normalizePathname(window.location.pathname));

  useEffect(() => {
    const handleLocationChange = () => setPathname(normalizePathname(window.location.pathname));

    window.addEventListener("popstate", handleLocationChange);
    return () => window.removeEventListener("popstate", handleLocationChange);
  }, []);

  return pathname;
}

export function navigate(
  path: NavigablePath,
  options?: { replace?: boolean },
): void {
  const current = normalizePathname(window.location.pathname);
  const next = normalizePathname(path);

  if (current === next) {
    window.scrollTo({ top: 0, behavior: "smooth" });
    return;
  }

  if (options?.replace) {
    window.history.replaceState({}, "", next);
  } else {
    window.history.pushState({}, "", next);
  }

  window.dispatchEvent(new PopStateEvent("popstate"));
  window.scrollTo({ top: 0 });
}

export function isCabinetRoute(pathname: string): boolean {
  return pathname === routes.dashboard || pathname.startsWith("/app/");
}
