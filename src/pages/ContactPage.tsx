import { routes } from "../app/navigation";
import { Brand } from "../components/Brand";
import { Icon } from "../components/Icon";
import { Mascot } from "../components/Mascot";
import { ThemeToggle, type Theme } from "../components/ThemeToggle";
import { maxSupportUrl, supportEmail, telegramSupportUrl } from "../config";
import "../help.css";

/*
 * Сюда ведёт кнопка поддержки в приложении. Человек приходит с одной
 * мыслью «куда написать», поэтому на странице только выбор канала,
 * и порядок задан его ситуацией: работает VPN, не работает, нет и MAX.
 */
const MAIL_SUBJECT = "VPaNfi: нужна помощь";
const MAIL_BODY =
  "Устройство и приложение: \nСеть (Wi-Fi или мобильная, оператор): \nЧто вижу на экране: \nКогда началось: \n";

export function ContactPage({
  theme,
  onToggleTheme,
}: {
  theme: Theme;
  onToggleTheme: () => void;
}) {
  return (
    <>
      <header className="site-header help-site-header shell">
        <Brand />
        <div className="header-actions">
          <ThemeToggle theme={theme} onToggle={onToggleTheme} />
          <a className="button button-ghost" href={routes.help}>
            Инструкции
          </a>
        </div>
      </header>
      <main className="help-page shell contact-page">
        <section className="help-intro">
          <div>
            <span className="section-kicker">Поддержка VPaNfi · без входа в аккаунт</span>
            <h1>
              Куда написать.
              <br />
              <span>Выберите то, что у Вас сейчас открывается.</span>
            </h1>
            <p>
              Отвечает Артём, помощник поддержки. Сложные вопросы и всё, что связано с
              деньгами, он передаёт Анфисе.
            </p>
          </div>
          <Mascot variant="support" className="help-hero-mascot" decorative />
        </section>

        <section className="contact-channel-list" aria-label="Способы связи">
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
        </section>

        <section className="cabinet-card contact-tips">
          <h2>Чтобы помочь с первого сообщения</h2>
          <ul>
            <li>Напишите, какое у Вас устройство и приложение.</li>
            <li>Скажите, с чего выходите в интернет: мобильная сеть или Wi-Fi.</li>
            <li>
              Приложите скриншот экрана с подпиской. Ссылку и QR-код на нём закройте.
            </li>
          </ul>
          <p className="muted">
            Пароли, коды из сообщений и данные карты поддержке не нужны никогда.
          </p>
          <a className="button button-ghost" href={`${routes.help}#trouble`}>
            Сначала попробовать самому: VPN не работает
          </a>
        </section>
      </main>
    </>
  );
}
