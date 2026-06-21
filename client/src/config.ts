// Centralized configuration sourced from EXPO_PUBLIC_* env vars.
// These are injected at build time by Expo. No secrets belong here.

export const WS_URL: string =
  process.env.EXPO_PUBLIC_WS_URL ?? 'ws://localhost:8080/ws';

export const SENTRY_DSN: string = process.env.EXPO_PUBLIC_SENTRY_DSN ?? '';

export const ELDER_ID: string =
  process.env.EXPO_PUBLIC_ELDER_ID ?? 'margaret-01';

// Tunables.
export const HEARTBEAT_INTERVAL_MS = 30_000;
export const RECONNECT_BASE_DELAY_MS = 1_000;
export const RECONNECT_MAX_DELAY_MS = 30_000;
export const ACCELEROMETER_HZ = 50;
