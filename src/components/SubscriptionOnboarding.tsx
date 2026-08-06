import type { SubscriptionLink } from "../api/contracts";
import { api } from "../api/client";
import { navigate, routes } from "../app/navigation";
import { tariffs } from "../data";
import { Icon } from "./Icon";
import { Mascot } from "./Mascot";
import { SubscriptionLinkForm } from "./SubscriptionLinkForm";
import { useAsyncResource } from "../hooks/useAsyncResource";

/*
 * Экран для аккаунта без подписки. Порядок важен: сначала предложение
 * и условия, и только потом поле для тех, у кого подписка уже есть.
 * Наоборот получалось, что кабинет требует то, чего у человека нет.
 */

const VISIBLE_COUNTRIES = 6;

const included = [
  "Три устройства одновременно",
  "Без лимита трафика",
  "Оставшиеся дни не сгорают при продлении",
  "Поддержка отвечает человеческим языком",
];

export function SubscriptionOnboarding({
  onLinked,
}: {
  onLinked: (result: SubscriptionLink) => void;
}) {
  const countries = useAsyncResource(api.getCountries);

  return (
    <div className="cabinet-page subscription-onboarding">
      <section className="page-intro cabinet-card">
        <div>
          <span className="cabinet-kicker">Добро пожаловать</span>
          <h2>Выберите подписку</h2>
          <p className="muted">
            Один тариф на все устройства: телефон, компьютер и телевизор.
            Ничего настраивать не нужно — Анфиса покажет каждый шаг.
          </p>
        </div>
        <Mascot variant="subscription-active" className="page-intro-mascot" decorative />
      </section>

      <section className="cabinet-card offer-card">
        <div className="section-heading compact-heading">
          <div>
            <span className="section-kicker">Чем дольше, тем выгоднее</span>
            <h2>Тарифы</h2>
          </div>
        </div>

        <div className="tariff-grid">
          {tariffs.map((tariff) => (
            <button
              className={`tariff ${tariff.popular ? "is-popular" : ""}`.trim()}
              type="button"
              key={tariff.period}
              onClick={() => navigate(routes.buy)}
            >
              {tariff.popular && <span className="popular-label">выгодно</span>}
              <span>{tariff.period}</span>
              <strong>{tariff.price}</strong>
              {tariff.saving && <small>{tariff.saving}</small>}
            </button>
          ))}
        </div>

        <ul className="offer-included">
          {included.map((item) => (
            <li key={item}>
              <Icon name="check" />
              {item}
            </li>
          ))}
        </ul>

        <div className="offer-countries">
          <span className="muted">Страны на выбор</span>
          <div className="country-list">
            {(countries.data ?? []).slice(0, VISIBLE_COUNTRIES).map((country) => (
              <span className="country-chip" key={country.code}>
                <span aria-hidden="true">{country.flag}</span> {country.name}
              </span>
            ))}
          </div>
        </div>

        <button
          className="button button-primary button-large full-button"
          type="button"
          onClick={() => navigate(routes.buy)}
        >
          Оформить подписку
        </button>
        <p className="muted offer-note">
          Оплата проходит здесь же — Telegram не нужен. Ссылку на подписку
          покажем сразу после оплаты.
        </p>
      </section>

      <SubscriptionLinkForm onLinked={onLinked} />
    </div>
  );
}
