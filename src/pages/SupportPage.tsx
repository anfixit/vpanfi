import { useState, type FormEvent } from "react";
import { Mascot } from "../components/Mascot";

const telegramUrl = import.meta.env.VITE_TELEGRAM_SUPPORT_URL ?? "https://t.me/VPaNfi_bot";

export function SupportPage() {
  const [message, setMessage] = useState("");
  const [sent, setSent] = useState(false);

  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!message.trim()) return;
    setSent(true);
    setMessage("");
  };

  return (
    <div className="cabinet-page">
      <section className="page-intro cabinet-card support-intro">
        <div>
          <span className="cabinet-kicker">Отвечаем по-человечески</span>
          <h2>Поддержка</h2>
          <p className="muted">Начните с короткого описания проблемы. Анфиса поможет найти решение или передаст обращение человеку.</p>
        </div>
        <Mascot variant="support" className="page-intro-mascot" decorative />
      </section>

      <section className="support-channel-grid">
        <a className="cabinet-card support-channel is-primary" href={telegramUrl} target="_blank" rel="noreferrer">
          <span className="support-channel-icon" aria-hidden="true">➤</span>
          <div><h3>Telegram</h3><p>Самый быстрый способ связаться с поддержкой.</p></div>
          <strong>Открыть →</strong>
        </a>
        <article className="cabinet-card support-channel">
          <span className="support-channel-icon" aria-hidden="true">✦</span>
          <div><h3>Умный чат</h3><p>Появится после подключения AI-помощника через API.</p></div>
          <span className="coming-soon">Скоро</span>
        </article>
        <article className="cabinet-card support-channel">
          <span className="support-channel-icon" aria-hidden="true">?</span>
          <div><h3>Частые вопросы</h3><p>Короткие инструкции без технических терминов.</p></div>
          <button className="text-action" type="button">Посмотреть</button>
        </article>
      </section>

      <section className="cabinet-card support-form-card">
        <div className="support-form-copy">
          <span className="section-kicker">Форма обращения</span>
          <h2>Что случилось?</h2>
          <p className="muted">Не присылайте пароль или данные банковской карты. Для диагностики достаточно описания устройства и того, что Вы видите на экране.</p>
          <Mascot variant={sent ? "success" : "support"} className="card-mascot" decorative />
        </div>
        {sent ? (
          <div className="support-success"><h3>Обращение принято</h3><p>В демонстрационном режиме оно не отправляется на сервер, но интерфейс уже готов к подключению backend.</p><button className="button button-secondary" type="button" onClick={() => setSent(false)}>Написать ещё</button></div>
        ) : (
          <form className="support-form" onSubmit={submit}>
            <label>Тема<select defaultValue="connection"><option value="connection">Не получается подключиться</option><option value="payment">Вопрос по оплате</option><option value="devices">Устройства</option><option value="other">Другое</option></select></label>
            <label>Сообщение<textarea value={message} onChange={(event) => setMessage(event.target.value)} placeholder="Например: HAPP установлен на Android, но после нажатия кнопки ничего не происходит" rows={7} /></label>
            <button className="button button-primary button-large" type="submit" disabled={!message.trim()}>Отправить обращение</button>
          </form>
        )}
      </section>
    </div>
  );
}
