import { useState, type FormEvent } from "react";
import { ApiRequestError, api } from "../api/client";
import { navigate, routes } from "../app/navigation";
import { Mascot } from "../components/Mascot";

/*
 * Сюда человек попадает по ссылке из письма. Токен лежит в адресе, и
 * это единственное, что подтверждает право сменить пароль: доступа к
 * почте достаточно, входить в кабинет для этого не нужно.
 *
 * После смены не пускаем в кабинет молча, а отправляем войти заново.
 * Так человек сразу убеждается, что новый пароль работает, а не узнаёт
 * об этом при следующем заходе через неделю.
 */

export function PasswordResetPage() {
  const token = new URLSearchParams(window.location.search).get("token");
  const [password, setPassword] = useState("");
  const [repeat, setRepeat] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!token) return;

    if (password !== repeat) {
      setError("Пароли не совпадают. Проверьте оба поля.");
      return;
    }

    setError(null);
    setBusy(true);

    try {
      await api.confirmPasswordReset(token, password);
      setDone(true);
    } catch (reason: unknown) {
      setError(
        reason instanceof ApiRequestError
          ? reason.message
          : "Не получилось сменить пароль. Попробуйте ещё раз.",
      );
    } finally {
      setBusy(false);
    }
  };

  if (!token) {
    return (
      <main className="auth-callback shell">
        <Mascot
          variant="error"
          className="resource-mascot"
          loading="eager"
          decorative
        />
        <h1>Ссылка неполная</h1>
        <p className="muted">
          Похоже, адрес скопировался не целиком. Откройте ссылку из письма
          ещё раз или запросите новую.
        </p>
        <button
          className="button button-primary button-large"
          type="button"
          onClick={() => navigate(routes.landing)}
        >
          На главную
        </button>
      </main>
    );
  }

  if (done) {
    return (
      <main className="auth-callback shell">
        <Mascot
          variant="connected"
          className="resource-mascot"
          loading="eager"
          decorative
        />
        <h1>Пароль сменили</h1>
        <p className="muted">
          Войдите с новым паролем. Все прежние входы мы закрыли: если
          доступ был у кого-то ещё, теперь его нет.
        </p>
        <button
          className="button button-primary button-large"
          type="button"
          onClick={() => navigate(routes.landing)}
        >
          Войти
        </button>
      </main>
    );
  }

  return (
    <main className="auth-callback shell">
      <Mascot
        variant={error ? "error" : "laptop"}
        className="resource-mascot"
        loading="eager"
        decorative
      />
      <h1>Новый пароль</h1>
      <p className="muted">
        Придумайте пароль не короче восьми символов. Старый перестанет
        работать сразу.
      </p>
      <form className="auth-form password-reset-form" onSubmit={submit}>
        <label>
          Новый пароль
          <input
            type="password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            required
            minLength={8}
            maxLength={128}
            autoComplete="new-password"
            placeholder="Не короче 8 символов"
          />
        </label>
        <label>
          Ещё раз
          <input
            type="password"
            value={repeat}
            onChange={(event) => setRepeat(event.target.value)}
            required
            minLength={8}
            maxLength={128}
            autoComplete="new-password"
            placeholder="Тот же пароль"
          />
        </label>
        {error && (
          <div className="auth-error" role="alert">
            {error}
          </div>
        )}
        <button
          className="button button-primary full-button"
          type="submit"
          disabled={busy}
        >
          {busy ? "Меняем…" : "Сменить пароль"}
        </button>
      </form>
    </main>
  );
}
