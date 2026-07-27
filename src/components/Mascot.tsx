/*
 * Единственный источник истины по внешности Анфисы — файлы в
 * public/mascots. Утверждённый референс лежит в design/mascot.
 * Ни эмодзи, ни ASCII, ни другой персонаж вместо неё не используются.
 */

export type MascotVariant =
  | "greeting"
  | "connected"
  | "phone"
  | "laptop"
  | "support"
  | "error"
  | "qr"
  | "payment-success"
  | "subscription-active"
  | "explorer";

/* Исходный размер файлов: задаёт пропорции и держит место до загрузки. */
const INTRINSIC_SIZE = 224;

const MASCOT_DIRECTORY = "/mascots";

const labels: Record<MascotVariant, string> = {
  greeting: "Анфиса приветственно машет рукой",
  connected: "Анфиса радуется успешному подключению",
  phone: "Анфиса показывает действие на телефоне",
  laptop: "Анфиса работает за ноутбуком",
  support: "Анфиса из поддержки в гарнитуре",
  error: "Анфиса расстроена из-за ошибки",
  qr: "Анфиса держит карточку с QR-кодом",
  "payment-success": "Анфиса радуется успешной оплате",
  "subscription-active": "Анфиса довольна активной подпиской",
  explorer: "Анфиса исследует интернет-джунгли",
};

export type MascotProps = {
  variant: MascotVariant;
  className?: string;
  /** Подпись для читалок экрана. По умолчанию — описание состояния. */
  alt?: string;
  /** Декоративный режим: пустой alt и скрытие от читалок экрана. */
  decorative?: boolean;
  /** Первый экран стоит грузить сразу, остальное — лениво. */
  loading?: "eager" | "lazy";
};

export function Mascot({
  variant,
  className = "",
  alt,
  decorative = false,
  loading = "lazy",
}: MascotProps) {
  const source = `${MASCOT_DIRECTORY}/anfisa-${variant}`;

  return (
    <picture className={`mascot mascot-${variant} ${className}`.trim()}>
      <source srcSet={`${source}.avif`} type="image/avif" />
      <img
        src={`${source}.webp`}
        alt={decorative ? "" : (alt ?? labels[variant])}
        aria-hidden={decorative || undefined}
        width={INTRINSIC_SIZE}
        height={INTRINSIC_SIZE}
        loading={loading}
        decoding="async"
        draggable={false}
      />
    </picture>
  );
}
