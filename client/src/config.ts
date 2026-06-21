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

/**
 * Fall-detection thresholds (easily tunable). Accelerometer magnitude is in g
 * (~1g at rest including gravity). The detector looks for an impact spike
 * followed by a stillness window inside a sliding buffer.
 */
export const FALL_DETECTION = {
  /** Sliding analysis window length. */
  windowMs: 2_500,
  /** Magnitude (g) that counts as an impact spike. Lower = more sensitive. */
  impactThresholdG: 2.5,
  /** Max deviation from 1g for a sample to count as "still". */
  stillnessBandG: 0.18,
  /** Continuous stillness required after the impact to confirm a fall. */
  stillnessMs: 1_200,
  /** Ignore further detections for this long after one fires (refractory). */
  cooldownMs: 10_000,
} as const;

/**
 * Always-on rolling audio buffer. The mic continuously records short segments;
 * on a trigger we send the most recent buffered segment (the seconds BEFORE the
 * event) instead of recording silence after the fact.
 */
export const AUDIO_BUFFER = {
  /** Length of each rolling segment === how many pre-trigger seconds we keep. */
  segmentMs: 4_000,
  /** How many completed segments to retain in the ring (>=1). */
  ringSize: 2,
  /** Master switch; disable to fall back to the bundled sample clip. */
  enabled: true,
} as const;
