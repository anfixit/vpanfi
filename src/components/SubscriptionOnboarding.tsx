import type { SubscriptionLink } from "../api/contracts";
import { telegramBotUrl } from "../config";
import { countries, tariffs } from "../data";
import { Icon } from "./Icon";
import { Mascot } from "./Mascot";
import { SubscriptionLinkForm } from "./SubscriptionLinkForm";

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
            <article
              className={`tariff ${tariff.popular ? "is-popular" : ""}`.trim()}
              key={tariff.period}
            >
              {tariff.popular && <span className="popular-label">выгодно</span>}
              <span>{tariff.period}</span>
              <strong>{tariff.price}</strong>
              {tariff.saving && <small>{tariff.saving}</small>}
            </article>
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
            {countries.slice(0, VISIBLE_COUNTRIES).map((country) => (
              <span className="country-chip" key={country.name}>
                <span aria-hidden="true">{country.flag}</span> {country.name}
              </span>
            ))}
          </div>
        </div>

        <a
          className="button button-primary button-large full-button"
          href={telegramBotUrl}
          target="_blank"
          rel="noreferrer"
        >
          Оформить подписку в боте
        </a>
        <p className="muted offer-note">
          Оплата и оформление пока проходят в боте — он же пришлёт ссылку,
          которую нужно вставить ниже.
        </p>
      </section>

      <SubscriptionLinkForm onLinked={onLinked} />
    </div>
  );
}
