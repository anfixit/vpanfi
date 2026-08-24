/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_BASE_URL?: string;
  readonly VITE_DEMO_MODE?: string;
  readonly VITE_TELEGRAM_SUPPORT_URL?: string;
  readonly VITE_TELEGRAM_BOT_URL?: string;
  readonly VITE_MAX_SUPPORT_URL?: string;
  readonly VITE_SUPPORT_EMAIL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
