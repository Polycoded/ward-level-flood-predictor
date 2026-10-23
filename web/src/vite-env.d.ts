/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_URL?: string;
  readonly VITE_USE_MOCK?: string;
  readonly VITE_SENTRY_DSN?: string;
  readonly VITE_ENABLE_CROWD_REPORTS?: string;
  readonly VITE_VAPID_PUBLIC_KEY?: string;
  readonly VITE_WHATSAPP_NUMBER?: string;
  readonly VITE_ENABLE_SW?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
