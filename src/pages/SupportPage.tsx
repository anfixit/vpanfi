import { useState, type FormEvent } from "react";
import { api, ApiRequestError } from "../api/client";
import type { SupportCategory } from "../api/contracts";
import { maxSupportUrl, supportEmail, telegramSupportUrl } from "../config";
import { Icon } from "../components/Icon";
import { Mascot } from "../components/Mascot";

const MESSAGE_ROWS = 7;

const faq = [
  {
    question: "Приложение установлено, но подключения нет",
    answer:
      "Откройте раздел «Подключение», скопируйте ключ заново и вставьте его в приложение. Чаще всего помогает именно это.",
  },
  {
    question: "Сколько устройств можно подключить",
    answer:
      "Три устройства входят в тариф. Дополнительное место можно будет купить отдельно.",
  },
  {
    question: "Что будет с днями при продлении",
    answer: "Оставшиеся дни не сгорают: новый период просто добавляется к текущему.",
  },
];

const MESSAGE_MIN = 10;

export function SupportPage() {
  const [message, setMessage] = useState("");
  const [category, setCategory] = useState<SupportCategory>("connection");
  const [sent, setSent] = useState(false);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [openQuestion, setOpenQuestion] = useState<string | null>(null);

  const tooShort = message.trim().length < MESSAGE_MIN;

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (tooShort || sending) return;

    setSending(true);
    setError(null);

    try {
      await api.createSupportTicket({ category, message: message.trim() });
      setSent(true);
      setMessage("");
    } catch (cause) {
      /*
       * Человек уже потратил силы на описание проблемы — текст остаётся
       * в поле, а рядом появляется адрес, по которому точно ответят.
       */
      setError(
        cause instanceof ApiRequestError
          ? cause.message
          : "Не удалось отправить обращение. Попробуйте ещё раз или напишите на почту.",
      );
    } finally {
      setSending(false);
    }
  };

  return (
    <div className="cabinet-page">
      <section className="page-intro cabinet-card support-intro">
        <div>
          <span className="cabinet-kicker">Отвечаем по-человечески</span>
          <h2>Поддержка</h2>
          <p className="muted">
            Начните с короткого описания проблемы. Анфиса поможет найти решение или передаст
            обращение человеку.
          </p>
        </div>
        <Mascot variant="support" className="page-intro-mascot" decorative />
      </section>

      <section className="support-channel-grid">
        <a
          className="cabinet-card support-channel is-primary"
          href={`mailto:${supportEmail}?subject=${encodeURIComponent(
            "VPaNfi — вопрос по подписке",
          )}`}
        >
          <span className="support-channel-icon">
            <Icon name="mail" />
          </span>
          <div>
            <h3>Почта</h3>
            <p>Работает, даже когда VPN не подключается.</p>
          </div>
          <strong>
            {supportEmail}
            <Icon name="arrow-right" />
          </strong>
        </a>
        <a
          className="cabinet-card support-channel"
          href={maxSupportUrl}
          target="_blank"
          rel="noreferrer"
        >
          <span className="support-channel-icon">
            <Icon name="message" />
          </span>
          <div>
            <h3>MAX</h3>
            <p>Мессенджер, который открывается без VPN.</p>
          </div>
          <strong>
            Написать
            <Icon name="arrow-right" />
          </strong>
        </a>
        <a
          className="cabinet-card support-channel"
          href={telegramSupportUrl}
          target="_blank"
          rel="noreferrer"
        >
          <span className="support-channel-icon">
            <Icon name="telegram" />
          </span>
          <div>
            <h3>Telegram</h3>
            <p>Быстрее всего, но нужен включённый VPN.</p>
          </div>
          <strong>
            Открыть
            <Icon name="arrow-right" />
          </strong>
        </a>
        <article className="cabinet-card support-channel">
          <span className="support-channel-icon">
            <Icon name="sparkle" />
          </span>
          <div>
            <h3>Умный чат</h3>
            <p>Появится после подключения AI-помощника через API.</p>
          </div>
          <span className="coming-soon">Скоро</span>
        </article>
        <article className="cabinet-card support-channel">
          <span className="support-channel-icon">
            <Icon name="question" />
          </span>
          <div>
            <h3>Частые вопросы</h3>
            <p>Короткие инструкции без технических терминов.</p>
          </div>
          <span className="coming-soon">Ниже на странице</span>
        </article>
      </section>

      <section className="cabinet-card support-form-card">
        <div className="support-form-copy">
          <span className="section-kicker">Форма обращения</span>
          <h2>Что случилось?</h2>
          <p className="muted">
            Не присылайте пароль или данные банковской карты. Для диагностики достаточно описания
            устройства и того, что Вы видите на экране.
          </p>
          <Mascot
            variant={sent ? "connected" : "support"}
            className="card-mascot"
            decorative
          />
        </div>
        {sent ? (
          <div className="support-success" role="status">
            <h3>Обращение принято</h3>
            <p>
              Анфиса получила письмо и ответит на {supportEmail}. Поддержка — один человек,
              поэтому ответ может занять несколько часов.
            </p>
            <button
              className="button button-secondary"
              type="button"
              onClick={() => setSent(false)}
            >
              Написать ещё
            </button>
          </div>
        ) : (
          <form className="support-form" onSubmit={submit}>
            <label>
              Тема
              <select
                value={category}
                onChange={(event) =>
                  setCategory(event.target.value as SupportCategory)
                }
              >
                <option value="connection">Не получается подключиться</option>
                <option value="payment">Вопрос по оплате</option>
                <option value="devices">Устройства</option>
                <option value="other">Другое</option>
              </select>
            </label>
            <label>
              Сообщение
              <textarea
                value={message}
                onChange={(event) => setMessage(event.target.value)}
                placeholder="Например: HAPP установлен на Android, но после нажатия кнопки ничего не происходит"
                rows={MESSAGE_ROWS}
              />
            </label>
            {error && (
              <div className="auth-error" role="alert">
                {error} Если не выходит — напишите на{" "}
                <a href={`mailto:${supportEmail}`}>{supportEmail}</a>.
              </div>
            )}
            <button
              className="button button-primary button-large"
              type="submit"
              disabled={tooShort || sending}
            >
              {sending ? "Отправляем…" : "Отправить обращение"}
            </button>
          </form>
        )}
      </section>

      <section className="cabinet-card support-faq">
        <div className="section-heading compact-heading">
          <div>
            <span className="section-kicker">Быстрые ответы</span>
            <h2>Частые вопросы</h2>
          </div>
        </div>
        {faq.map((item) => (
          <button
            className={`faq-row ${openQuestion === item.question ? "is-open" : ""}`.trim()}
            type="button"
            key={item.question}
            aria-expanded={openQuestion === item.question}
            onClick={() =>
              setOpenQuestion((current) => (current === item.question ? null : item.question))
            }
          >
            <span className="faq-question">
              <strong>{item.question}</strong>
              <Icon
                name="chevron-down"
                className={openQuestion === item.question ? "icon-rotated" : ""}
              />
            </span>
            {openQuestion === item.question && <span className="faq-answer">{item.answer}</span>}
          </button>
        ))}
      </section>
    </div>
  );
}
