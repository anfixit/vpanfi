import { useState } from "react";
import { inviteLink } from "../referral";

/*
 * Карточка с личной ссылкой приглашения. Показывается там, где известно
 * имя учётки: страницу открыли из приложения, и панель подставила его
 * в адрес.
 *
 * Живёт отдельным компонентом, потому что нужна на двух страницах:
 * «куда написать» и «приведите друга». Один текст условий на две
 * страницы: разъехавшиеся сроки читаются как обман.
 */

const COPIED_HINT_MS = 2500;

export function InviteCard({ username }: { username: string }) {
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
