import { useEffect, useState, type FormEvent } from "react";
import { api, ApiRequestError } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { useDemoNotice } from "../components/DemoNotice";
import { Icon } from "../components/Icon";
import { Mascot } from "../components/Mascot";
import { ErrorState, LoadingState } from "../components/ResourceState";
import { useAsyncResource } from "../hooks/useAsyncResource";

const PENDING_BACKEND = "Это действие включится вместе с API профиля на сервере.";
const SAVED_HINT_MS = 2600;

function ConnectionStatus({ connected }: { connected: boolean }) {
  return (
    <span className={`connection-status ${connected ? "is-connected" : ""}`}>
      {connected ? "Подключено" : "Не подключено"}
    </span>
  );
}

export function ProfilePage() {
  // Профиль берётся из того же места, что и приветствие в шапке:
  // раньше форма читала его из ответа дашборда и показывала чужие
  // демонстрационные данные.
  const { profile, applyProfile, logout } = useAuth();
  const subscriptionLink = useAsyncResource(api.getSubscription);
  const { explain } = useDemoNotice();

  const [displayName, setDisplayName] = useState("");
  const [email, setEmail] = useState("");
  const [busy, setBusy] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!profile) return;
    setDisplayName(profile.displayName);
    setEmail(profile.email);
  }, [profile]);

  const unlinkSubscription = async () => {
    const confirmed = window.confirm(
      "Отвязать подписку от этого аккаунта? Сама подписка сохранится, " +
        "её можно будет привязать снова по той же ссылке.",
    );
    if (!confirmed) return;

    await api.unlinkSubscription();
    subscriptionLink.reload();
  };

  const save = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (busy) return;

    setBusy(true);
    setError(null);
    setSaved(false);

    try {
      applyProfile(
        await api.updateProfile({
          displayName: displayName.trim(),
          email: email.trim(),
        }),
      );
      setSaved(true);
      window.setTimeout(() => setSaved(false), SAVED_HINT_MS);
    } catch (reason: unknown) {
      setError(
        reason instanceof ApiRequestError
          ? reason.message
          : "Не удалось сохранить изменения",
      );
    } finally {
      setBusy(false);
    }
  };

  if (!profile) {
    if (subscriptionLink.error) {
      return (
        <ErrorState message={subscriptionLink.error} onRetry={subscriptionLink.reload} />
      );
    }
    return <LoadingState label="Анфиса открывает профиль…" />;
  }

  const unchanged =
    displayName.trim() === profile.displayName && email.trim() === profile.email;

  const linkedAccounts = [
    {
      key: "telegram",
      name: "Telegram",
      note: "Вход через знакомый аккаунт и связь с поддержкой.",
      mark: "TG",
      markClass: "tg",
      connected: profile.telegramLinked,
    },
    {
      key: "yandex",
      name: "Яндекс",
      note: "Быстрый вход без отдельного пароля.",
      mark: "Я",
      markClass: "ya",
      connected: profile.yandexLinked,
    },
    {
      key: "vk",
      name: "VK",
      note: "Ещё один удобный способ войти в кабинет.",
      mark: "VK",
      markClass: "vk",
      connected: profile.vkLinked,
    },
  ];

  return (
    <div className="cabinet-page">
      <section className="page-intro cabinet-card">
        <div>
          <span className="cabinet-kicker">Ваш аккаунт</span>
          <h2>Профиль</h2>
          <p className="muted">Здесь можно изменить данные и привязать удобные способы входа.</p>
        </div>
        <Mascot variant="greeting" className="page-intro-mascot" decorative />
      </section>

      <section className="profile-grid">
        <form className="cabinet-card profile-details" onSubmit={save}>
          <header>
            <span className="cabinet-card-icon">
              <Icon name="profile" />
            </span>
            <h3>Основные данные</h3>
          </header>
          <label>
            Имя
            <input
              value={displayName}
              onChange={(event) => setDisplayName(event.target.value)}
              autoComplete="name"
              required
              maxLength={80}
            />
          </label>
          <label>
            Email
            <input
              type="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              autoComplete="email"
              required
            />
          </label>
          {error && (
            <div className="auth-error" role="alert">
              {error}
            </div>
          )}
          {saved && (
            <div className="profile-saved" role="status">
              Изменения сохранены
            </div>
          )}
          <button
            className="button button-primary"
            type="submit"
            disabled={busy || unchanged || !displayName.trim()}
          >
            {busy ? "Сохраняем…" : "Сохранить изменения"}
          </button>
        </form>

        <article className="cabinet-card profile-security">
          <header>
            <span className="cabinet-card-icon">
              <Icon name="shield" />
            </span>
            <h3>Безопасность</h3>
          </header>
          <div className="security-row">
            <div>
              <strong>Пароль</strong>
              <p className="muted">
                {profile.passwordEnabled ? "Пароль установлен" : "Пароль ещё не создан"}
              </p>
            </div>
            <button
              className="button button-secondary"
              type="button"
              onClick={() => explain(PENDING_BACKEND)}
            >
              Изменить
            </button>
          </div>
          <div className="security-row">
            <div>
              <strong>Активные сеансы</strong>
              <p className="muted">Управление входами на других устройствах.</p>
            </div>
            <button className="button button-secondary" type="button" onClick={() => logout()}>
              Выйти везде
            </button>
          </div>
        </article>
      </section>

      <section className="cabinet-card linked-accounts">
        <div className="section-heading compact-heading">
          <div>
            <span className="section-kicker">Вход без лишних препятствий</span>
            <h2>Связанные аккаунты</h2>
          </div>
        </div>
        <div className="linked-account-list">
          {linkedAccounts.map((account) => (
            <div className="linked-account" key={account.key}>
              <span className={account.markClass} aria-hidden="true">
                {account.mark}
              </span>
              <div>
                <strong>{account.name}</strong>
                <p>{account.note}</p>
              </div>
              <ConnectionStatus connected={account.connected} />
              <button
                className="button button-ghost"
                type="button"
                onClick={() =>
                  explain(`Вход через ${account.name} появится после настройки ключей приложения.`)
                }
              >
                {account.connected ? "Отвязать" : "Подключить"}
              </button>
            </div>
          ))}
        </div>
      </section>

      <section className="cabinet-card linked-subscription">
        <div>
          <h3>Подписка</h3>
          {subscriptionLink.data?.linked ? (
            <p className="muted">
              Привязана к аккаунту панели{" "}
              <strong>{subscriptionLink.data.panelUsername ?? "без имени"}</strong>. Срок и
              устройства всегда берутся из панели.
            </p>
          ) : (
            <p className="muted">
              Подписка пока не привязана. Добавьте её на главной странице кабинета.
            </p>
          )}
        </div>
        {subscriptionLink.data?.linked && (
          <button className="button button-secondary" type="button" onClick={unlinkSubscription}>
            Отвязать
          </button>
        )}
      </section>

      <section className="cabinet-card danger-zone">
        <div>
          <h3>Удаление аккаунта</h3>
          <p className="muted">
            Аккаунт и история будут удалены после подтверждения. Активная подписка при этом не
            возвращается автоматически.
          </p>
        </div>
        <button
          className="button button-ghost danger-action"
          type="button"
          onClick={() =>
            explain(
              "Удаление аккаунта включится вместе с API профиля: оно необратимо и требует подтверждения на сервере.",
            )
          }
        >
          Удалить аккаунт
        </button>
      </section>
    </div>
  );
}
