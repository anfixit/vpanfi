import { useEffect, useState, type FormEvent } from "react";
import { shop, ShopRequestError } from "../api/shop";
import type { GuestPurchaseStatus, ShopTariff } from "../api/contracts";
import { navigate, routes } from "../app/navigation";
import { Brand } from "../components/Brand";
import { Mascot } from "../components/Mascot";
import { ThemeToggle, type Theme } from "../components/ThemeToggle";
import { useAsyncResource } from "../hooks/useAsyncResource";
import { legalDocuments, legalPath } from "../legal";

/*
 * Покупка без регистрации.
 *
 * Человек попадает сюда, когда Telegram ему недоступен — а именно ради
 * него сервис и покупают. Поэтому здесь нет ни пароля, ни подтверждения
 * почты: почта нужна только чтобы узнать покупателя при следующем
 * заходе. Аккаунт заводит бот сам в момент оплаты.
 *
 * Оплату подтверждает вебхук платёжной системы, поэтому возврат из
 * платёжки ничего не доказывает: страница спрашивает статус у сервера,
 * пока тот не подтвердит оплату.
 */

const POLL_INTERVAL_MS = 3000;
const POLL_LIMIT = 100; // ~5 минут: дольше человек ждать не станет.

function formatDays(days: number): string {
  if (days % 30 === 0) {
    const months = days / 30;
    if (months === 1) return "1 месяц";
    if (months < 5) return `${months} месяца`;
    return `${months} месяцев`;
  }
  return `${days} дней`;
}

function PurchaseResult({
  token,
  onOpenAuth,
}: {
  token: string;
  onOpenAuth: () => void;
}) {
  const [status, setStatus] = useState<GuestPurchaseStatus | null>(null);
  const [timedOut, setTimedOut] = useState(false);

  useEffect(() => {
    let cancelled = false;
    let attempts = 0;

    const tick = async () => {
      if (cancelled) return;

      try {
        const next = await shop.getPurchaseStatus(token);
        if (cancelled) return;
        setStatus(next);
        /* Дальше спрашивать нечего: подписка выдана либо платёж не состоялся. */
        if (next.done || next.failed) return;
      } catch {
        /* Разрыв связи не повод сдаваться: следующая попытка через паузу. */
      }

      attempts += 1;
      if (attempts >= POLL_LIMIT) {
        setTimedOut(true);
        return;
      }
      window.setTimeout(tick, POLL_INTERVAL_MS);
    };

    void tick();
    return () => {
      cancelled = true;
    };
  }, [token]);

  if (status?.done && status.subscriptionUrl) {
    return (
      <section className="cabinet-card buy-result">
        <Mascot variant="greeting" className="card-mascot" decorative />
        <h1>Готово, подписка оформлена</h1>

        <p>
          <strong>Это ваша подписка. Нажмите на неё — она скопируется.</strong>
        </p>
        <p className="buy-subscription-link">
          <code>{status.subscriptionUrl}</code>
        </p>

        <p className="muted">
          Ссылку нужно вставить в приложение — сама по себе она ничего не
          включает. Сохраните её: понадобится, чтобы подключить другое
          устройство.
        </p>

        <div className="buy-apps">
          <span className="muted">Приложение для вашего устройства:</span>
          <div className="buy-app-links">
            <a
              className="button button-ghost"
              href="https://apps.apple.com/ru/app/incy/id6756943388"
              target="_blank"
              rel="noreferrer noopener"
            >
              iPhone — INCY
            </a>
            <a
              className="button button-ghost"
              href="https://play.google.com/store/apps/details?id=com.happproxy"
              target="_blank"
              rel="noreferrer noopener"
            >
              Android — HAPP
            </a>
          </div>
        </div>

        {/*
          * Кабинет здесь не предлагается: аккаунта у покупателя ещё нет, а
          * в браузере мог остаться чужой сеанс с прошлого входа — человек
          * попадал бы в чужую подписку вместо своей.
          */}
        <p className="muted">
          Чтобы следить за сроком и подключать устройства из кабинета,
          заведите аккаунт на ту же почту.
        </p>
        <button
          className="button button-primary button-large"
          type="button"
          onClick={onOpenAuth}
        >
          Создать аккаунт
        </button>
      </section>
    );
  }

  if (status?.failed) {
    return (
      <section className="cabinet-card buy-result">
        <Mascot variant="qr" className="card-mascot" decorative />
        <h1>Оплата не прошла</h1>
        <p className="muted">
          Деньги не списаны. Попробуйте оформить заново, а если списание всё
          же произошло — напишите в поддержку, разберёмся.
        </p>
        <button
          className="button button-primary button-large"
          type="button"
          onClick={() => navigate(routes.buy)}
        >
          Оформить заново
        </button>
      </section>
    );
  }

  return (
    <section className="cabinet-card buy-result">
      <Mascot variant="qr" className="card-mascot" decorative />
      <h1>{timedOut ? "Оплата пока не подтвердилась" : "Ждём подтверждения оплаты"}</h1>
      <p className="muted">
        {timedOut
          ? "Если деньги списались, подписка появится сама — обновите страницу через пару минут. Если нет, напишите в поддержку."
          : "Это занимает несколько секунд. Страницу закрывать не нужно."}
      </p>
    </section>
  );
}

