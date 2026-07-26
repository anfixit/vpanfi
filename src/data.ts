export type Tariff = {
  period: string;
  price: string;
  saving?: string;
  popular?: boolean;
};

export const tariffs: Tariff[] = [
  { period: "1 месяц", price: "300 ₽" },
  { period: "3 месяца", price: "800 ₽", saving: "экономия 11%", popular: true },
  { period: "6 месяцев", price: "1500 ₽", saving: "экономия 17%" },
];

export const platforms = [
  { name: "Android", icon: "🤖" },
  { name: "iPhone / iPad", icon: "●" },
  { name: "Windows", icon: "⊞" },
  { name: "macOS", icon: "⌘" },
  { name: "Linux", icon: "🐧" },
  { name: "Android TV", icon: "▣" },
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

export const cabinetStats = {
  daysLeft: 184,
  expiresAt: "11 ноября 2026",
  traffic: "Без лимита",
  devicesUsed: 3,
  devicesLimit: 3,
};
