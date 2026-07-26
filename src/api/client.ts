import type {
  ConnectionClient,
  DashboardPayload,
  Device,
  Payment,
} from "./contracts";
import {
  demoClients,
  demoDashboard,
  demoDevices,
  demoPayments,
} from "./demo";

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? "/api").replace(/\/$/, "");
const DEMO_MODE = import.meta.env.VITE_DEMO_MODE !== "false";

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
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    credentials: "include",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
      ...init?.headers,
    },
  });

  if (!response.ok) {
    let message = "Не удалось выполнить запрос";
    let code: string | undefined;

    try {
      const payload = (await response.json()) as { message?: string; code?: string };
      message = payload.message ?? message;
      code = payload.code;
    } catch {
      // Сервер мог вернуть пустой ответ или HTML. Пользователю показываем понятное сообщение.
    }

    throw new ApiRequestError(message, response.status, code);
  }

  return response.json() as Promise<T>;
}

function demoDelay<T>(value: T): Promise<T> {
  return new Promise((resolve) => window.setTimeout(() => resolve(value), 180));
}

export const api = {
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
