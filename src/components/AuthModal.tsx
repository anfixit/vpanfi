import { useState, type FormEvent } from "react";
import { api } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { useAsyncResource } from "../hooks/useAsyncResource";
import { legalDocuments, legalPath } from "../legal";
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
  /*
   * Третий режим, а не отдельная страница: человек упирается в отказ
   * здесь же, и уводить его со страницы ради одного поля значит терять
   * половину тех, кто и так уже не смог войти.
   */
  const [mode, setMode] = useState<"login" | "register" | "recover">("register");
  const [sentTo, setSentTo] = useState<string | null>(null);
  const [displayName, setDisplayName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [accepted, setAccepted] = useState<Record<string, boolean>>({});
  const [error, setError] = useState<string | null>(null);

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError(null);
    setBusy(true);

    try {
      if (mode === "recover") {
        const sent = await api.requestPasswordReset(email.trim());
        setSentTo(sent.email);
        return;
      }
      if (mode === "register") {
        await register({ displayName: displayName.trim(), email, password });
      } else {
        await login({ email, password });
      }
      onAuthenticated();
    } catch (reason: unknown) {
      setError(
        reason instanceof Error
          ? reason.message
          : mode === "recover"
            ? "Не получилось отправить письмо"
            : "Не удалось войти",
      );
    } finally {
      setBusy(false);
    }
  };

  const switchMode = (nextMode: "login" | "register" | "recover") => {
    setMode(nextMode);
    setError(null);
    setSentTo(null);
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
  const allAccepted = legalDocuments.every((item) => accepted[item.slug]);

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
        <h2 id="auth-title">{mode === "register" ? "Начнём знакомство" : mode === "recover" ? "Восстановим доступ" : "С возвращением"}</h2>
        <p>{mode === "register" ? "Создайте аккаунт и получите семь дней бесплатно." : mode === "recover" ? "Оставьте почту, и мы пришлём ссылку для смены пароля." : "Введите данные своего аккаунта."}</p>
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
          {mode !== "recover" && (
            <label>
              Пароль
              <input type="password" value={password} onChange={(event) => setPassword(event.target.value)} placeholder="Не короче 8 символов" required minLength={mode === "register" ? 8 : 1} maxLength={128} autoComplete={mode === "login" ? "current-password" : "new-password"} />
            </label>
          )}
          {mode === "login" && (
            <button className="auth-link" type="button" onClick={() => switchMode("recover")}>
              Забыли пароль?
            </button>
          )}
          {mode === "recover" && (
            <button className="auth-link" type="button" onClick={() => switchMode("login")}>
              Вспомнили пароль? Войти
            </button>
          )}
          {mode === "register" && (
            /*
             * Отметка ставится напротив каждого документа отдельно.
             * Одна общая галочка на три документа означала бы, что
             * человек согласился с тем, чего мог не открыть, — а
             * платёжный провайдер проверяет именно принятие оферты.
             */
            <fieldset className="auth-consent-group">
              <legend>Перед регистрацией подтвердите согласие</legend>
              {legalDocuments.map((item) => (
                <label className="auth-consent" key={item.slug}>
                  <input
                    type="checkbox"
                    checked={accepted[item.slug] ?? false}
                    onChange={(event) =>
                      setAccepted((current) => ({
                        ...current,
                        [item.slug]: event.target.checked,
                      }))
                    }
                    required
                    /*
                     * Ссылка внутри метки не складывается в имя для
                     * скринридера: без этого галочка читалась как «on».
                     */
                    aria-label={`Я принимаю ${item.titleAccusative}`}
                  />
                  <span>
                    Я принимаю{" "}
                    <a
                      href={legalPath(item.slug)}
                      target="_blank"
                      rel="noreferrer noopener"
                    >
                      {item.titleAccusative}
                    </a>
                  </span>
                </label>
              ))}
            </fieldset>
          )}
          {error && <div className="auth-error" role="alert">{error}</div>}
          {sentTo && (
            <div className="auth-sent" role="status">
              Письмо ушло на <strong>{sentTo}</strong>. Откройте ссылку из него
              и придумайте новый пароль. Если письма нет, посмотрите в спаме.
            </div>
          )}
          <button
            className="button button-primary full-button"
            type="submit"
            disabled={busy || (mode === "register" && !allAccepted)}
          >
            {busy
              ? "Подождите…"
              : mode === "register"
                ? "Получить 7 дней бесплатно"
                : mode === "recover"
                  ? sentTo
                    ? "Прислать ещё раз"
                    : "Прислать ссылку"
                  : "Войти"}
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
