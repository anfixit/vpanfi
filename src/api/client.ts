import { getAccessToken } from "../auth/tokenStore";
import type {
  AccessTokenPayload,
  ConnectionClient,
  DashboardPayload,
  Device,
  LoginPayload,
  Payment,
  RegisterPayload,
} from "./contracts";
import {
  demoClients,
  demoDashboard,
  demoDevices,
  demoPayments,
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

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const accessToken = getAccessToken();
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    credentials: "include",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
      ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
      ...init?.headers,
    },
  });

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

  async refreshSession(): Promise<AccessTokenPayload> {
    if (DEMO_MODE) return demoDelay(demoAccessToken);
    return request<AccessTokenPayload>("/v1/auth/refresh", { method: "POST" });
  },

  async logout(): Promise<void> {
    if (DEMO_MODE) return demoDelay(undefined);
    await request<void>("/v1/auth/logout", { method: "POST" });
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

  async getConnectionClients(): Promise<ConnectionClient[]> {
    if (DEMO_MODE) return demoDelay(demoClients);
    return request<ConnectionClient[]>("/v1/cabinet/connection-clients");
  },
};
