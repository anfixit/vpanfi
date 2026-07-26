export type MascotVariant =
  | "greeting"
  | "success"
  | "checking"
  | "working"
  | "support"
  | "error"
  | "qr"
  | "payment"
  | "subscription"
  | "explorer";

const positions: Record<MascotVariant, string> = {
  greeting: "0% 0%",
  success: "25% 0%",
  checking: "50% 0%",
  working: "75% 0%",
  support: "100% 0%",
  error: "0% 100%",
  qr: "25% 100%",
  payment: "50% 100%",
  subscription: "75% 100%",
  explorer: "100% 100%",
};

const labels: Record<MascotVariant, string> = {
  greeting: "Анфиса приветствует Вас",
  success: "Анфиса радуется успешному подключению",
  checking: "Анфиса проверяет подключение",
  working: "Анфиса работает за ноутбуком",
  support: "Анфиса из поддержки",
  error: "Анфиса расстроена из-за ошибки",
  qr: "Анфиса показывает QR-код",
  payment: "Анфиса празднует успешную оплату",
  subscription: "Анфиса с активной подпиской и бананом",
  explorer: "Анфиса исследует интернет-джунгли",
};

export function Mascot({
  variant,
  className = "",
  decorative = false,
}: {
  variant: MascotVariant;
  className?: string;
  decorative?: boolean;
}) {
  return (
    <span
      className={`mascot mascot-${variant} ${className}`.trim()}
      style={{ backgroundPosition: positions[variant] }}
      role={decorative ? undefined : "img"}
      aria-hidden={decorative || undefined}
      aria-label={decorative ? undefined : labels[variant]}
    />
  );
}
