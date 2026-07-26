import { checkingMascotData } from "../assets/checking-mascot-data";
import { greetingMascotData } from "../assets/greeting-mascot-data";
import { successMascotData } from "../assets/success-mascot-data";

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

/*
 * Пока в репозитории находятся первые три точных вырезки из утверждённого
 * листа. Для ещё не добавленных состояний используется только утверждённая
 * Анфиса, а не эмодзи или другой рисунок. По мере добавления файлов эта карта
 * будет заменена на десять самостоятельных изображений.
 */
const mascotSources: Record<MascotVariant, string> = {
  greeting: greetingMascotData,
  success: successMascotData,
  checking: checkingMascotData,
  working: checkingMascotData,
  support: greetingMascotData,
  error: checkingMascotData,
  qr: greetingMascotData,
  payment: successMascotData,
  subscription: successMascotData,
  explorer: greetingMascotData,
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
    <img
      className={`mascot mascot-${variant} ${className}`.trim()}
      src={mascotSources[variant]}
      alt={decorative ? "" : labels[variant]}
      aria-hidden={decorative || undefined}
      draggable={false}
    />
  );
}
