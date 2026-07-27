import type { IconName } from "./components/Icon";

export type Tariff = {
  period: string;
  price: string;
  priceRub: number;
  saving?: string;
  popular?: boolean;
};

export const tariffs: Tariff[] = [
  { period: "1 месяц", price: "300 ₽", priceRub: 300 },
  {
    period: "3 месяца",
    price: "800 ₽",
    priceRub: 800,
    saving: "экономия 11%",
    popular: true,
  },
  { period: "6 месяцев", price: "1500 ₽", priceRub: 1500, saving: "экономия 17%" },
];

export type Platform = {
  name: string;
  icon: IconName;
};

export const platforms: Platform[] = [
  { name: "Android", icon: "smartphone" },
  { name: "iPhone / iPad", icon: "smartphone" },
  { name: "Windows", icon: "monitor" },
  { name: "macOS", icon: "laptop" },
  { name: "Linux", icon: "terminal" },
  { name: "Android TV", icon: "tv" },
  { name: "Apple TV", icon: "tv" },
];

export const countries = [
  { name: "Нидерланды", flag: "🇳🇱" },
  { name: "Германия", flag: "🇩🇪" },
  { name: "США", flag: "🇺🇸" },
  { name: "Испания", flag: "🇪🇸" },
  { name: "Япония", flag: "🇯🇵" },
  { name: "Казахстан", flag: "🇰🇿" },
];

export const EXTRA_DEVICE_PRICE_RUB = 100;
