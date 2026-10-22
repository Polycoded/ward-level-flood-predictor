type SentryModule = typeof import('@sentry/react');

const DSN = import.meta.env.VITE_SENTRY_DSN;
let sentry: SentryModule | null = null;

/**
 * Error monitoring is opt-in: Sentry is only downloaded and initialised when
 * VITE_SENTRY_DSN is set at build time, so the default bundle stays small.
 */
export async function initMonitoring(): Promise<void> {
  if (!DSN) return;
  const Sentry = await import('@sentry/react');
  Sentry.init({
    dsn: DSN,
    environment: import.meta.env.MODE,
    integrations: [Sentry.browserTracingIntegration()],
    tracesSampleRate: 0.2,
    sendDefaultPii: false,
  });
  sentry = Sentry;
}

export function reportError(error: unknown, context?: Record<string, unknown>): void {
  console.error(error);
  sentry?.captureException(error, { extra: context });
}
