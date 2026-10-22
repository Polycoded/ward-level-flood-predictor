/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_URL?: string;
  readonly VITE_USE_MOCK?: string;
  readonly VITE_SENTRY_DSN?: string;
  readonly VITE_ENABLE_CROWD_REPORTS?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
