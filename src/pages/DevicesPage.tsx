import { useMemo, useState } from "react";
import { api } from "../api/client";
import { navigate, routes } from "../app/navigation";
import { useDemoNotice } from "../components/DemoNotice";
import { Icon, type IconName } from "../components/Icon";
import { Mascot } from "../components/Mascot";
import { EmptyState, ErrorState, LoadingState } from "../components/ResourceState";
import { EXTRA_DEVICE_PRICE_RUB } from "../data";
import { useAsyncResource } from "../hooks/useAsyncResource";
import { formatDate, formatDateTime } from "../utils/format";

const FALLBACK_DEVICE_LIMIT = 3;
const FULL_PERCENT = 100;

function platformIcon(platform: string): IconName {
  if (platform.includes("TV")) return "tv";
  if (platform === "macOS") return "laptop";
  if (platform === "Windows") return "monitor";
  if (platform === "Linux") return "terminal";
  return "smartphone";
}

export function DevicesPage() {
  const devicesResource = useAsyncResource(api.getDevices);
  const subscriptionLink = useAsyncResource(api.getSubscription);
  const { explain } = useDemoNotice();
  const [removedIds, setRemovedIds] = useState<string[]>([]);
  const [busyId, setBusyId] = useState<string | null>(null);
  const devices = useMemo(
    () => (devicesResource.data ?? []).filter((device) => !removedIds.includes(device.id)),
    [devicesResource.data, removedIds],
  );

  const unlink = async (deviceId: string, deviceName: string) => {
    const confirmed = window.confirm(
      `Отвязать устройство ${deviceName}? Подключение на нём перестанет работать.`,
    );
    if (!confirmed) return;

    setBusyId(deviceId);
    try {
      await api.unlinkDevice(deviceId);
      setRemovedIds((current) => [...current, deviceId]);
    } finally {
      setBusyId(null);
    }
  };

  if (devicesResource.loading && !devicesResource.data) {
    return <LoadingState label="Анфиса считает устройства…" />;
  }
  if (devicesResource.error || !devicesResource.data) {
    return (
      <ErrorState
        message={devicesResource.error ?? "Устройства не найдены"}
        onRetry={devicesResource.reload}
      />
    );
  }

  // Лимит задаётся в панели и у разных тарифов разный: захардкоженная
  // тройка показывала бы «10 из 3» тому, у кого мест десять.
  const deviceLimit =
    subscriptionLink.data?.subscription?.devicesLimit ?? FALLBACK_DEVICE_LIMIT;
  const usedPercent = Math.min(
    FULL_PERCENT,
    (devices.length / Math.max(deviceLimit, 1)) * FULL_PERCENT,
  );
  const overLimit = devices.length > deviceLimit;

  return (
    <div className="cabinet-page">
      <section className="page-intro cabinet-card">
        <div>
          <span className="cabinet-kicker">
            {deviceLimit} мест включено в тариф
          </span>
          <h2>Ваши устройства</h2>
          <p className="muted">
            Отвязывать устройство нужно только тогда, когда Вы больше не планируете им
            пользоваться.
          </p>
        </div>
        <Mascot variant="laptop" className="page-intro-mascot" decorative />
      </section>

      <section className="cabinet-card device-summary">
        <div>
          <span className="muted">Используется</span>
          <strong>
            {devices.length} из {deviceLimit}
          </strong>
        </div>
        <div
          className="device-progress"
          role="progressbar"
          aria-valuemin={0}
          aria-valuemax={deviceLimit}
          aria-valuenow={devices.length}
          aria-label="Занятые места для устройств"
        >
          <span style={{ width: `${usedPercent}%` }} />
        </div>
        {overLimit && (
          <p className="muted device-over-limit">
            Подключено больше устройств, чем мест в тарифе. Лишние могут
            перестать работать — отвяжите те, которыми не пользуетесь.
          </p>
        )}
        <button
          className="button button-secondary"
          type="button"
          onClick={() =>
            explain(
              `Дополнительное место за ${EXTRA_DEVICE_PRICE_RUB} ₽ появится вместе с платёжным провайдером.`,
            )
          }
        >
          Добавить ещё одно за {EXTRA_DEVICE_PRICE_RUB} ₽
        </button>
      </section>

      {devices.length > 0 ? (
        <section className="device-list">
          {devices.map((device) => (
            <article className="cabinet-card device-row" key={device.id}>
              <div className="device-platform-icon">
                <Icon name={platformIcon(device.platform)} />
              </div>
              <div className="device-main">
                <div className="device-title-row">
                  <h3>{device.name}</h3>
                  {device.current && <span className="status-pill">Это устройство</span>}
                </div>
                <p className="muted">
                  {device.platform} · добавлено {formatDate(device.createdAt)}
                </p>
                <small>
                  Последняя активность: {formatDateTime(device.lastSeenAt)}
                </small>
              </div>
              <button
                className="button button-ghost danger-action"
                type="button"
                disabled={busyId === device.id}
                onClick={() => unlink(device.id, device.name)}
              >
                {busyId === device.id ? "Отвязываем…" : "Отвязать"}
              </button>
            </article>
          ))}
        </section>
      ) : (
        <section className="cabinet-card">
          <EmptyState
            mascot="phone"
            title="Пока нет подключённых устройств"
            description="Начните с телефона: Анфиса покажет приложение и один следующий шаг."
          >
            <button
              className="button button-primary"
              type="button"
              onClick={() => navigate(routes.connect)}
            >
              Подключить устройство
            </button>
          </EmptyState>
        </section>
      )}
    </div>
  );
}
