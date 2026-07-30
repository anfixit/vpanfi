import { useEffect, useState } from "react";
import { ApiRequestError } from "../api/client";
import { navigate, routes } from "../app/navigation";
import { useAuth } from "../auth/AuthContext";
import { Mascot } from "../components/Mascot";

/*
 * Сюда провайдер возвращает человека после согласия. Код обменивается на
 * сеанс один раз: повторный обмен тем же кодом провайдер отклонит, а
 * React в строгом режиме монтирует эффект дважды.
 */

function readProvider(state: string | null): string | null {
  if (!state) return null;

  try {
    const payload = JSON.parse(atob(state.split(".")[1] ?? ""));
    return typeof payload.sub === "string" ? payload.sub : null;
  } catch {
    return null;
  }
}

export function AuthCallbackPage() {
  const { completeOAuth } = useAuth();
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const code = params.get("code");
    const state = params.get("state");
    const provider = readProvider(state);
    const denied = params.get("error");

    if (denied) {
      setError("Вход отменён. Можно попробовать ещё раз или войти по паролю.");
      return;
    }

    if (!code || !state || !provider) {
      setError("Ссылка входа неполная. Начните вход заново.");
      return;
    }

    let cancelled = false;

    completeOAuth(provider, code, state)
      .then(() => {
        if (!cancelled) navigate(routes.dashboard, { replace: true });
      })
      .catch((reason: unknown) => {
        if (cancelled) return;
        setError(
          reason instanceof ApiRequestError
            ? reason.message
            : "Не удалось завершить вход",
        );
      });

    return () => {
      cancelled = true;
    };
  }, [completeOAuth]);

  return (
    <main className="auth-callback shell">
      <Mascot
        variant={error ? "error" : "laptop"}
        className="resource-mascot"
        loading="eager"
        decorative
      />
      {error ? (
        <>
          <h1>Вход не завершился</h1>
          <p className="muted">{error}</p>
          <button
            className="button button-primary button-large"
            type="button"
            onClick={() => navigate(routes.landing)}
          >
            Вернуться на главную
          </button>
        </>
      ) : (
        <>
          <h1>Заходим в кабинет…</h1>
          <p className="muted">Анфиса проверяет ответ и открывает кабинет.</p>
        </>
      )}
    </main>
  );
}
