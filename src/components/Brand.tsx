import { navigate, routes } from "../app/navigation";
import { Mascot } from "./Mascot";

export function Brand({ compact = false }: { compact?: boolean }) {
  return (
    <button
      className="brand"
      type="button"
      onClick={() => navigate(routes.landing)}
      aria-label="Перейти на главную VPaNfi"
    >
      <span className="brand-mark" aria-hidden="true">
        <Mascot variant="greeting" decorative />
      </span>
      {!compact && <span>VPaNfi</span>}
    </button>
  );
}
