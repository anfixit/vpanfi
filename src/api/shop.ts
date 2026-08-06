/*
 * Витрина и покупка.
 *
 * Тарифы, цены и приём денег живут в боте — он и остаётся единственной
 * кассой. Сайт ничего не считает сам: он показывает то, что отдал бот, и
 * возвращает человеку ссылку на оплату. Иначе при первом же изменении
 * цены сайт и бот начали бы называть разные суммы.
 *
 * Запросы идут на свой домен, а не напрямую в бот: политика безопасности
 * страницы разрешает обращения только к своему origin, и nginx
 * проксирует /shop/ дальше (см. nginx.conf).
 */

import type {
  GuestPurchase,
  GuestPurchasePayload,
  GuestPurchaseStatus,
  ShopConfig,
  ShopPaymentMethod,
  ShopTariff,
} from "./contracts";

/** Адрес витрины в боте. Задан при создании страницы продаж. */
const SHOP_SLUG = "vpanfi";
const SHOP_BASE = "/shop";

const FALLBACK_ERROR = "Не удалось связаться с сервисом. Попробуйте ещё раз.";

export class ShopRequestError extends Error {
  readonly code?: string;

  constructor(message: string, code?: string) {
    super(message);
    this.name = "ShopRequestError";
    this.code = code;
  }
}

/* Бот отвечает snake_case, сайт живёт в camelCase. Разбор — в одном месте. */
type RawPeriod = {
  days: number;
  price_kopeks: number;
  price_label?: string | null;
};

type RawTariff = {
  id: number;
  name: string;
  description?: string | null;
  device_limit: number;
  traffic_limit_gb: number;
  periods: RawPeriod[];
};

type RawPaymentMethod = {
  method_id: string;
  display_name?: string | null;
  sub_options?: { id: string; name: string }[] | null;
};

type RawConfig = {
  title: string;
  subtitle?: string | null;
  tariffs: RawTariff[];
  payment_methods: RawPaymentMethod[];
};

function formatPrice(kopeks: number): string {
  return `${Math.round(kopeks / 100).toLocaleString("ru-RU")} ₽`;
}

function toTariff(raw: RawTariff): ShopTariff {
  return {
    id: raw.id,
    name: raw.name,
    description: raw.description ?? null,
    deviceLimit: raw.device_limit,
    trafficLimitGb: raw.traffic_limit_gb,
    periods: raw.periods.map((period) => ({
      days: period.days,
      priceKopeks: period.price_kopeks,
      // Метка приходит от бота; своя нужна только если он её не прислал.
      priceLabel: period.price_label || formatPrice(period.price_kopeks),
    })),
  };
}

function toPaymentMethod(raw: RawPaymentMethod): ShopPaymentMethod {
  const options = (raw.sub_options ?? []).map((option) => ({
    id: option.id,
    name: option.name,
  }));

  return {
    methodId: raw.method_id,
    // У Platega имя пустое, зато варианты названы понятно — берём первый.
    name: raw.display_name || options[0]?.name || raw.method_id,
    options,
  };
}

async function shopRequest<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;

  try {
    response = await fetch(`${SHOP_BASE}${path}`, {
      ...init,
      headers: {
        "Content-Type": "application/json",
        ...(init?.headers ?? {}),
      },
    });
  } catch {
    throw new ShopRequestError(FALLBACK_ERROR);
  }

  if (!response.ok) {
    let message = FALLBACK_ERROR;
    let code: string | undefined;

    try {
      const payload = (await response.json()) as {
        detail?: string | { message?: string; code?: string };
      };
      if (typeof payload.detail === "string") {
        message = payload.detail;
      } else if (payload.detail) {
        message = payload.detail.message ?? message;
        code = payload.detail.code;
      }
    } catch {
      /* Сервер мог ответить пустым телом или HTML — оставляем общий текст. */
    }

    throw new ShopRequestError(message, code);
  }

  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export const shop = {
  /** Тарифы и способы оплаты — те же, что видит покупатель в боте. */
  async getConfig(): Promise<ShopConfig> {
    const raw = await shopRequest<RawConfig>(`/${SHOP_SLUG}`);
    return {
      title: raw.title,
      subtitle: raw.subtitle ?? null,
      tariffs: (raw.tariffs ?? []).map(toTariff),
      paymentMethods: (raw.payment_methods ?? []).map(toPaymentMethod),
    };
  },

  /*
   * Покупка без регистрации: почта нужна, чтобы узнать человека при
   * следующем заходе, и не более того. Аккаунт заводит бот сам.
   */
  async createPurchase(payload: GuestPurchasePayload): Promise<GuestPurchase> {
    const raw = await shopRequest<{ token: string; payment_url?: string | null }>(
      `/${SHOP_SLUG}/purchase`,
      {
        method: "POST",
        body: JSON.stringify({
          tariff_id: payload.tariffId,
          period_days: payload.periodDays,
          contact_type: "email",
          contact_value: payload.email,
          payment_method: payload.paymentMethod,
        }),
      },
    );

    return { token: raw.token, paymentUrl: raw.payment_url ?? null };
  },

  /*
   * Состояние оплаты. Платёж подтверждает вебхук от платёжной системы,
   * поэтому страница результата спрашивает сервер, а не доверяет тому,
   * что человек вернулся: вернуться можно и не заплатив.
   */
  async getPurchaseStatus(token: string): Promise<GuestPurchaseStatus> {
    const raw = await shopRequest<{
      status: string;
      subscription_url?: string | null;
    }>(`/purchase/${encodeURIComponent(token)}`);

    return {
      status: raw.status,
      paid: raw.status === "paid" || raw.status === "activated",
      subscriptionUrl: raw.subscription_url ?? null,
    };
  },
};
