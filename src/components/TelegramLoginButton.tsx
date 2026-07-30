import { useEffect, useRef } from "react";

/*
 * Telegram не использует OAuth: он даёт виджет, который сам подписывает
 * данные о пользователе и отдаёт их в браузер. Подпись проверяется на
 * сервере — без этого можно было бы прислать чужой идентификатор.
 */

const WIDGET_SCRIPT = "https://telegram.org/js/telegram-widget.js?22";
const CALLBACK_NAME = "onVPaNfiTelegramAuth";

declare global {
  interface Window {
    [CALLBACK_NAME]?: (payload: Record<string, unknown>) => void;
  }
}

export function TelegramLoginButton({
  botUsername,
  onAuth,
}: {
  botUsername: string;
  onAuth: (payload: Record<string, unknown>) => void;
}) {
  const holder = useRef<HTMLDivElement>(null);
  const handler = useRef(onAuth);
  handler.current = onAuth;

  useEffect(() => {
    const node = holder.current;
    if (!node) return;

    window[CALLBACK_NAME] = (payload) => handler.current(payload);

    const script = document.createElement("script");
    script.src = WIDGET_SCRIPT;
    script.async = true;
    script.setAttribute("data-telegram-login", botUsername);
    script.setAttribute("data-size", "large");
    script.setAttribute("data-radius", "14");
    script.setAttribute("data-userpic", "false");
    script.setAttribute("data-onauth", `${CALLBACK_NAME}(user)`);
    node.appendChild(script);

    return () => {
      node.replaceChildren();
      delete window[CALLBACK_NAME];
    };
  }, [botUsername]);

  return <div className="telegram-login" ref={holder} />;
}
