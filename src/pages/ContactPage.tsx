import { routes } from "../app/navigation";
import { Brand } from "../components/Brand";
import { Icon } from "../components/Icon";
import { InviteCard } from "../components/InviteCard";
import { Mascot } from "../components/Mascot";
import { SupportChannels } from "../components/SupportChannels";
import { ThemeToggle, type Theme } from "../components/ThemeToggle";
import { inviterFromUrl } from "../referral";
import "../help.css";

/*
 * Сюда ведёт кнопка поддержки в приложении. Человек приходит с одной
 * мыслью «куда написать», поэтому на странице только выбор канала,
 * и порядок задан его ситуацией: работает VPN, не работает, нет и MAX.
 */

export function ContactPage({
  theme,
  onToggleTheme,
}: {
  theme: Theme;
  onToggleTheme: () => void;
}) {
  const inviter = inviterFromUrl();

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

        {inviter ? (
          <a className="contact-invite-jump" href="#invite">
            <span>🎁 &nbsp;Ваша ссылка приглашения: +15 дней за друга</span>
            <Icon name="arrow-right" />
          </a>
        ) : (
          <a className="contact-invite-jump" href={routes.invite}>
            <span>🎁 &nbsp;Приведите друга: по 15 дней каждому из вас</span>
            <Icon name="arrow-right" />
          </a>
        )}

        <section className="contact-channel-list" aria-label="Способы связи">
          <SupportChannels />
        </section>

        {inviter && (
          <>
            <InviteCard username={inviter} />
            <p className="muted">
              Как это работает и что делает друг:{" "}
              <a href={routes.invite}>партнёрская программа</a>.
            </p>
          </>
        )}

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
