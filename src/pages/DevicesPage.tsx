import { useMemo, useState } from "react";
import { api } from "../api/client";
import { Mascot } from "../components/Mascot";
import { ErrorState, LoadingState } from "../components/ResourceState";
import { useAsyncResource } from "../hooks/useAsyncResource";

export function DevicesPage() {
  const devicesResource = useAsyncResource(api.getDevices);
  const [removedIds, setRemovedIds] = useState<string[]>([]);
  const [busyId, setBusyId] = useState<string | null>(null);
  const devices = useMemo(
    () => (devicesResource.data ?? []).filter((device) => !removedIds.includes(device.id)),
    [devicesResource.data, removedIds],
  );

  const unlink = async (deviceId: string, deviceName: string) => {
    const confirmed = window.confirm(`Отвязать устройство ${deviceName}? Подключение на нём перестанет работать.`);
    if (!confirmed) return;

    setBusyId(deviceId);
    try {
      await api.unlinkDevice(deviceId);
      setRemovedIds((current) => [...current, deviceId]);
    } finally {
      setBusyId(null);
    }
  };

  if (devicesResource.loading && !devicesResource.data) return <LoadingState label="Анфиса считает устройства…" />;
  if (devicesResource.error || !devicesResource.data) {
    return <ErrorState message={devicesResource.error ?? "Устройства не найдены"} onRetry={devicesResource.reload} />;
  }

  return (
    <div className="cabinet-page">
      <section className="page-intro cabinet-card">
        <div>
          <span className="cabinet-kicker">3 места включены в тариф</span>
          <h2>Ваши устройства</h2>
          <p className="muted">Отвязывать устройство нужно только тогда, когда Вы больше не планируете им пользоваться.</p>
        </div>
        <Mascot variant="working" className="page-intro-mascot" decorative />
      </section>

      <section className="cabinet-card device-summary">
        <div><span className="muted">Используется</span><strong>{devices.length} из 3</strong></div>
        <div className="device-progress"><span style={{ width: `${Math.min(100, (devices.length / 3) * 100)}%` }} /></div>
        <button className="button button-secondary" type="button">Добавить ещё одно за 100 ₽</button>
      </section>

      <section className="device-list">
        {devices.map((device) => (
          <article className="cabinet-card device-row" key={device.id}>
            <div className="device-platform-icon" aria-hidden="true">{device.platform.includes("Android") ? "●" : device.platform === "macOS" ? "⌘" : "▣"}</div>
            <div className="device-main">
              <div className="device-title-row">
                <h3>{device.name}</h3>
                {device.current && <span className="status-pill">Это устройство</span>}
              </div>
              <p className="muted">{device.platform} · добавлено {device.createdAt}</p>
              <small>Последняя активность: {device.lastSeenAt}</small>
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

      {devices.length === 0 && (
        <section className="cabinet-card empty-state">
          <Mascot variant="error" className="card-mascot" decorative />
          <h3>Пока нет подключённых устройств</h3>
          <p className="muted">Перейдите в раздел подключения, и Анфиса всё покажет.</p>
        </section>
      )}
    </div>
  );
}
