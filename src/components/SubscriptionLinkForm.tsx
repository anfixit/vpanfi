import { useState, type FormEvent } from "react";
import { api, ApiRequestError } from "../api/client";
import type { SubscriptionLink } from "../api/contracts";
import { Mascot } from "./Mascot";

const FALLBACK_ERROR = "Не получилось привязать подписку. Попробуйте ещё раз.";
const TELEGRAM_URL =
  import.meta.env.VITE_TELEGRAM_SUPPORT_URL ?? "https://t.me/VPaNfi_bot";

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
        <span className="cabinet-kicker">Один шаг до кабинета</span>
        <h2>Если у Вас уже есть подписка</h2>
        <p className="muted">
          Вставьте ссылку на неё — ту самую, которую прислал бот. Анфиса
          найдёт подписку и покажет здесь срок, устройства и всё остальное.
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

      <div className="subscription-link-alternative">
        <strong>А если подписки ещё нет?</strong>
        <p className="muted">
          Её оформляет бот — он же пришлёт ссылку, которую нужно вставить
          сюда. Это займёт пару минут.
        </p>
        <a
          className="button button-secondary"
          href={TELEGRAM_URL}
          target="_blank"
          rel="noreferrer"
        >
          Открыть бота
        </a>
      </div>
    </section>
  );
}
