import { useState } from "react";
import { api } from "../api/client";
import { useDemoNotice } from "../components/DemoNotice";
import { Mascot } from "../components/Mascot";
import { EmptyState, ErrorState, LoadingState } from "../components/ResourceState";
import { EXTRA_DEVICE_PRICE_RUB, tariffs } from "../data";
import { useAsyncResource } from "../hooks/useAsyncResource";
import { formatRubles } from "../utils/format";

const DEFAULT_TARIFF = "3 месяца";

const paymentStatusLabels: Record<string, string> = {
  succeeded: "Оплачено",
  pending: "В обработке",
  failed: "Не прошёл",
  refunded: "Возврат",
  cancelled: "Отменён",
};

export function PaymentsPage() {
  const payments = useAsyncResource(api.getPayments);
  const { isDemoMode, explain } = useDemoNotice();
  const [selectedTariff, setSelectedTariff] = useState(DEFAULT_TARIFF);
  const [autoRenew, setAutoRenew] = useState(true);
  const [demoReceiptShown, setDemoReceiptShown] = useState(false);

  const startPayment = () => {
    if (!isDemoMode) {
      /*
       * Оплата подключена, но продление и покупка — разные вещи. Покупка
       * заводит нового человека, а продление обязано попасть в уже
       * существующего. Сопоставить их можно только по почте, а у тех, кто
       * пришёл из Telegram, её в базе бота нет: продление через покупку
       * создало бы им второй аккаунт и вторую подписку вместо продления.
       * Поэтому до связки аккаунтов продлевать отправляем в бота.
       */
      explain(
        "Продление пока проходит в боте — там подписка продлится, а не заведётся заново.",
      );
      return;
    }
    setDemoReceiptShown(true);
  };

  if (payments.loading && !payments.data) {
    return <LoadingState label="Анфиса проверяет платежи…" />;
  }
  if (payments.error || !payments.data) {
    return (
      <ErrorState
        message={payments.error ?? "История платежей не найдена"}
        onRetry={payments.reload}
      />
    );
  }

  return (
    <div className="cabinet-page">
      <section className="page-intro cabinet-card">
        <div>
          <span className="cabinet-kicker">Оплата через СБП</span>
          <h2>Продление и платежи</h2>
          <p className="muted">
            Оплатите новый период заранее. Оставшиеся дни никуда не пропадут и просто суммируются.
          </p>
        </div>
        <Mascot variant="payment-success" className="page-intro-mascot" decorative />
      </section>

      {demoReceiptShown ? (
        <section className="cabinet-card payment-result" role="status">
          <Mascot variant="payment-success" className="card-mascot" decorative />
          <span className="demo-badge">Демонстрация</span>
          <h2>Так выглядит успешная оплата</h2>
          <p className="muted">
            Это предпросмотр экрана. Деньги не списывались и платёж не создавался: провайдер СБП
            ещё не подключён.
          </p>
          <button
            className="button button-secondary"
            type="button"
            onClick={() => setDemoReceiptShown(false)}
          >
            Вернуться к тарифам
          </button>
        </section>
      ) : (
        <section className="cabinet-card payment-plans">
          <div className="section-heading compact-heading">
            <div>
              <span className="section-kicker">Выберите период</span>
              <h2>Продлить подписку</h2>
            </div>
          </div>
          <div className="tariff-grid" role="group" aria-label="Тарифные периоды">
            {tariffs.map((tariff) => (
              <button
                className={`tariff ${tariff.popular ? "is-popular" : ""} ${
                  selectedTariff === tariff.period ? "is-selected" : ""
                }`}
                type="button"
                key={tariff.period}
                aria-pressed={selectedTariff === tariff.period}
                onClick={() => setSelectedTariff(tariff.period)}
              >
                {tariff.popular && <span className="popular-label">выгодно</span>}
                <span>{tariff.period}</span>
                <strong>{tariff.price}</strong>
                {tariff.saving && <small>{tariff.saving}</small>}
              </button>
            ))}
          </div>
          <div className="payment-checkout">
            <div>
              <small>Вы выбрали</small>
              <strong>{selectedTariff}</strong>
              <span>3 устройства · без лимита трафика</span>
            </div>
            <button
              className="button button-primary button-large"
              type="button"
              onClick={startPayment}
            >
              {isDemoMode ? "Показать демо-оплату" : "Оплатить через СБП"}
            </button>
          </div>
          {isDemoMode && (
            <p className="muted payment-demo-note">
              В демо-режиме оплата не выполняется — кнопка показывает, как выглядит экран после
              успешного платежа.
            </p>
          )}
        </section>
      )}

      <section className="cabinet-grid cabinet-grid-bottom">
        <article className="cabinet-card renewal-settings">
          <header>
            <h3>Автопродление</h3>
          </header>
          <p className="muted">
            Если на балансе достаточно средств, новый месяц включится автоматически.
          </p>
          <label className="toggle-row">
            <span>
              <strong>Автопродление</strong>
              <small>{autoRenew ? "Включено" : "Выключено"}</small>
            </span>
            <input
              type="checkbox"
              checked={autoRenew}
              onChange={(event) => setAutoRenew(event.target.checked)}
            />
          </label>
          <div className="balance-row">
            <span>Баланс</span>
            <strong>{formatRubles(0)}</strong>
          </div>
          <button
            className="button button-secondary full-button"
            type="button"
            onClick={() => explain("Пополнение баланса откроется вместе с платёжным провайдером.")}
          >
            Пополнить баланс
          </button>
        </article>

        <article className="cabinet-card payment-device-addon">
          <header>
            <h3>Дополнительное устройство</h3>
          </header>
          <Mascot variant="subscription-active" className="card-mascot-small" decorative />
          <strong className="big-stat">{formatRubles(EXTRA_DEVICE_PRICE_RUB)}</strong>
          <p className="muted">Одно дополнительное место на весь срок действующей подписки.</p>
          <button
            className="button button-secondary full-button"
            type="button"
            onClick={() =>
              explain("Покупка дополнительного места появится вместе с платёжным провайдером.")
            }
          >
            Добавить устройство
          </button>
        </article>
      </section>

      <section className="cabinet-card payment-history-full">
        <div className="section-heading compact-heading">
          <div>
            <span className="section-kicker">Все операции</span>
            <h2>История платежей</h2>
          </div>
        </div>
        {payments.data.length > 0 ? (
          <div className="payment-table">
            {payments.data.map((payment) => (
              <div className="payment-table-row" key={payment.id}>
                <div>
                  <strong>{payment.description}</strong>
                  <small>{payment.createdAt}</small>
                </div>
                <span className={`payment-status is-${payment.status}`}>
                  {paymentStatusLabels[payment.status] ?? payment.status}
                </span>
                <b>{formatRubles(payment.amountRub)}</b>
              </div>
            ))}
          </div>
        ) : (
          <EmptyState
            mascot="subscription-active"
            title="Платежей ещё не было"
            description="Как только Вы оплатите период, операции появятся здесь."
          />
        )}
      </section>
    </div>
  );
}
