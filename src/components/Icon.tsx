import type { ReactNode } from "react";

/*
 * Единый набор линейных иконок вместо эмодзи и псевдографики: эмодзи
 * рисуются по-разному в разных системах и читаются экранными дикторами
 * как случайный текст.
 */

export type IconName =
  | "home"
  | "connect"
  | "devices"
  | "payments"
  | "support"
  | "profile"
  | "check"
  | "leaf"
  | "globe"
  | "qr"
  | "refresh"
  | "plus"
  | "telegram"
  | "mail"
  | "message"
  | "sparkle"
  | "question"
  | "sun"
  | "moon"
  | "shield"
  | "bell"
  | "chevron-down"
  | "arrow-right"
  | "infinity"
  | "smartphone"
  | "laptop"
  | "monitor"
  | "terminal"
  | "tv";

const ICON_SIZE = 24;

const shapes: Record<IconName, ReactNode> = {
  home: <path d="M4 10.5 12 4l8 6.5V19a1 1 0 0 1-1 1h-4v-6H9v6H5a1 1 0 0 1-1-1z" />,
  connect: <path d="M13 3 5 13h6l-1 8 8-10h-6z" />,
  devices: (
    <>
      <rect x="3" y="5" width="12" height="10" rx="1.5" />
      <rect x="16" y="9" width="5" height="10" rx="1.5" />
      <path d="M7 19h5" />
    </>
  ),
  payments: (
    <>
      <rect x="3" y="6" width="18" height="12" rx="2" />
      <path d="M3 10h18M7 15h4" />
    </>
  ),
  support: (
    <>
      <path d="M5 13a7 7 0 0 1 14 0" />
      <rect x="3" y="13" width="4" height="6" rx="1.5" />
      <rect x="17" y="13" width="4" height="6" rx="1.5" />
      <path d="M19 19a3 3 0 0 1-3 3h-2" />
    </>
  ),
  profile: (
    <>
      <circle cx="12" cy="8.5" r="3.5" />
      <path d="M5 20a7 7 0 0 1 14 0" />
    </>
  ),
  check: <path d="m5 12.5 4.5 4.5L19 7" />,
  leaf: (
    <>
      <path d="M20 4c0 8-5 12-11 12H5c0-7 5-11 11-11z" />
      <path d="M14 8 4 20" />
    </>
  ),
  globe: (
    <>
      <circle cx="12" cy="12" r="8.5" />
      <path d="M3.5 12h17M12 3.5c2.4 2.4 3.6 5.3 3.6 8.5S14.4 18.1 12 20.5c-2.4-2.4-3.6-5.3-3.6-8.5S9.6 5.9 12 3.5z" />
    </>
  ),
  qr: (
    <>
      <rect x="4" y="4" width="6" height="6" rx="1" />
      <rect x="14" y="4" width="6" height="6" rx="1" />
      <rect x="4" y="14" width="6" height="6" rx="1" />
      <path d="M14 14h3v3h-3zM20 14v6h-3" />
    </>
  ),
  refresh: (
    <>
      <path d="M20 12a8 8 0 1 1-2.6-5.9" />
      <path d="M20 4v5h-5" />
    </>
  ),
  plus: <path d="M12 5v14M5 12h14" />,
  telegram: <path d="M21 4 3 11l6 2.2L11 20l3-4.4 5 1.6z" />,
  mail: (
    <>
      <rect x="3" y="5.5" width="18" height="13" rx="2" />
      <path d="m3.8 7 8.2 6 8.2-6" />
    </>
  ),
  message: (
    <>
      <path d="M20.5 12.5c0 3.9-3.8 7-8.5 7-1 0-2-.15-2.9-.4L4 20.5l1.5-3.6A6.6 6.6 0 0 1 3.5 12.5c0-3.9 3.8-7 8.5-7s8.5 3.1 8.5 7z" />
    </>
  ),
  sparkle: <path d="M12 3.5 14 10l6.5 2-6.5 2-2 6.5-2-6.5L3.5 12 10 10z" />,
  question: (
    <>
      <circle cx="12" cy="12" r="8.5" />
      <path d="M9.6 9.6a2.5 2.5 0 1 1 3.4 2.3c-.6.3-1 .9-1 1.6v.3" />
      <path d="M12 17.2h.01" />
    </>
  ),
  sun: (
    <>
      <circle cx="12" cy="12" r="4" />
      <path d="M12 3v2M12 19v2M3 12h2M19 12h2M5.6 5.6 7 7M17 17l1.4 1.4M18.4 5.6 17 7M7 17l-1.4 1.4" />
    </>
  ),
  moon: <path d="M20 14.5A8.5 8.5 0 0 1 9.5 4a8.5 8.5 0 1 0 10.5 10.5z" />,
  shield: (
    <>
      <path d="M12 3.5 19 6v5.5c0 4.2-2.8 7.4-7 9-4.2-1.6-7-4.8-7-9V6z" />
      <path d="m9 12 2 2 4-4" />
    </>
  ),
  bell: (
    <>
      <path d="M6.5 10a5.5 5.5 0 0 1 11 0c0 4 1.5 5.5 1.5 5.5H5S6.5 14 6.5 10z" />
      <path d="M10 18.5a2 2 0 0 0 4 0" />
    </>
  ),
  "chevron-down": <path d="m6 9.5 6 6 6-6" />,
  "arrow-right": <path d="M4 12h15M13 6l6 6-6 6" />,
  infinity: (
    <path d="M8.5 8.5a3.5 3.5 0 1 0 0 7c2.6 0 4.4-7 7-7a3.5 3.5 0 1 1 0 7c-2.6 0-4.4-7-7-7z" />
  ),
  smartphone: (
    <>
      <rect x="7" y="3" width="10" height="18" rx="2" />
      <path d="M11 17.5h2" />
    </>
  ),
  laptop: (
    <>
      <rect x="4" y="5" width="16" height="11" rx="1.5" />
      <path d="M2.5 19.5h19" />
    </>
  ),
  monitor: (
    <>
      <rect x="3" y="4" width="18" height="12" rx="1.5" />
      <path d="M9 20h6M12 16v4" />
    </>
  ),
  terminal: (
    <>
      <rect x="3" y="4" width="18" height="16" rx="2" />
      <path d="m7.5 9.5 3 2.5-3 2.5M13 15h4" />
    </>
  ),
  tv: (
    <>
      <rect x="3" y="6" width="18" height="12" rx="2" />
      <path d="m8.5 2.5 3.5 3.5 3.5-3.5" />
    </>
  ),
};

export type IconProps = {
  name: IconName;
  className?: string;
  /** Подпись, когда иконка несёт смысл сама по себе. */
  label?: string;
};

export function Icon({ name, className = "", label }: IconProps) {
  return (
    <svg
      className={`icon ${className}`.trim()}
      viewBox={`0 0 ${ICON_SIZE} ${ICON_SIZE}`}
      width={ICON_SIZE}
      height={ICON_SIZE}
      fill="none"
      stroke="currentColor"
      strokeWidth={1.7}
      strokeLinecap="round"
      strokeLinejoin="round"
      role={label ? "img" : undefined}
      aria-label={label}
      aria-hidden={label ? undefined : true}
      focusable="false"
    >
      {shapes[name]}
    </svg>
  );
}