export function BuyPage({
  theme,
  onToggleTheme,
  onOpenAuth,
}: {
  theme: Theme;
  onToggleTheme: () => void;
  onOpenAuth: () => void;
}) {
  const config = useAsyncResource(shop.getConfig);
  const payMethods = useAsyncResource(shop.getPaymentMethods);

  const [tariffId, setTariffId] = useState<number | null>(null);
  const [email, setEmail] = useState("");
  /* Код способа у Platega: 2 СБП, 11 карта, 13 криптовалюта. */
  const [option, setOption] = useState<number | null>(null);
  /* Отметка напротив каждого документа отдельно — как при регистрации. */
  const [accepted, setAccepted] = useState<Record<string, boolean>>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  /* Возврат из платёжки: токен в адресе означает, что покупка уже создана. */
  const token = new URLSearchParams(window.location.search).get("token");

  const allAccepted = legalDocuments.every((item) => accepted[item.slug]);
  const tariffs = config.data?.tariffs ?? [];
  const methods = payMethods.data ?? [];
  const selected: ShopTariff | null =
    tariffs.find((item) => item.id === tariffId) ?? null;

  useEffect(() => {
    if (tariffId === null && tariffs.length > 0) setTariffId(tariffs[0].id);
  }, [tariffId, tariffs]);

  useEffect(() => {
    if (option === null && methods.length > 0) setOption(methods[0].code);
  }, [option, methods]);

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (busy || !selected) return;

    const period = selected.periods[0];
    if (!period) return;

    setBusy(true);
    setError(null);

    try {
      const purchase = await shop.createPurchase({
        tariffId: selected.id,
        periodDays: period.days,
        email: email.trim(),
        paymentMethod: option,
      });

      if (purchase.paymentUrl) {
        window.location.href = purchase.paymentUrl;
        return;
      }

      /* Ссылки нет — показываем ожидание, статус всё равно спросим у сервера. */
      navigate(`${routes.buy}?token=${encodeURIComponent(purchase.token)}` as never);
    } catch (reason: unknown) {
      setError(
        reason instanceof ShopRequestError
          ? reason.message
          : "Не получилось оформить покупку. Попробуйте ещё раз.",
      );
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <header className="site-header shell">
        <Brand />
        <div className="header-actions">
          <ThemeToggle theme={theme} onToggle={onToggleTheme} />
          <button
            className="button button-ghost"
            type="button"
            onClick={() => navigate(routes.landing)}
          >
            На главную
          </button>
        </div>
      </header>

      <main className="buy-page shell">
        {token ? (
          <PurchaseResult token={token} onOpenAuth={onOpenAuth} />
        ) : (
          <section className="cabinet-card">
            <span className="section-kicker">Без регистрации</span>
            <h1>Оформление подписки</h1>
            <p className="muted">
              Telegram не нужен: выберите срок, укажите почту и оплатите.
              Ссылку на подписку покажем сразу после оплаты.
            </p>

            {config.loading && <p className="muted">Загружаем тарифы…</p>}
            {config.error && (
              <div className="auth-error" role="alert">
                Не удалось загрузить тарифы. Обновите страницу.
              </div>
            )}

            {config.data && (
              <form className="buy-form" onSubmit={submit}>
                <div className="tariff-grid">
                  {tariffs.map((tariff) => {
                    const period = tariff.periods[0];
                    if (!period) return null;
                    return (
                      <button
                        className={`tariff ${tariff.id === tariffId ? "is-selected" : ""}`.trim()}
                        type="button"
                        key={tariff.id}
                        aria-pressed={tariff.id === tariffId}
                        onClick={() => setTariffId(tariff.id)}
                      >
                        <span>{formatDays(period.days)}</span>
                        <strong>{period.priceLabel}</strong>
                        <small>{tariff.deviceLimit} устройства</small>
                      </button>
                    );
                  })}
                </div>

                {/*
                 * Про несгорающие дни сказано в кабинете, в справке и
                 * в оферте, а на странице оплаты, где и принимается
                 * решение, не было ни слова. Человек с действующим
                 * доступом видел только цену и разумно откладывал
                 * покупку до конца срока, чтобы не потерять остаток.
                 * 31.08.2026 так ушёл готовый покупатель.
                 */}
                <p className="buy-note">
                  Оставшиеся дни не сгорают: новый срок прибавляется
                  к текущему.
                </p>

                <label>
                  Почта
                  <input
                    type="email"
                    value={email}
                    onChange={(event) => setEmail(event.target.value)}
                    placeholder="you@example.com"
                    autoComplete="email"
                    required
                    maxLength={255}
                    aria-describedby="buy-email-hint"
                  />
                </label>
                <p className="muted" id="buy-email-hint">
                  Нужна, чтобы узнать вас при следующем заходе. Пароль
                  придумывать не надо.
                </p>

                {methods.length > 1 && (
                  <fieldset className="buy-methods">
                    <legend>Способ оплаты</legend>
                    {methods.map((item) => (
                      <label key={item.code} className="buy-method">
                        <input
                          type="radio"
                          name="payment-option"
                          value={item.code}
                          checked={option === item.code}
                          onChange={() => setOption(item.code)}
                        />
                        <span className="buy-method-copy">
                          <strong>{item.name}</strong>
                          <small>{item.description}</small>
                        </span>
                      </label>
                    ))}
                  </fieldset>
                )}

                <fieldset className="auth-consent-group">
                  <legend>Перед оплатой подтвердите согласие</legend>
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

                {error && (
                  <div className="auth-error" role="alert">
                    {error}
                  </div>
                )}

                <button
                  className="button button-primary button-large full-button"
                  type="submit"
                  disabled={busy || !selected || !allAccepted}
                >
                  {busy
                    ? "Готовим оплату…"
                    : selected
                      ? `Оплатить ${selected.periods[0]?.priceLabel ?? ""}`
                      : "Выберите тариф"}
                </button>
              </form>
            )}
          </section>
        )}
      </main>
    </>
  );
}
