import { maxSupportUrl, supportEmail, telegramSupportUrl } from "../config";
import { Icon } from "./Icon";

/*
 * Три канала поддержки, общие для страницы «Куда написать» и кабинета.
 * Порядок задан ситуацией человека: работает VPN, не работает, нет и MAX.
 * Обёртку с сеткой даёт страница, здесь только сами карточки.
 */
const MAIL_SUBJECT = "VPaNfi: нужна помощь";
const MAIL_BODY =
  "Устройство и приложение: \nСеть (Wi-Fi или мобильная, оператор): \nЧто вижу на экране: \nКогда началось: \n";

export function SupportChannels() {
  return (
    <>
      <a
        className="cabinet-card support-channel is-primary"
        href={telegramSupportUrl}
        target="_blank"
        rel="noreferrer"
      >
        <span className="support-channel-icon">
          <Icon name="telegram" />
        </span>
        <div>
          <span className="contact-channel-when">VPN работает</span>
          <h3>Telegram</h3>
          <p>Самый быстрый способ. Telegram открывается только с включённым VPN.</p>
        </div>
        <strong>
          Написать в Telegram
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
          <span className="contact-channel-when">VPN не работает</span>
          <h3>MAX</h3>
          <p>Мессенджер MAX открывается без VPN. Там отвечает тот же Артём.</p>
        </div>
        <strong>
          Написать в MAX
          <Icon name="arrow-right" />
        </strong>
      </a>

      <a
        className="cabinet-card support-channel"
        href={`mailto:${supportEmail}?subject=${encodeURIComponent(
          MAIL_SUBJECT,
        )}&body=${encodeURIComponent(MAIL_BODY)}`}
      >
        <span className="support-channel-icon">
          <Icon name="mail" />
        </span>
        <div>
          <span className="contact-channel-when">Нет ни VPN, ни MAX</span>
          <h3>Почта</h3>
          <p>
            Работает всегда. Письмо читает Анфиса, ответ приходит в течение нескольких
            часов. Адрес: {supportEmail}
          </p>
        </div>
        <strong>
          Написать на почту
          <Icon name="arrow-right" />
        </strong>
      </a>
    </>
  );
}
