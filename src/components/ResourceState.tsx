import { Mascot } from "./Mascot";

export function LoadingState({ label = "Анфиса собирает данные…" }: { label?: string }) {
  return (
    <div className="resource-state" role="status">
      <Mascot variant="checking" className="resource-mascot" decorative />
      <strong>{label}</strong>
      <span className="resource-dots" aria-hidden="true"><i /><i /><i /></span>
    </div>
  );
}

export function ErrorState({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div className="resource-state resource-error" role="alert">
      <Mascot variant="error" className="resource-mascot" decorative />
      <strong>Кажется, лиана запуталась</strong>
      <p>{message}</p>
      <button className="button button-secondary" type="button" onClick={onRetry}>
        Попробовать ещё раз
      </button>
    </div>
  );
}
