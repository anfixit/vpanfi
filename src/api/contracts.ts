export type SubscriptionStatus = "trial" | "active" | "expired" | "disabled";

export type Subscription = {
  status: SubscriptionStatus;
  planName: string;
  daysLeft: number;
  expiresAt: string;
  trafficLabel: string;
  devicesUsed: number;
  devicesLimit: number;
  autoRenewEnabled: boolean;
  balanceRub: number;
};

export type Country = {
  code: string;
  name: string;
  flag: string;
  available: boolean;
};

export type Device = {
  id: string;
  name: string;
  platform: string;
  lastSeenAt: string | null;
  createdAt: string;
  current: boolean;
};

export type PaymentStatus = "pending" | "succeeded" | "failed" | "refunded" | "cancelled";

export type Payment = {
  id: string;
  createdAt: string;
  description: string;
  amountRub: number;
  status: PaymentStatus;
};

export type ConnectionClient = {
  id: string;
  name: string;
  platform: string;
  recommended: boolean;
  description: string;
  installUrl: string;
  deepLink?: string;
};

export type UserProfile = {
  id: string;
  displayName: string;
  email: string;
  telegramLinked: boolean;
  yandexLinked: boolean;
  vkLinked: boolean;
  passwordEnabled: boolean;
  isAdmin: boolean;
};

export type DashboardPayload = {
  subscription: Subscription | null;
  countries: Country[];
  recentPayments: Payment[];
  profile: UserProfile;
};

export type RegisterPayload = {
  displayName: string;
  email: string;
  password: string;
};

export type UpdateProfilePayload = {
  displayName: string;
  email: string;
};

export type AuthProvider = {
  provider: "telegram" | "vk" | "yandex";
  name: string;
  authorizationUrl: string | null;
  botUsername: string | null;
};

export type ChangePasswordPayload = {
  currentPassword: string;
  newPassword: string;
};

export type LoginPayload = {
  email: string;
  password: string;
};

export type AccessTokenPayload = {
  accessToken: string;
  tokenType: "bearer";
  expiresIn: number;
};

export type ApiErrorPayload = {
  message: string;
  code?: string;
};

export type SubscriptionLink = {
  linked: boolean;
  panelUsername: string | null;
  subscriptionUrl: string | null;
  subscription: Subscription | null;
};

export type SubscriptionLinkPayload = {
  subscriptionLink: string;
};

/*
 * Витрина и покупка приходят от бота: тарифы, цены и приём платежей
 * живут в нём, и вторая их копия на сайте означала бы вторую кассу.
 *
 * Цены приходят и числом, и уже отформатированной строкой. Строку и
 * показываем: округление и знак валюты задаются настройками бота, и
 * повторять эту логику на сайте — верный способ разойтись с ним на рубль.
 */
export type ShopPeriod = {
  days: number;
  priceKopeks: number;
  priceLabel: string;
};

export type ShopTariff = {
  id: number;
  name: string;
  description: string | null;
  deviceLimit: number;
  /** 0 — безлимит. */
  trafficLimitGb: number;
  periods: ShopPeriod[];
};

/** Способ оплаты и его варианты: у Platega это СБП и криптовалюта. */
export type ShopPaymentOption = {
  id: string;
  name: string;
};

export type ShopPaymentMethod = {
  methodId: string;
  name: string;
  options: ShopPaymentOption[];
};

export type ShopConfig = {
  title: string;
  subtitle: string | null;
  tariffs: ShopTariff[];
  paymentMethods: ShopPaymentMethod[];
};

export type GuestPurchasePayload = {
  tariffId: number;
  periodDays: number;
  email: string;
  paymentMethod: string;
};

export type GuestPurchase = {
  token: string;
  paymentUrl: string | null;
};

/*
 * Оплату подтверждает вебхук от платёжной системы, поэтому страница
 * результата опрашивает статус, а не верит возврату из платёжки:
 * вернуться человек может и сам, не заплатив.
 */
export type GuestPurchaseStatus = {
  status: string;
  /** Подписка выдана — можно показывать ссылку. */
  done: boolean;
  /** Оплата не состоится: платёж отклонён или счёт протух. */
  failed: boolean;
  subscriptionUrl: string | null;
};
