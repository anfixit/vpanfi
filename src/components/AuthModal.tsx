import { useState, type FormEvent } from "react";
import { api } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { useAsyncResource } from "../hooks/useAsyncResource";
import { Icon } from "./Icon";
import { Mascot } from "./Mascot";
import { TelegramLoginButton } from "./TelegramLoginButton";

const PROVIDER_MARKS: Record<string, string> = {
  telegram: "tg",
  vk: "vk",
  yandex: "ya",
};

export function AuthModal({
  onClose,
  onAuthenticated,
}: {
  onClose: () => void;
  onAuthenticated: () => void;
}) {
  const { login, register, signInWithTelegram } = useAuth();
  // Показываем только настроенные способы: кнопка, которая заведомо не
  // работает, хуже её отсутствия.
  const providers = useAsyncResource(api.getAuthProviders);
  const [mode, setMode] = useState<"login" | "register">("register");
  const [displayName, setDisplayName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError(null);
    setBusy(true);

    try {
      if (mode === "register") {
        await register({ displayName: displayName.trim(), email, password });
      } else {
        await login({ email, password });
      }
      onAuthenticated();
    } catch (reason: unknown) {
      setError(reason instanceof Error ? reason.message : "Не удалось войти");
    } finally {
      setBusy(false);
    }
  };

  const switchMode = (nextMode: "login" | "register") => {
    setMode(nextMode);
    setError(null);
  };

  const signInWithProvider = (url: string) => {
    // Провайдер вернёт человека на /auth/callback с кодом и state.
    window.location.assign(url);
  };

  const telegramAuth = async (payload: Record<string, unknown>) => {
    setError(null);
    setBusy(true);
    try {
      await signInWithTelegram(payload);
      onAuthenticated();
    } catch (reason: unknown) {
      setError(
        reason instanceof Error ? reason.message : "Не удалось войти через Telegram",
      );
    } finally {
      setBusy(false);
    }
  };

  const available = providers.data ?? [];

  return (
    <div className="modal-backdrop" role="presentation" onMouseDown={onClose}>
      <section
        className="auth-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="auth-title"
        onMouseDown={(event) => event.stopPropagation()}
      >
        <button className="modal-close" type="button" onClick={onClose} aria-label="Закрыть">×</button>
        <Mascot
          variant={error ? "error" : "greeting"}
          className="auth-mascot"
          loading="eager"
          decorative
        />
        <span className="section-kicker">Анфиса уже приготовила всё нужное</span>
        <h2 id="auth-title">{mode === "register" ? "Начнём знакомство" : "С возвращением"}</h2>
        <p>{mode === "register" ? "Создайте аккаунт и получите семь дней бесплатно." : "Введите данные своего аккаунта."}</p>
        <div className="modal-tabs">
          <button className={mode === "register" ? "is-active" : ""} type="button" onClick={() => switchMode("register")}>Регистрация</button>
          <button className={mode === "login" ? "is-active" : ""} type="button" onClick={() => switchMode("login")}>Вход</button>
        </div>
        <form className="auth-form" onSubmit={submit}>
          {mode === "register" && (
            <label>
              Как Вас зовут
              <input value={displayName} onChange={(event) => setDisplayName(event.target.value)} required minLength={1} maxLength={80} autoComplete="name" />
            </label>
          )}
          <label>
            Email
            <input type="email" value={email} onChange={(event) => setEmail(event.target.value)} placeholder="you@example.com" required autoComplete="email" />
          </label>
          <label>
            Пароль
            <input type="password" value={password} onChange={(event) => setPassword(event.target.value)} placeholder="Не короче 8 символов" required minLength={mode === "register" ? 8 : 1} maxLength={128} autoComplete={mode === "login" ? "current-password" : "new-password"} />
          </label>
          {error && <div className="auth-error" role="alert">{error}</div>}
          <button className="button button-primary full-button" type="submit" disabled={busy}>
            {busy ? "Подождите…" : mode === "register" ? "Получить 7 дней бесплатно" : "Войти"}
          </button>
        </form>
        {available.length > 0 && (
          <>
            <div className="modal-divider">
              <span>или войдите через</span>
            </div>
            <div className="social-login">
              {available.map((provider) =>
                provider.provider === "telegram" && provider.botUsername ? (
                  <TelegramLoginButton
                    key={provider.provider}
                    botUsername={provider.botUsername}
                    onAuth={telegramAuth}
                  />
                ) : (
                  provider.authorizationUrl && (
                    <button
                      key={provider.provider}
                      type="button"
                      disabled={busy}
                      onClick={() => signInWithProvider(provider.authorizationUrl!)}
                    >
                      <span
                        className={PROVIDER_MARKS[provider.provider]}
                        aria-hidden="true"
                      >
                        {provider.provider === "telegram" ? (
                          <Icon name="telegram" />
                        ) : provider.provider === "vk" ? (
                          "VK"
                        ) : (
                          "Я"
                        )}
                      </span>{" "}
                      {provider.name}
                    </button>
                  )
                ),
              )}
            </div>
          </>
        )}
      </section>
    </div>
  );
}
