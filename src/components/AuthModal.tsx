import { useState, type FormEvent } from "react";
import { useAuth } from "../auth/AuthContext";
import { Mascot } from "./Mascot";

export function AuthModal({
  onClose,
  onAuthenticated,
}: {
  onClose: () => void;
  onAuthenticated: () => void;
}) {
  const { login, register } = useAuth();
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

  const showProviderNotice = (provider: string) => {
    setError(`Вход через ${provider} появится после настройки ключей приложения.`);
  };

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
        <Mascot variant={error ? "error" : "greeting"} className="auth-mascot" decorative />
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
        <div className="modal-divider"><span>или</span></div>
        <div className="social-login">
          <button type="button" onClick={() => showProviderNotice("Яндекс")}><span className="ya">Я</span> Яндекс</button>
          <button type="button" onClick={() => showProviderNotice("VK")}><span className="vk">VK</span> VK</button>
          <button type="button" onClick={() => showProviderNotice("Telegram")}><span className="tg">➤</span> Telegram</button>
        </div>
      </section>
    </div>
  );
}
