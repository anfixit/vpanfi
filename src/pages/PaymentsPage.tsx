import { useState } from "react";
import { api } from "../api/client";
import { Mascot } from "../components/Mascot";
import { ErrorState, LoadingState } from "../components/ResourceState";
import { tariffs } from "../data";
import { useAsyncResource } from "../hooks/useAsyncResource";
import { formatRubles } from "../utils/format";

export function PaymentsPage() {
  const payments = useAsyncResource(api.getPayments);
  const [selectedTariff, setSelectedTariff] = useState("3 месяца");
  const [autoRenew, setAutoRenew] = useState(true);

  if (payments.loading && !payments.data) return <LoadingState label="Анфиса проверяет платежи…" />;
  if (payments.error || !payments.data) return <ErrorState message={payments.error ?? "История платежей не найдена"} onRetry={payments.reload} />;

  return (
    <div className="cabinet-page">
      <section className="page-intro cabinet-card">
        <div>
          <span className="cabinet-kicker">Оплата через СБП</span>
          <h2>Продление и платежи</h2>
          <p className="muted">Оплатите новый период заранее. Оставшиеся дни никуда не пропадут и просто суммируются.</p>
        </div>
        <Mascot variant="payment" className="page-intro-mascot" decorative />
      </section>

      <section className="cabinet-card payment-plans">
        <div className="section-heading compact-heading"><div><span className="section-kicker">Выберите период</span><h2>Продлить подписку</h2></div></div>
        <div className="tariff-grid">
          {tariffs.map((tariff) => (
            <button
              className={`tariff ${tariff.popular ? "is-popular" : ""} ${selectedTariff === tariff.period ? "is-selected" : ""}`}
              type="button"
              key={tariff.period}
              onClick={() => setSelectedTariff(tariff.period)}
            >
              {tariff.popular && <span className="popular-label">выгодно</span>}
              <span>{tariff.period}</span><strong>{tariff.price}</strong>{tariff.saving && <small>{tariff.saving}</small>}
            </button>
          ))}
        </div>
        <div className="payment-checkout">
          <div><small>Вы выбрали</small><strong>{selectedTariff}</strong><span>3 устройства · без лимита трафика</span></div>
          <button className="button button-primary button-large" type="button">Оплатить через СБП</button>
        </div>
      </section>

      <section className="cabinet-grid cabinet-grid-bottom">
        <article className="cabinet-card renewal-settings">
          <header><span aria-hidden="true">↻</span><h3>Автопродление</h3></header>
          <p className="muted">Если на балансе достаточно средств, новый месяц включится автоматически.</p>
          <label className="toggle-row"><span><strong>Автопродление</strong><small>{autoRenew ? "Включено" : "Выключено"}</small></span><input type="checkbox" checked={autoRenew} onChange={(event) => setAutoRenew(event.target.checked)} /></label>
          <div className="balance-row"><span>Баланс</span><strong>0 ₽</strong></div>
          <button className="button button-secondary full-button" type="button">Пополнить баланс</button>
        </article>

        <article className="cabinet-card payment-device-addon">
          <header><span aria-hidden="true">＋</span><h3>Дополнительное устройство</h3></header>
          <Mascot variant="subscription" className="card-mascot-small" decorative />
          <strong className="big-stat">100 ₽</strong>
          <p className="muted">Одно дополнительное место на весь срок действующей подписки.</p>
          <button className="button button-secondary full-button" type="button">Добавить устройство</button>
        </article>
      </section>

      <section className="cabinet-card payment-history-full">
        <div className="section-heading compact-heading"><div><span className="section-kicker">Все операции</span><h2>История платежей</h2></div></div>
        <div className="payment-table">
          {payments.data.map((payment) => (
            <div className="payment-table-row" key={payment.id}>
              <div><strong>{payment.description}</strong><small>{payment.createdAt}</small></div>
              <span className={`payment-status is-${payment.status}`}>{payment.status === "succeeded" ? "Оплачено" : payment.status}</span>
              <b>{formatRubles(payment.amountRub)}</b>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
