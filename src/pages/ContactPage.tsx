import { useState } from "react";
import { routes } from "../app/navigation";
import { Brand } from "../components/Brand";
import { Icon } from "../components/Icon";
import { Mascot } from "../components/Mascot";
import { SupportChannels } from "../components/SupportChannels";
import { ThemeToggle, type Theme } from "../components/ThemeToggle";
import { inviteLink, inviterFromUrl } from "../referral";
import "../help.css";

/*
 * Сюда ведёт кнопка поддержки в приложении. Человек приходит с одной
 * мыслью «куда написать», поэтому на странице только выбор канала,
 * и порядок задан его ситуацией: работает VPN, не работает, нет и MAX.
 */

const COPIED_HINT_MS = 2500;

/*
 * Карточка с личной ссылкой приглашения. Показывается, только когда
 * страницу открыли из приложения и в адресе есть имя учётки.
 */
function InviteCard({ username }: { username: string }) {
  const link = inviteLink(username);
  const [copied, setCopied] = useState(false);
  const [copyFailed, setCopyFailed] = useState(false);
  const canShare = typeof navigator !== "undefined" && "share" in navigator;

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(link);
      setCopied(true);
      setCopyFailed(false);
      window.setTimeout(() => setCopied(false), COPIED_HINT_MS);
    } catch {
      setCopyFailed(true);
    }
  };

  const share = async () => {
    try {
      await navigator.share({
        title: "VPaNfi",
        text: "Мой VPN. По этой ссылке к первой покупке добавится 15 дней.",
        url: link,
      });
    } catch {
      // Человек закрыл окно «Поделиться»: это не ошибка.
    }
  };

  return (
    <section className="cabinet-card contact-invite" id="invite">
      <span className="contact-channel-when">Приведите друга</span>
      <h2>Ваша ссылка приглашения</h2>
      <p className="muted">
        Друг оплатит подписку по этой ссылке, и каждый из Вас получит по 15 дней. Когда
        друг впервые продлит подписку, Вам добавится ещё 15.
      </p>
      <p className="buy-subscription-link">
        <code>{link}</code>
      </p>
      <div className="contact-invite-actions">
        <button className="button button-primary" type="button" onClick={copy}>
          {copied ? "Скопировано" : "Скопировать ссылку"}
        </button>
        {canShare && (
          <button className="button button-ghost" type="button" onClick={share}>
            Поделиться
          </button>
        )}
      </div>
      {copyFailed && (
        <p className="muted">
          Браузер не разрешил копирование. Ссылку можно выделить и скопировать вручную.
        </p>
      )}
    </section>
  );
}

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

        {inviter && (
          <a className="contact-invite-jump" href="#invite">
            <span>🎁 &nbsp;Ваша ссылка приглашения: +15 дней за друга</span>
            <Icon name="arrow-right" />
          </a>
        )}

        <section className="contact-channel-list" aria-label="Способы связи">
          <SupportChannels />
        </section>

        {inviter && <InviteCard username={inviter} />}

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
