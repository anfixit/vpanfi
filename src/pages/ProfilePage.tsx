import { useEffect, useState, type FormEvent } from "react";
import { api, ApiRequestError } from "../api/client";
import { navigate, routes } from "../app/navigation";
import { useAuth } from "../auth/AuthContext";
import { useDemoNotice } from "../components/DemoNotice";
import { Icon } from "../components/Icon";
import { Mascot } from "../components/Mascot";
import { ErrorState, LoadingState } from "../components/ResourceState";
import { useAsyncResource } from "../hooks/useAsyncResource";

const SAVED_HINT_MS = 2600;
const MIN_PASSWORD_LENGTH = 8;

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
  // Те же провайдеры, что и на экране входа: привязка и вход — одно и
  // то же действие, разница лишь в том, вошёл ли человек уже.
  const providers = useAsyncResource(api.getAuthProviders);
  const { explain } = useDemoNotice();

  const [displayName, setDisplayName] = useState("");
  const [email, setEmail] = useState("");
  const [busy, setBusy] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [changingPassword, setChangingPassword] = useState(false);
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [passwordBusy, setPasswordBusy] = useState(false);
  const [passwordSaved, setPasswordSaved] = useState(false);
  const [passwordError, setPasswordError] = useState<string | null>(null);

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

  const changePassword = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (passwordBusy) return;

    setPasswordBusy(true);
    setPasswordError(null);
    setPasswordSaved(false);

    try {
      await api.changePassword({ currentPassword, newPassword });
      setCurrentPassword("");
      setNewPassword("");
      setPasswordSaved(true);
      setChangingPassword(false);
      window.setTimeout(() => setPasswordSaved(false), SAVED_HINT_MS);
    } catch (reason: unknown) {
      setPasswordError(
        reason instanceof ApiRequestError
          ? reason.message
          : "Не удалось сменить пароль",
      );
    } finally {
      setPasswordBusy(false);
    }
  };

  const deleteAccount = async () => {
    const password = window.prompt(
      "Удаление необратимо: данные аккаунта будут стёрты, а войти станет " +
        "нельзя. Подписка в панели сохранится. Введите пароль, чтобы " +
        "подтвердить.",
    );
    if (!password) return;

    try {
      await api.deleteAccount(password);
      await logout();
      navigate(routes.landing);
    } catch (reason: unknown) {
      explain(
        reason instanceof ApiRequestError
          ? reason.message
          : "Не удалось удалить аккаунт",
      );
    }
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

  const configured = providers.data ?? [];
  const linkedAccounts = [
    {
      key: "telegram",
      name: "Telegram",
      note: "Вход одним нажатием через знакомый аккаунт.",
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
  ].map((account) => ({
    ...account,
    available: configured.some((item) => item.provider === account.key),
    authorizationUrl:
      configured.find((item) => item.provider === account.key)
        ?.authorizationUrl ?? null,
  }));

  const toggleProvider = async (account: (typeof linkedAccounts)[number]) => {
    if (!account.available) {
      explain(
        `Вход через ${account.name} появится, когда будут добавлены ключи приложения.`,
      );
      return;
    }

    if (!account.connected) {
      if (account.authorizationUrl) {
        window.location.assign(account.authorizationUrl);
      } else {
        explain(
          `Вход через ${account.name} подключается на экране входа: выйдите и нажмите там его кнопку.`,
        );
      }
      return;
    }

    try {
      await api.unlinkProvider(account.key);
      applyProfile(await api.getProfile());
    } catch (reason: unknown) {
      explain(
        reason instanceof ApiRequestError
          ? reason.message
          : `Не удалось отвязать ${account.name}`,
      );
    }
  };

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
                {passwordSaved
                  ? "Пароль изменён, остальные сеансы завершены"
                  : profile.passwordEnabled
                    ? "Пароль установлен"
                    : "Пароль ещё не создан"}
              </p>
            </div>
            <button
              className="button button-secondary"
              type="button"
              aria-expanded={changingPassword}
              onClick={() => {
                setChangingPassword((open) => !open);
                setPasswordError(null);
              }}
            >
              {changingPassword ? "Отмена" : "Изменить"}
            </button>
          </div>
          {changingPassword && (
            <form className="password-form" onSubmit={changePassword}>
              <label>
                Текущий пароль
                <input
                  type="password"
                  value={currentPassword}
                  onChange={(event) => setCurrentPassword(event.target.value)}
                  autoComplete="current-password"
                  required
                />
              </label>
              <label>
                Новый пароль
                <input
                  type="password"
                  value={newPassword}
                  onChange={(event) => setNewPassword(event.target.value)}
                  autoComplete="new-password"
                  minLength={MIN_PASSWORD_LENGTH}
                  required
                />
              </label>
              <p className="muted">
                Не короче {MIN_PASSWORD_LENGTH} символов. Вход на других
                устройствах после смены придётся выполнить заново.
              </p>
              {passwordError && (
                <div className="auth-error" role="alert">
                  {passwordError}
                </div>
              )}
              <button
                className="button button-primary"
                type="submit"
                disabled={
                  passwordBusy ||
                  !currentPassword ||
                  newPassword.length < MIN_PASSWORD_LENGTH
                }
              >
                {passwordBusy ? "Меняем…" : "Сменить пароль"}
              </button>
            </form>
          )}
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
                onClick={() => toggleProvider(account)}
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
        <button className="button button-ghost danger-action" type="button" onClick={deleteAccount}>
          Удалить аккаунт
        </button>
      </section>
    </div>
  );
}
