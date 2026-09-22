import { useMemo, useState } from "react";
import { api } from "../api/client";
import { useDemoNotice } from "../components/DemoNotice";
import { Icon } from "../components/Icon";
import { Mascot } from "../components/Mascot";
import { EmptyState, ErrorState, LoadingState } from "../components/ResourceState";
import { QrCode } from "../components/QrCode";
import { platforms } from "../data";
import { appDeepLink, detectPlatform, lacksGooglePlay } from "../platform";
import { useAsyncResource } from "../hooks/useAsyncResource";

const COPIED_HINT_MS = 2400;

export function ConnectPage() {
  const clients = useAsyncResource(api.getConnectionClients);
  const subscriptionLink = useAsyncResource(api.getSubscription);
  const { explain } = useDemoNotice();
  // Устройство угадываем сами: человек с айфона не должен начинать с Google Play.
  const [selectedPlatform, setSelectedPlatform] = useState(
    () => detectPlatform() ?? "Android",
  );
  const [showAlternatives, setShowAlternatives] = useState(false);
  const [copied, setCopied] = useState(false);
  const [appDidNotOpen, setAppDidNotOpen] = useState(false);

  const platformClients = useMemo(
    () => (clients.data ?? []).filter((client) => client.platform === selectedPlatform),
    [clients.data, selectedPlatform],
  );
  // Телефону без Google Play первым показываем файл APK, иначе «Установить»
  // уведёт его в магазин, которого на нём нет.
  const apkFirst = selectedPlatform === "Android" && lacksGooglePlay();
  const recommended =
    (apkFirst ? platformClients.find((client) => client.id.endsWith("-apk")) : undefined) ??
    platformClients.find((client) => client.recommended) ??
    platformClients[0];
  const alternatives = platformClients.filter((client) => client.id !== recommended?.id);

  const connectionKey = subscriptionLink.data?.subscriptionUrl ?? null;
  // Сервер ссылку для кнопки не присылает, собираем её здесь из адреса
  // подписки: без неё после установки приложения человеку нечего нажать.
  const deepLink = recommended
    ? (recommended.deepLink ?? appDeepLink(recommended.id, connectionKey))
    : null;

  const copyKey = async () => {
    if (!connectionKey) return;

    try {
      await navigator.clipboard.writeText(connectionKey);
      setCopied(true);
      window.setTimeout(() => setCopied(false), COPIED_HINT_MS);
    } catch {
      explain("Браузер не разрешил копирование. Ключ можно выделить в разделе «Технические детали».");
    }
  };

  if (clients.loading && !clients.data) {
    return <LoadingState label="Анфиса подбирает приложение…" />;
  }
  if (clients.error || !clients.data) {
    return (
      <ErrorState
        message={clients.error ?? "Не удалось загрузить приложения"}
        onRetry={clients.reload}
      />
    );
  }

  return (
    <div className="cabinet-page">
      <section className="page-intro cabinet-card">
        <div>
          <span className="cabinet-kicker">Один экран, один следующий шаг</span>
          <h2>Подключите устройство</h2>
          <p className="muted">
            VPN работает через отдельное приложение. Ниже Ваша ссылка для подключения: её нужно
            вставить в это приложение. Сама по себе в браузере она ничего не включает.
          </p>
          {connectionKey && (
            <div className="connection-key-block">
              <span className="connection-key-label">Ваша ссылка для подключения</span>
              <p className="buy-subscription-link">
                <code>{connectionKey}</code>
              </p>
              <button className="button button-secondary" type="button" onClick={copyKey}>
                {copied ? "Скопировано" : "Скопировать ссылку"}
              </button>
              <p className="muted connection-key-hint">
                Как использовать: шаг 1 выберите устройство, шаг 2 установите приложение, шаг 3
                нажмите «Открыть в приложении» или вставьте скопированную ссылку в приложение
                через значок «+».
              </p>
            </div>
          )}
        </div>
        <Mascot variant="phone" className="page-intro-mascot" decorative />
      </section>

      <section className="cabinet-card connection-wizard">
        <div className="wizard-step-heading">
          <span>1</span>
          <div>
            <h3>Что Вы подключаете?</h3>
            <p className="muted">Можно вернуться и выбрать другое устройство в любой момент.</p>
          </div>
        </div>
        <div className="platform-selector" role="group" aria-label="Выбор устройства">
          {platforms.map((platform) => (
            <button
              className={selectedPlatform === platform.name ? "is-active" : ""}
              type="button"
              key={platform.name}
              aria-pressed={selectedPlatform === platform.name}
              onClick={() => {
                setSelectedPlatform(platform.name);
                setShowAlternatives(false);
              }}
            >
              <Icon name={platform.icon} />
              {platform.name}
            </button>
          ))}
        </div>
      </section>

      <section className="cabinet-card connection-wizard">
        <div className="wizard-step-heading">
          <span>2</span>
          <div>
            <h3>Установите приложение</h3>
            <p className="muted">Для большинства пользователей лучше всего подходит HAPP.</p>
          </div>
        </div>
        {recommended ? (
          <div className="client-card is-recommended">
            <div className="happ-logo">{recommended.name.slice(0, 4).toUpperCase()}</div>
            <div className="client-copy">
              <span className="recommended-label">Рекомендуем</span>
              <h3>{recommended.name}</h3>
              <p>{recommended.description}</p>
            </div>
            <a
              className="button button-primary"
              href={recommended.installUrl}
              target="_blank"
              rel="noreferrer"
            >
              Установить
            </a>
          </div>
        ) : (
          <EmptyState
            mascot="laptop"
            title="Приложение ещё готовится"
            description={`Для платформы «${selectedPlatform}» мы пока добавляем инструкцию.`}
          />
        )}
        {alternatives.length > 0 && (
          <>
            <button
              className="alternative-apps"
              type="button"
              aria-expanded={showAlternatives}
              onClick={() => setShowAlternatives((value) => !value)}
            >
              <span>
                <strong>Другие приложения</strong>
                <small>Для тех, кто уже знает, что ему нужно</small>
              </span>
              <Icon name="chevron-down" className={showAlternatives ? "icon-rotated" : ""} />
            </button>
            {showAlternatives && (
              <div className="alternative-client-list">
                {alternatives.map((client) => (
                  <div className="client-card" key={client.id}>
                    <div className="happ-logo">{client.name.slice(0, 2).toUpperCase()}</div>
                    <div className="client-copy">
                      <h3>{client.name}</h3>
                      <p>{client.description}</p>
                    </div>
                    <a
                      className="button button-secondary"
                      href={client.installUrl}
                      target="_blank"
                      rel="noreferrer"
                    >
                      Установить
                    </a>
                  </div>
                ))}
              </div>
            )}
          </>
        )}
      </section>

      <section className="connection-final-grid">
        <article className="cabinet-card connection-wizard">
          <div className="wizard-step-heading">
            <span>3</span>
            <div>
              <h3>Добавьте подключение</h3>
              <p className="muted">
                Приложение уже установлено? Нажмите кнопку ниже, подписка добавится сама.
                Если кнопка не сработала, скопируйте ключ, откройте приложение и вставьте
                его из буфера обмена (значок «+»). QR-код нужен для другого устройства.
              </p>
            </div>
          </div>
          <div className="connection-methods">
            {deepLink && (
              <a
                className="button button-primary button-large"
                href={deepLink}
                onClick={() => {
                  // Если приложения нет, ссылка не делает ничего и молчит.
                  // Когда приложение открылось, страница уходит в фон, и
                  // подсказка не появляется.
                  window.setTimeout(() => {
                    if (document.visibilityState === "visible") setAppDidNotOpen(true);
                  }, 1800);
                }}
              >
                Открыть в приложении
              </a>
            )}
            <button
              className="button button-secondary button-large"
              type="button"
              onClick={copyKey}
              disabled={!connectionKey}
            >
              {copied ? "Ключ скопирован" : "Скопировать ключ"}
            </button>
          </div>
          {appDidNotOpen && (
            <p className="connection-hint" role="status">
              Приложение не открылось? Значит, оно ещё не установлено: вернитесь к шагу 2,
              нажмите «Установить», дождитесь установки и нажмите эту кнопку ещё раз.
            </p>
          )}
          {!connectionKey && (
            <p className="muted">
              Ключ появится, как только Вы добавите подписку на главной
              странице кабинета.
            </p>
          )}
          {copied && (
            <div className="connection-success" role="status">
              <Mascot variant="connected" className="card-mascot-small" decorative />
              <div>
                <strong>Готово, ключ у Вас</strong>
                <p className="muted">Вставьте его в приложение — подключение появится сразу.</p>
              </div>
            </div>
          )}
          {connectionKey && (
            <details className="technical-details">
              <summary>Технические детали</summary>
              <p className="muted">
                Это ссылка на подписку. Обычно её не нужно открывать вручную — приложение всё
                сделает само.
              </p>
              <code>{connectionKey}</code>
            </details>
          )}
        </article>

        <article className="cabinet-card qr-card">
          <Mascot variant="qr" className="card-mascot" decorative />
          <h3>QR-код</h3>
          {connectionKey ? (
            <>
              <QrCode value={connectionKey} label="QR-код Вашей подписки" />
              <p className="muted">Наведите камеру устройства, которое хотите подключить.</p>
            </>
          ) : (
            <p className="muted">
              QR-код появится вместе с подпиской: в нём зашита именно Ваша ссылка.
            </p>
          )}
        </article>
      </section>
    </div>
  );
}
