import { useEffect, useMemo, useState } from "react";
import { api } from "../api/client";
import { shop, ShopRequestError } from "../api/shop";
import type { CheckoutQuote, ShopTariff } from "../api/contracts";
import { useAuth } from "../auth/AuthContext";
import { useDemoNotice } from "../components/DemoNotice";
import { Mascot } from "../components/Mascot";
import { EmptyState, ErrorState, LoadingState } from "../components/ResourceState";
import { EXTRA_DEVICE_PRICE_RUB } from "../data";
import { useAsyncResource } from "../hooks/useAsyncResource";
import { formatRubles, pluralizeRu } from "../utils/format";

const paymentStatusLabels: Record<string, string> = {
  succeeded: "Оплачено",
  pending: "В обработке",
  failed: "Не прошёл",
  refunded: "Возврат",
  cancelled: "Отменён",
};

const CHECKOUT_ERROR = "Не получилось создать платёж. Попробуйте ещё раз.";

const KOPECKS_IN_RUBLE = 100;

function devices(count: number): string {
  return `${count} ${pluralizeRu(count, "устройство", "устройства", "устройств")}`;
}

/*
 * Один выбор человека: тариф и срок вместе. В витрине «30 дней»,
 * «90 дней» и «180 дней» — это три отдельных тарифа с одним периодом
 * каждый, поэтому раскладываем их в плоский список вариантов.
 */
type PeriodOption = {
  key: string;
  tariffId: number;
  periodDays: number;
  name: string;
  priceLabel: string;
  deviceLimit: number;
  trafficLimitGb: number;
};

function toOptions(tariffs: ShopTariff[]): PeriodOption[] {
  return tariffs.flatMap((tariff) =>
    tariff.periods.map((period) => ({
      key: `${tariff.id}:${period.days}`,
      tariffId: tariff.id,
      periodDays: period.days,
      name: tariff.name,
      priceLabel: period.priceLabel,
      deviceLimit: tariff.deviceLimit,
      trafficLimitGb: tariff.trafficLimitGb,
    })),
  );
}

function describeOption(option: PeriodOption): string {
  const traffic =
    option.trafficLimitGb === 0
      ? "без лимита трафика"
      : `${option.trafficLimitGb} ГБ трафика`;
  return `${devices(option.deviceLimit)} · ${traffic}`;
}

