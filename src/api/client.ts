import {
  clearAccessToken,
  getAccessToken,
  setAccessToken,
} from "../auth/tokenStore";
import type {
  AccessTokenPayload,
  AuthProvider,
  ConnectionClient,
  DashboardPayload,
  Device,
  LoginPayload,
  Payment,
  ChangePasswordPayload,
  Country,
  RegisterPayload,
  SubscriptionLink,
  SupportTicket,
  SupportTicketPayload,
  UpdateProfilePayload,
  UserProfile,
} from "./contracts";
import {
  demoClients,
  demoCountries,
  demoDashboard,
  demoDevices,
  demoPayments,
  readDemoSubscriptionLink,
  setDemoSubscriptionLinked,
} from "./demo";

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? "/api").replace(/\/$/, "");
const DEMO_MODE = import.meta.env.VITE_DEMO_MODE !== "false";
const demoAccessToken: AccessTokenPayload = {
  accessToken: "demo-vpanfi-access-token",
  tokenType: "bearer",
  expiresIn: 15 * 60,
};

type ErrorEnvelope = {
  message?: string;
  code?: string;
  detail?: string | { message?: string; code?: string };
};

export class ApiRequestError extends Error {
  readonly status: number;
  readonly code?: string;

  constructor(message: string, status: number, code?: string) {
    super(message);
    this.name = "ApiRequestError";
    this.status = status;
    this.code = code;
  }
}

const REFRESH_PATH = "/v1/auth/refresh";

/*
 * Access-токен живёт пятнадцать минут. Без этого пользователя выбрасывало
 * бы на вход посреди работы, поэтому один раз на запрос кабинет молча
 * обновляет сеанс и повторяет попытку.
 */
let unauthorizedHandler: (() => void) | null = null;
let refreshInFlight: Promise<boolean> | null = null;

export function setUnauthorizedHandler(handler: (() => void) | null): void {
  unauthorizedHandler = handler;
}

async function refreshAccessToken(): Promise<boolean> {
  refreshInFlight ??= (async () => {
    try {
      const response = await fetch(`${API_BASE_URL}${REFRESH_PATH}`, {
        method: "POST",
        credentials: "include",
        headers: { Accept: "application/json" },
      });
      if (!response.ok) return false;

      const tokens = (await response.json()) as AccessTokenPayload;
      setAccessToken(tokens.accessToken);
      return true;
    } catch {
      return false;
    } finally {
      // Освобождаем слот в следующем тике, чтобы параллельные запросы
      // успели дождаться одного и того же обновления.
      window.setTimeout(() => {
        refreshInFlight = null;
      }, 0);
    }
  })();

  return refreshInFlight;
}

async function send(path: string, init?: RequestInit): Promise<Response> {
  const accessToken = getAccessToken();
  return fetch(`${API_BASE_URL}${path}`, {
    ...init,
    credentials: "include",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
      ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
      ...init?.headers,
    },
  });
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response = await send(path, init);

  if (response.status === 401 && path !== REFRESH_PATH) {
    if (await refreshAccessToken()) {
      response = await send(path, init);
    }

    if (response.status === 401) {
      clearAccessToken();
      unauthorizedHandler?.();
    }
  }

  if (!response.ok) {
    let message = "Не удалось выполнить запрос";
    let code: string | undefined;

    try {
      const payload = (await response.json()) as ErrorEnvelope;
      if (typeof payload.detail === "string") {
        message = payload.detail;
      } else if (payload.detail) {
        message = payload.detail.message ?? message;
        code = payload.detail.code;
      } else {
        message = payload.message ?? message;
        code = payload.code;
      }
    } catch {
      // Сервер мог вернуть пустой ответ или HTML. Пользователю показываем понятное сообщение.
    }

    throw new ApiRequestError(message, response.status, code);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  const contentType = response.headers.get("content-type") ?? "";
  if (!contentType.includes("application/json")) {
    return undefined as T;
  }

  return response.json() as Promise<T>;
}

function demoDelay<T>(value: T): Promise<T> {
  return new Promise((resolve) => window.setTimeout(() => resolve(value), 180));
}

