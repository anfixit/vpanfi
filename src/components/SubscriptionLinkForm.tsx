import { useState, type FormEvent } from "react";
import { api, ApiRequestError } from "../api/client";
import type { SubscriptionLink } from "../api/contracts";
import { Mascot } from "./Mascot";

const FALLBACK_ERROR = "Не получилось привязать подписку. Попробуйте ещё раз.";

export function SubscriptionLinkForm({
  onLinked,
}: {
  onLinked: (result: SubscriptionLink) => void;
}) {
  const [value, setValue] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!value.trim() || busy) return;

    setBusy(true);
    setError(null);

    try {
      onLinked(await api.linkSubscription(value.trim()));
      setValue("");
    } catch (reason: unknown) {
      // Сервер уже прислал понятную человеку причину: опечатка в ссылке,
      // чужая подписка и недоступная панель различаются по коду.
      setError(
        reason instanceof ApiRequestError ? reason.message : FALLBACK_ERROR,
      );
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="cabinet-card subscription-link-card">
      <Mascot variant="qr" className="card-mascot" decorative />
      <div className="subscription-link-copy">
        <span className="cabinet-kicker">Подписка уже есть?</span>
        <h2>Перенесите её в кабинет</h2>
        <p className="muted">
          Вставьте ссылку, которую прислал бот, — срок, устройства и
          остальные данные подтянутся сюда сами.
        </p>
      </div>

      <form className="subscription-link-form" onSubmit={submit}>
        <label>
          Ссылка на подписку
          <input
            value={value}
            onChange={(event) => setValue(event.target.value)}
            placeholder="https://…/sub/…"
            autoComplete="off"
            spellCheck={false}
            inputMode="url"
            required
            maxLength={500}
            aria-describedby="subscription-link-hint"
          />
        </label>
        <p className="muted" id="subscription-link-hint">
          Подойдёт и вся ссылка целиком, и только её последняя часть.
        </p>
        {error && (
          <div className="auth-error" role="alert">
            {error}
          </div>
        )}
        <button
          className="button button-primary button-large full-button"
          type="submit"
          disabled={busy || !value.trim()}
        >
          {busy ? "Ищем подписку…" : "Привязать подписку"}
        </button>
      </form>

    </section>
  );
}
