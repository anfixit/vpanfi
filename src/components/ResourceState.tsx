export function LoadingState({ label = "Анфиса собирает данные…" }: { label?: string }) {
  return (
    <div className="resource-state" role="status">
      <div className="resource-monkey" aria-hidden="true">🐵</div>
      <strong>{label}</strong>
      <span className="resource-dots" aria-hidden="true"><i /><i /><i /></span>
    </div>
  );
}

export function ErrorState({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div className="resource-state resource-error" role="alert">
      <div className="resource-monkey" aria-hidden="true">🙈</div>
      <strong>Кажется, лиана запуталась</strong>
      <p>{message}</p>
      <button className="button button-secondary" type="button" onClick={onRetry}>
        Попробовать ещё раз
      </button>
    </div>
  );
}
