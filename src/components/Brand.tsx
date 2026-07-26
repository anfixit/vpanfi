import { navigate, routes } from "../app/navigation";

export function Brand({ compact = false }: { compact?: boolean }) {
  return (
    <button
      className="brand"
      type="button"
      onClick={() => navigate(routes.landing)}
      aria-label="Перейти на главную VPaNfi"
    >
      <span className="brand-mark" aria-hidden="true">
        <span className="brand-ear brand-ear-left" />
        <span className="brand-ear brand-ear-right" />
        <span className="brand-face">•ᴗ•</span>
      </span>
      {!compact && <span>VPaNfi</span>}
    </button>
  );
}
