import { useMemo, useState } from "react";
import { api } from "../api/client";
import { Mascot } from "../components/Mascot";
import { ErrorState, LoadingState } from "../components/ResourceState";
import { platforms } from "../data";
import { useAsyncResource } from "../hooks/useAsyncResource";

const demoConnectionKey = "https://connect.vpanfi.example/demo-subscription";

export function ConnectPage() {
  const clients = useAsyncResource(api.getConnectionClients);
  const [selectedPlatform, setSelectedPlatform] = useState("Android");
  const [showAlternatives, setShowAlternatives] = useState(false);
  const [copied, setCopied] = useState(false);

  const platformClients = useMemo(
    () => (clients.data ?? []).filter((client) => client.platform === selectedPlatform),
    [clients.data, selectedPlatform],
  );
  const recommended = platformClients.find((client) => client.recommended) ?? platformClients[0];
  const alternatives = platformClients.filter((client) => client.id !== recommended?.id);

  const copyKey = async () => {
    try {
      await navigator.clipboard.writeText(demoConnectionKey);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1800);
    } catch {
      setCopied(false);
    }
  };

  if (clients.loading && !clients.data) return <LoadingState label="Анфиса подбирает приложение…" />;
  if (clients.error || !clients.data) return <ErrorState message={clients.error ?? "Не удалось загрузить приложения"} onRetry={clients.reload} />;

  return (
    <div className="cabinet-page">
      <section className="page-intro cabinet-card">
        <div>
          <span className="cabinet-kicker">Один экран, один следующий шаг</span>
          <h2>Подключите устройство</h2>
          <p className="muted">Сначала выберите устройство. Мы покажем одно рекомендуемое приложение и короткую инструкцию.</p>
        </div>
        <Mascot variant="checking" className="page-intro-mascot" decorative />
      </section>

      <section className="cabinet-card connection-wizard">
        <div className="wizard-step-heading"><span>1</span><div><h3>Что Вы подключаете?</h3><p className="muted">Можно вернуться и выбрать другое устройство в любой момент.</p></div></div>
        <div className="platform-selector">
          {platforms.map((platform) => (
            <button
              className={selectedPlatform === platform.name ? "is-active" : ""}
              type="button"
              key={platform.name}
              onClick={() => { setSelectedPlatform(platform.name); setShowAlternatives(false); }}
            >
              <span aria-hidden="true">{platform.icon}</span>
              {platform.name}
            </button>
          ))}
        </div>
      </section>

      <section className="cabinet-card connection-wizard">
        <div className="wizard-step-heading"><span>2</span><div><h3>Установите приложение</h3><p className="muted">Для большинства пользователей лучше всего подходит HAPP.</p></div></div>
        {recommended ? (
          <div className="client-card is-recommended">
            <div className="happ-logo">{recommended.name.slice(0, 4).toUpperCase()}</div>
            <div className="client-copy"><span className="recommended-label">Рекомендуем</span><h3>{recommended.name}</h3><p>{recommended.description}</p></div>
            <a className="button button-primary" href={recommended.installUrl} target="_blank" rel="noreferrer">Установить</a>
          </div>
        ) : (
          <p className="muted">Для этой платформы приложение пока добавляется.</p>
        )}
        {alternatives.length > 0 && (
          <>
            <button className="alternative-apps" type="button" onClick={() => setShowAlternatives((value) => !value)}>
              <span><strong>Другие приложения</strong><small>Для тех, кто уже знает, что ему нужно</small></span>
              <span aria-hidden="true">{showAlternatives ? "⌃" : "⌄"}</span>
            </button>
            {showAlternatives && <div className="alternative-client-list">{alternatives.map((client) => (
              <div className="client-card" key={client.id}><div className="happ-logo">{client.name.slice(0, 2).toUpperCase()}</div><div className="client-copy"><h3>{client.name}</h3><p>{client.description}</p></div><a className="button button-secondary" href={client.installUrl} target="_blank" rel="noreferrer">Установить</a></div>
            ))}</div>}
          </>
        )}
      </section>

      <section className="connection-final-grid">
        <article className="cabinet-card connection-wizard">
          <div className="wizard-step-heading"><span>3</span><div><h3>Добавьте подключение</h3><p className="muted">Откройте приложение по кнопке или отсканируйте QR-код другим устройством.</p></div></div>
          <div className="connection-methods">
            {recommended?.deepLink && <a className="button button-primary button-large" href={recommended.deepLink}>Открыть в приложении</a>}
            <button className="button button-secondary button-large" type="button" onClick={copyKey}>{copied ? "Скопировано ✓" : "Скопировать ключ"}</button>
          </div>
          <details className="technical-details"><summary>Технические детали</summary><code>{demoConnectionKey}</code></details>
        </article>

        <article className="cabinet-card qr-card">
          <Mascot variant="qr" className="card-mascot" decorative />
          <h3>QR-код</h3>
          <div className="demo-qr" aria-label="Демонстрационный QR-код"><span /></div>
          <p className="muted">Наведите камеру устройства, которое хотите подключить.</p>
        </article>
      </section>
    </div>
  );
}
