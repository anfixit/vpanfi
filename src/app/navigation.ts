import { useEffect, useState } from "react";

export const routes = {
  landing: "/",
  dashboard: "/app",
  connect: "/app/connect",
  devices: "/app/devices",
  payments: "/app/payments",
  support: "/app/support",
  profile: "/app/profile",
  admin: "/admin",
  authCallback: "/auth/callback",
} as const;

export type AppRoute = (typeof routes)[keyof typeof routes];

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

export function navigate(path: AppRoute, options?: { replace?: boolean }): void {
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
