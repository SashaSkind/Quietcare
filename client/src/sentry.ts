import * as Sentry from '@sentry/react-native';
import { SENTRY_DSN, ELDER_ID } from './config';

let initialized = false;

export function initSentry(): void {
  if (initialized) return;
  if (!SENTRY_DSN) {
    // No DSN configured (e.g. local dev without .env). Skip silently.
    return;
  }
  Sentry.init({
    dsn: SENTRY_DSN,
    tracesSampleRate: 1.0,
    enableNative: true,
    // Keep payloads small: never attach raw request/response bodies (audio is large).
    maxBreadcrumbs: 100,
  });
  Sentry.setTag('elder_id', ELDER_ID);
  initialized = true;
}

// Lightweight breadcrumb helper used by the WebSocket + audio layers.
export function breadcrumb(
  category: string,
  message: string,
  data?: Record<string, unknown>,
): void {
  Sentry.addBreadcrumb({ category, message, level: 'info', data });
}

export function captureException(error: unknown, context?: Record<string, unknown>): void {
  Sentry.captureException(error, context ? { extra: context } : undefined);
}

export { Sentry };
