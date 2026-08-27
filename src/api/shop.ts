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
  CheckoutPaymentMethod,
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
   * Способы оплаты спрашиваем у своей кассы, а не у витрины бота:
   * та описывает мерчант бота, где включены СБП и криптовалюта, а
   * карты нет. Наш мерчант принимает и карту.
   */
  async getPaymentMethods(): Promise<CheckoutPaymentMethod[]> {
    const response = await fetch("/api/v1/payments/methods");
    if (!response.ok) return [];
    return (await response.json()) as CheckoutPaymentMethod[];
  },

  /*
   * Покупка без регистрации: почта нужна, чтобы узнать человека при
   * следующем заходе, и не более того.
   *
   * Деньги принимает сайт своей кассой. Раньше покупку создавал бот, и
   * платёж уходил на его мерчант; теперь тарифы мы по-прежнему читаем у
   * бота, чтобы цены не разъехались, а касса своя. Сумму сюда не
   * передаём намеренно: её выясняет сервер, иначе цену можно было бы
   * назначить себе самому.
   */
  async createPurchase(payload: GuestPurchasePayload): Promise<GuestPurchase> {
    const response = await fetch("/api/v1/payments/checkout", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        email: payload.email,
        tariffId: payload.tariffId,
        periodDays: payload.periodDays,
        /*
         * Выбранный способ раньше собирался на странице и терялся
         * здесь: в теле уходили только почта, тариф и срок. Человек
         * отмечал криптовалюту и всё равно уезжал в СБП.
         */
        ...(payload.paymentMethod === null
          ? {}
          : { paymentMethod: payload.paymentMethod }),
      }),
    });

    if (!response.ok) {
      throw new ShopRequestError(FALLBACK_ERROR);
    }

    const raw = (await response.json()) as {
      paymentId: string;
      redirectUrl: string;
    };

    return { token: raw.paymentId, paymentUrl: raw.redirectUrl };
  },

  /*
   * Состояние оплаты. Платёж подтверждает вебхук от платёжной системы,
   * поэтому страница результата спрашивает сервер, а не доверяет тому,
   * что человек вернулся: вернуться можно и не заплатив.
   *
   * Токен здесь — идентификатор нашего платежа. У бота его нет, и
   * прежний запрос к нему ответил бы «не найдено», а страница ждала бы
   * подтверждения вечно.
   */
  async getPurchaseStatus(token: string): Promise<GuestPurchaseStatus> {
    const response = await fetch(
      `/api/v1/payments/${encodeURIComponent(token)}`,
    );

    if (!response.ok) {
      throw new ShopRequestError(FALLBACK_ERROR);
    }

    const raw = (await response.json()) as {
      status: string;
      paid: boolean;
      subscriptionUrl?: string | null;
    };

    return {
      status: raw.status,
      done: raw.paid,
      failed: raw.status === "failed" || raw.status === "cancelled",
      subscriptionUrl: raw.subscriptionUrl ?? null,
};
  },
};