export function PaymentsPage() {
  const payments = useAsyncResource(api.getPayments);
  const config = useAsyncResource(shop.getConfig);
  const methods = useAsyncResource(shop.getPaymentMethods);
  const { profile } = useAuth();
  const { isDemoMode } = useDemoNotice();

  const [selectedKey, setSelectedKey] = useState<string | null>(null);
  const [selectedMethod, setSelectedMethod] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [demoReceiptShown, setDemoReceiptShown] = useState(false);
  /*
   * Смету считает сервер: витрина продаёт базовый тариф на три места, а
   * у человека, купившего места в боте, их может быть пять — и доплата
   * за них входит в сумму. Считать её второй раз здесь значило бы
   * показать на странице одно, а списать другое.
   */
  const [quote, setQuote] = useState<CheckoutQuote | null>(null);

  const options = useMemo(
    () => toOptions(config.data?.tariffs ?? []),
    [config.data],
  );
  const selected =
    options.find((option) => option.key === selectedKey) ?? options[0] ?? null;
  const paymentMethods = methods.data ?? [];
  /* Цена витрины — пока сметы нет: своей суммы страница не выдумывает. */
  const priceLabel = quote
    ? formatRubles(quote.amountKopecks / KOPECKS_IN_RUBLE)
    : (selected?.priceLabel ?? "");

  /* Первый вариант выбран заранее: продление в один шаг, без лишних решений. */
  useEffect(() => {
    if (selectedKey === null && options.length > 0) {
      setSelectedKey(options[0].key);
    }
  }, [selectedKey, options]);

  useEffect(() => {
    if (selectedMethod === null && paymentMethods.length > 0) {
      setSelectedMethod(paymentMethods[0].code);
    }
  }, [selectedMethod, paymentMethods]);

  /*
   * В демо-режиме сметы не спрашиваем: показывать там выдуманную сумму к
   * оплате хуже, чем оставить цену витрины. Ответ опоздавшего запроса
   * отбрасываем — иначе быстрый перебор тарифов оставил бы на экране
   * сумму от предыдущего.
   */
  useEffect(() => {
    if (isDemoMode || !selected) {
      setQuote(null);
      return;
    }

    let actual = true;
    setQuote(null);
    api
      .getCheckoutQuote({
        tariffId: selected.tariffId,
        periodDays: selected.periodDays,
      })
      .then((answer) => {
        if (actual) setQuote(answer);
      })
      .catch(() => {
        if (actual) setQuote(null);
      });

    return () => {
      actual = false;
    };
  }, [isDemoMode, selected]);

  /*
   * Продление идёт той же кассой и той же ручкой, что и покупка с витрины.
   * Второй подписки это не создаёт: сервер сначала ищет учётку панели,
   * привязанную к кабинету этой почты, и продлевает её от даты окончания —
   * остаток оплаченного срока не теряется. Учётки нет вовсе только у того,
   * кто на сайте не заводился, а в кабинете такого быть не может.
   *
   * Раньше здесь стояла заметка «продление пока проходит в боте»: связать
   * подписку из бота с кабинетом было нечем, и продление через покупку
   * завело бы человеку вторую учётку. С появлением привязки по ссылке
   * («Профиль» → «Подписка из бота») причина ушла, а заметка осталась и
   * отправляла платящих людей в бота с рабочей страницы оплаты.
   */
  const startPayment = async () => {
    if (isDemoMode) {
      setDemoReceiptShown(true);
      return;
    }
    if (busy || !selected || !profile) return;

    setBusy(true);
    setError(null);

    try {
      const purchase = await shop.createPurchase({
        tariffId: selected.tariffId,
        periodDays: selected.periodDays,
        email: profile.email,
        paymentMethod: selectedMethod,
      });

      if (purchase.paymentUrl) {
        window.location.href = purchase.paymentUrl;
        return;
      }

      /* Платёж создан, а ссылки нет — платить негде, молчать об этом нельзя. */
      setError(CHECKOUT_ERROR);
    } catch (reason: unknown) {
      setError(reason instanceof ShopRequestError ? reason.message : CHECKOUT_ERROR);
    } finally {
      setBusy(false);
    }
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
            Это предпросмотр экрана. Деньги не списывались и платёж не создавался: сайт открыт
            в демо-режиме.
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

          {config.loading && !config.data ? (
            <LoadingState label="Анфиса уточняет цены…" />
          ) : options.length === 0 ? (
            <ErrorState
              message={config.error ?? "Тарифы сейчас недоступны"}
              onRetry={config.reload}
            />
          ) : (
            <>
              <div className="tariff-grid" role="group" aria-label="Тарифные периоды">
                {options.map((option) => (
                  <button
                    className={`tariff ${selected?.key === option.key ? "is-selected" : ""}`}
                    type="button"
                    key={option.key}
                    aria-pressed={selected?.key === option.key}
                    onClick={() => setSelectedKey(option.key)}
                  >
                    <span>{option.name}</span>
                    <strong>{option.priceLabel}</strong>
                  </button>
                ))}
              </div>

              {quote && quote.extraDevices > 0 && quote.devicesLimit !== null && (
                <p className="payment-device-limit-note" role="status">
                  В Вашей подписке {devices(quote.devicesLimit)}, а в базовый тариф входит{" "}
                  {devices(quote.tariffDevices ?? 0)}. Доплата за остальные —{" "}
                  {formatRubles(
                    (quote.amountKopecks - quote.baseKopecks) / KOPECKS_IN_RUBLE,
                  )}{" "}
                  за выбранный период, она уже включена в сумму к оплате. Места остаются Вашими,
                  менять ничего не нужно.
                </p>
              )}

              {paymentMethods.length > 1 && (
                <div
                  className="tariff-grid payment-method-grid"
                  role="group"
                  aria-label="Способ оплаты"
                >
                  {paymentMethods.map((method) => (
                    <button
                      className={`tariff ${selectedMethod === method.code ? "is-selected" : ""}`}
                      type="button"
                      key={method.code}
                      aria-pressed={selectedMethod === method.code}
                      onClick={() => setSelectedMethod(method.code)}
                    >
                      <span>{method.name}</span>
                      <small>{method.description}</small>
                    </button>
                  ))}
                </div>
              )}

              <div className="payment-checkout">
                <div>
                  <small>Вы выбрали</small>
                  <strong>
                    {selected?.name}
                    {selected && priceLabel ? ` · ${priceLabel}` : ""}
                  </strong>
                  <span>{selected ? describeOption(selected) : ""}</span>
                </div>
                <button
                  className="button button-primary button-large"
                  type="button"
                  onClick={startPayment}
                  disabled={busy || !selected}
                >
                  {isDemoMode
                    ? "Показать демо-оплату"
                    : busy
                      ? "Создаём платёж…"
                      : "Перейти к оплате"}
                </button>
              </div>

              {error && (
                <div className="auth-error" role="alert">
                  {error}
                </div>
              )}

              {isDemoMode && (
                <p className="muted payment-demo-note">
                  В демо-режиме оплата не выполняется — кнопка показывает, как выглядит экран после
                  успешного платежа.
                </p>
              )}
            </>
          )}
        </section>
      )}

      <section className="cabinet-grid cabinet-grid-bottom">
        <article className="cabinet-card payment-device-addon">
          <header>
            <h3>Дополнительное устройство</h3>
          </header>
          <Mascot variant="subscription-active" className="card-mascot-small" decorative />
          <strong className="big-stat">{formatRubles(EXTRA_DEVICE_PRICE_RUB)}</strong>
          <p className="muted">
            Одно дополнительное место за каждый месяц оплаченного периода. Пока это оформляется
            через поддержку — напишите нам, и место добавят к Вашей подписке.
          </p>
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