export const api = {
  isDemoMode: DEMO_MODE,

  async register(payload: RegisterPayload): Promise<AccessTokenPayload> {
    if (DEMO_MODE) return demoDelay(demoAccessToken);
    return request<AccessTokenPayload>("/v1/auth/register", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  async login(payload: LoginPayload): Promise<AccessTokenPayload> {
    if (DEMO_MODE) return demoDelay(demoAccessToken);
    return request<AccessTokenPayload>("/v1/auth/login", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  /*
   * Восстановление пароля. Отвечаем честно, если почты нет: тот же
   * выбор, что и на входе. Иначе ошибшийся в адресе ждал бы письма,
   * которое никогда не придёт.
   */
  async requestPasswordReset(
    email: string,
  ): Promise<{ email: string; expiresInMinutes: number }> {
    if (DEMO_MODE) return demoDelay({ email, expiresInMinutes: 60 });
    return request("/v1/auth/password/reset-request", {
      method: "POST",
      body: JSON.stringify({ email }),
    });
  },

  async confirmPasswordReset(token: string, password: string): Promise<void> {
    await request("/v1/auth/password/reset", {
      method: "POST",
      body: JSON.stringify({ token, password }),
    });
  },

  async getAuthProviders(): Promise<AuthProvider[]> {
    // В демо-режиме внешнего входа нет: там нечего подтверждать.
    if (DEMO_MODE) return demoDelay([]);
    return request<AuthProvider[]>("/v1/auth/providers");
  },

  async completeOAuth(
    provider: string,
    code: string,
    state: string,
  ): Promise<AccessTokenPayload> {
    return request<AccessTokenPayload>(
      `/v1/auth/oauth/${encodeURIComponent(provider)}/callback`,
      { method: "POST", body: JSON.stringify({ code, state }) },
    );
  },

  async loginWithTelegram(
    payload: Record<string, unknown>,
  ): Promise<AccessTokenPayload> {
    return request<AccessTokenPayload>("/v1/auth/telegram", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  async unlinkProvider(provider: string): Promise<void> {
    if (DEMO_MODE) return demoDelay(undefined);
    await request<void>(
      `/v1/auth/providers/${encodeURIComponent(provider)}`,
      { method: "DELETE" },
    );
  },

  async refreshSession(): Promise<AccessTokenPayload> {
    if (DEMO_MODE) return demoDelay(demoAccessToken);
    return request<AccessTokenPayload>("/v1/auth/refresh", { method: "POST" });
  },

  async logout(): Promise<void> {
    if (DEMO_MODE) return demoDelay(undefined);
    await request<void>("/v1/auth/logout", { method: "POST" });
  },

  async getProfile(): Promise<UserProfile> {
    if (DEMO_MODE) return demoDelay(demoDashboard.profile);
    return request<UserProfile>("/v1/auth/me");
  },

  async updateProfile(payload: UpdateProfilePayload): Promise<UserProfile> {
    if (DEMO_MODE) {
      return demoDelay({ ...demoDashboard.profile, ...payload });
    }
    return request<UserProfile>("/v1/auth/me", {
      method: "PATCH",
      body: JSON.stringify(payload),
    });
  },

  async changePassword(payload: ChangePasswordPayload): Promise<void> {
    if (DEMO_MODE) return demoDelay(undefined);
    const tokens = await request<AccessTokenPayload>("/v1/auth/password", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    // Смена пароля отзывает прежние сеансы, поэтому этому устройству
    // выдаётся новый токен — иначе следующий же запрос вернул бы 401.
    setAccessToken(tokens.accessToken);
  },

  async deleteAccount(password: string): Promise<void> {
    if (DEMO_MODE) return demoDelay(undefined);
    await request<void>("/v1/auth/me", {
      method: "DELETE",
      body: JSON.stringify({ password }),
    });
  },

  async getDashboard(): Promise<DashboardPayload> {
    if (DEMO_MODE) return demoDelay(demoDashboard);
    return request<DashboardPayload>("/v1/cabinet/dashboard");
  },

  async getDevices(): Promise<Device[]> {
    if (DEMO_MODE) return demoDelay(demoDevices);
    return request<Device[]>("/v1/cabinet/devices");
  },

  async unlinkDevice(deviceId: string): Promise<void> {
    if (DEMO_MODE) return demoDelay(undefined);
    await request<void>(`/v1/cabinet/devices/${encodeURIComponent(deviceId)}`, {
      method: "DELETE",
    });
  },

  async getPayments(): Promise<Payment[]> {
    if (DEMO_MODE) return demoDelay(demoPayments);
    return request<Payment[]>("/v1/cabinet/payments");
  },

  async getCountries(): Promise<Country[]> {
    if (DEMO_MODE) return demoDelay(demoCountries);
    return request<Country[]>("/v1/cabinet/countries");
  },

  async getConnectionClients(): Promise<ConnectionClient[]> {
    if (DEMO_MODE) return demoDelay(demoClients);
    return request<ConnectionClient[]>("/v1/cabinet/connection-clients");
  },

  async getSubscription(): Promise<SubscriptionLink> {
    if (DEMO_MODE) return demoDelay(readDemoSubscriptionLink());
    return request<SubscriptionLink>("/v1/cabinet/subscription");
  },

  async linkSubscription(subscriptionLink: string): Promise<SubscriptionLink> {
    if (DEMO_MODE) {
      setDemoSubscriptionLinked(true);
      return demoDelay(readDemoSubscriptionLink());
    }
    return request<SubscriptionLink>("/v1/cabinet/subscription/link", {
      method: "POST",
      body: JSON.stringify({ subscriptionLink }),
    });
  },

  async createSupportTicket(
    payload: SupportTicketPayload,
  ): Promise<SupportTicket> {
    if (DEMO_MODE) {
      return demoDelay({
        id: "demo",
        subject: payload.message.split("\n")[0],
        status: "waiting_for_support",
      });
    }
    return request<SupportTicket>("/v1/cabinet/support", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  async unlinkSubscription(): Promise<void> {
    if (DEMO_MODE) {
      setDemoSubscriptionLinked(false);
      return demoDelay(undefined);
    }
    await request<void>("/v1/cabinet/subscription/link", { method: "DELETE" });
  },
};
