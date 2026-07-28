import { useMemo } from "react";
import qrcode from "qrcode-generator";

/*
 * QR рисуется одним <path>: так он остаётся чётким на любом экране и
 * не тянет за собой ни canvas, ни запрос к серверу.
 */

const AUTO_TYPE_NUMBER = 0;
const ERROR_CORRECTION = "M";
const QUIET_ZONE_MODULES = 4;

function buildPath(value: string): { path: string; size: number } | null {
  try {
    const qr = qrcode(AUTO_TYPE_NUMBER, ERROR_CORRECTION);
    qr.addData(value);
    qr.make();

    const modules = qr.getModuleCount();
    const size = modules + QUIET_ZONE_MODULES * 2;
    const parts: string[] = [];

    for (let row = 0; row < modules; row += 1) {
      for (let column = 0; column < modules; column += 1) {
        if (qr.isDark(row, column)) {
          const x = column + QUIET_ZONE_MODULES;
          const y = row + QUIET_ZONE_MODULES;
          parts.push(`M${x} ${y}h1v1h-1z`);
        }
      }
    }

    return { path: parts.join(""), size };
  } catch {
    // Ссылка длиннее, чем помещается в QR максимальной версии.
    return null;
  }
}

export function QrCode({
  value,
  label,
  className = "",
}: {
  value: string;
  label: string;
  className?: string;
}) {
  const code = useMemo(() => buildPath(value), [value]);

  if (!code) {
    return (
      <p className="muted">
        Ссылка слишком длинная для QR-кода — воспользуйтесь кнопкой
        «Скопировать ключ».
      </p>
    );
  }

  return (
    <svg
      className={`qr-code ${className}`.trim()}
      viewBox={`0 0 ${code.size} ${code.size}`}
      role="img"
      aria-label={label}
      shapeRendering="crispEdges"
    >
      <rect width={code.size} height={code.size} fill="#fff" />
      <path d={code.path} fill="#191c1d" />
    </svg>
  );
}
