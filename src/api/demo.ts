import type {
  ConnectionClient,
  Country,
  DashboardPayload,
  Device,
  Payment,
  SubscriptionLink,
} from "./contracts";

export const demoCountries: Country[] = [
  { code: "NL", name: "Нидерланды", flag: "🇳🇱", available: true },
  { code: "DE", name: "Германия", flag: "🇩🇪", available: true },
  { code: "AT", name: "Австрия", flag: "🇦🇹", available: true },
  { code: "US", name: "США", flag: "🇺🇸", available: true },
  { code: "KZ", name: "Казахстан", flag: "🇰🇿", available: true },
  { code: "ES", name: "Испания", flag: "🇪🇸", available: true },
  { code: "JP", name: "Япония", flag: "🇯🇵", available: true },
];

export const demoPayments: Payment[] = [
  {
    id: "pay_2026_05_11",
    createdAt: "11 мая 2026",
    description: "Продление на 6 месяцев",
    amountRub: 1500,
    status: "succeeded",
  },
  {
    id: "pay_2025_11_11",
    createdAt: "11 ноября 2025",
    description: "Продление на 3 месяца",
    amountRub: 800,
    status: "succeeded",
  },
  {
    id: "pay_2025_08_11",
    createdAt: "11 августа 2025",
    description: "Подключение на 1 месяц",
    amountRub: 300,
    status: "succeeded",
  },
];

export const demoDevices: Device[] = [
  {
    id: "device_android",
    name: "Samsung Galaxy",
    platform: "Android",
    lastSeenAt: "сегодня, 08:42",
    createdAt: "18 июля 2026",
    current: true,
  },
  {
    id: "device_macos",
    name: "MacBook Air",
    platform: "macOS",
    lastSeenAt: "вчера, 22:10",
    createdAt: "3 июля 2026",
    current: false,
  },
  {
    id: "device_tv",
    name: "Телевизор",
    platform: "Android TV",
    lastSeenAt: "24 июля, 20:16",
    createdAt: "12 июня 2026",
    current: false,
  },
];

export const demoClients: ConnectionClient[] = [
  {
    id: "happ-android",
    name: "HAPP",
    platform: "Android",
    recommended: true,
    description: "Самый простой вариант. Устанавливается и подключается в пару нажатий.",
    installUrl: "https://play.google.com/store/apps/details?id=com.happproxy",
    deepLink: "happ://add/demo-vpanfi-subscription",
  },
  {
    id: "happ-ios",
    name: "HAPP",
    platform: "iPhone / iPad",
    recommended: true,
    description: "Основное приложение для iPhone и iPad.",
    installUrl: "https://apps.apple.com/",
    deepLink: "happ://add/demo-vpanfi-subscription",
  },
  {
    id: "happ-windows",
    name: "HAPP",
    platform: "Windows",
    recommended: true,
    description: "Подходит для быстрого подключения на Windows.",
    installUrl: "https://github.com/Happ-proxy/happ-desktop/releases",
  },
  {
    id: "happ-macos",
    name: "HAPP",
    platform: "macOS",
    recommended: true,
    description: "Основное приложение для компьютеров Mac.",
    installUrl: "https://apps.apple.com/",
  },
  {
    id: "v2rayn-windows",
    name: "v2rayN",
    platform: "Windows",
    recommended: false,
    description: "Дополнительный вариант для опытных пользователей.",
    installUrl: "https://github.com/2dust/v2rayN/releases",
  },
  {
    id: "shadowrocket-ios",
    name: "Shadowrocket",
    platform: "iPhone / iPad",
    recommended: false,
    description: "Платное приложение с расширенными настройками.",
    installUrl: "https://apps.apple.com/",
  },
  {
    id: "nekobox-linux",
    name: "NekoBox",
    platform: "Linux",
    recommended: true,
    description: "Понятный клиент для Linux.",
    installUrl: "https://github.com/MatsuriDayo/nekoray/releases",
  },
  {
    id: "happ-android-tv",
    name: "HAPP",
    platform: "Android TV",
    recommended: true,
    description: "Удобное подключение телевизора и приставки.",
    installUrl: "https://play.google.com/",
  },
  {
    id: "shadowrocket-apple-tv",
    name: "Shadowrocket",
    platform: "Apple TV",
    recommended: true,
    description: "Подключение Apple TV через знакомое приложение.",
    installUrl: "https://apps.apple.com/",
  },
];

export const demoDashboard: DashboardPayload = {
  subscription: {
    status: "active",
    planName: "6 месяцев",
    daysLeft: 184,
    expiresAt: "11 ноября 2026",
    trafficLabel: "Без лимита",
    devicesUsed: demoDevices.length,
    devicesLimit: 3,
    autoRenewEnabled: true,
    balanceRub: 0,
  },
  countries: demoCountries,
  recentPayments: demoPayments,
  profile: {
    id: "user_demo",
    displayName: "Алексей",
    email: "alexey@vpanfi.demo",
    telegramLinked: true,
    yandexLinked: false,
    vkLinked: false,
    passwordEnabled: true,
  },
};

/*
 * Демо-режим держит состояние привязки в памяти, чтобы оба экрана —
 * и «подписка не привязана», и привязанная — можно было посмотреть
 * по-настоящему, а не только на скриншоте.
 */
let demoLinked = true;

export function readDemoSubscriptionLink(): SubscriptionLink {
  return demoLinked
    ? {
        linked: true,
        panelUsername: "anfisa-demo",
        subscription: demoDashboard.subscription,
      }
    : { linked: false, panelUsername: null, subscription: null };
}

export function setDemoSubscriptionLinked(linked: boolean): void {
  demoLinked = linked;
}
