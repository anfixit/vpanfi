import { useState } from "react";
import { Mascot } from "./Mascot";

export function AuthModal({ onClose, onContinue }: { onClose: () => void; onContinue: () => void }) {
  const [mode, setMode] = useState<"login" | "register">("register");

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
        <Mascot variant="greeting" className="auth-mascot" decorative />
        <span className="section-kicker">Анфиса уже приготовила всё нужное</span>
        <h2 id="auth-title">{mode === "register" ? "Начнём знакомство" : "С возвращением"}</h2>
        <p>Пока работает демонстрационный вход. Настоящая авторизация появится вместе с backend.</p>
        <div className="modal-tabs">
          <button className={mode === "register" ? "is-active" : ""} type="button" onClick={() => setMode("register")}>Регистрация</button>
          <button className={mode === "login" ? "is-active" : ""} type="button" onClick={() => setMode("login")}>Вход</button>
        </div>
        <label>Email<input type="email" placeholder="you@example.com" autoComplete="email" /></label>
        <label>Пароль<input type="password" placeholder="Не короче 8 символов" autoComplete={mode === "login" ? "current-password" : "new-password"} /></label>
        <button className="button button-primary full-button" type="button" onClick={onContinue}>
          {mode === "register" ? "Получить 7 дней бесплатно" : "Войти"}
        </button>
        <div className="modal-divider"><span>или</span></div>
        <div className="social-login">
          <button type="button"><span className="ya">Я</span> Яндекс</button>
          <button type="button"><span className="vk">VK</span> VK</button>
          <button type="button"><span className="tg">➤</span> Telegram</button>
        </div>
      </section>
    </div>
  );
}
