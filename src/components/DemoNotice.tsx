import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { api } from "../api/client";
import { Icon } from "./Icon";

/*
 * Часть действий нельзя выполнить, пока не подключены платёжный
 * провайдер, панель Remnawave и почта. Вместо кнопок, которые молча
 * ничего не делают, и вместо поддельного «успеха» интерфейс честно
 * объясняет, чего именно не хватает.
 */

type DemoNoticeValue = {
  isDemoMode: boolean;
  message: string | null;
  explain: (message: string) => void;
  dismiss: () => void;
};

const DemoNoticeContext = createContext<DemoNoticeValue | null>(null);

export function DemoNoticeProvider({ children }: { children: ReactNode }) {
  const [message, setMessage] = useState<string | null>(null);

  const explain = useCallback((next: string) => setMessage(next), []);
  const dismiss = useCallback(() => setMessage(null), []);

  const value = useMemo<DemoNoticeValue>(
    () => ({ isDemoMode: api.isDemoMode, message, explain, dismiss }),
    [message, explain, dismiss],
  );

  return (
    <DemoNoticeContext.Provider value={value}>
      {children}
      <div className="demo-notice-region" role="status" aria-live="polite">
        {message && (
          <div className="demo-notice">
            <Icon name="sparkle" className="demo-notice-icon" />
            <p>{message}</p>
            <button type="button" onClick={dismiss} aria-label="Скрыть сообщение">
              Понятно
            </button>
          </div>
        )}
      </div>
    </DemoNoticeContext.Provider>
  );
}

export function useDemoNotice(): DemoNoticeValue {
  const value = useContext(DemoNoticeContext);
  if (!value) {
    throw new Error("useDemoNotice must be used inside DemoNoticeProvider");
  }
  return value;
}
