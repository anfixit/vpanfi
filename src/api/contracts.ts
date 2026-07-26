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
  lastSeenAt: string;
  createdAt: string;
  current: boolean;
};

export type PaymentStatus = "pending" | "succeeded" | "failed" | "refunded";

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
};

export type DashboardPayload = {
  subscription: Subscription;
  countries: Country[];
  recentPayments: Payment[];
  profile: UserProfile;
};

export type ApiErrorPayload = {
  message: string;
  code?: string;
};
