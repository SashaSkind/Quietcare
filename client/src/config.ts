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
 * On-device ML fall model (SisFall-style CNN-LSTM via TFLite). This runs
 * ALONGSIDE the threshold detector above as a more-robust confirmer — the
 * threshold path keeps working even if the model/native module is absent. The
 * model only runs when a sample exceeds `gateG` (a cheap pre-gate), so
 * inference stays off during quiet periods (battery + cost).
 *
 * It is a graceful no-op until a `.tflite` model asset is provided and injected
 * via `setFallModelSource(...)` (see client README / sensors/fallModel.ts).
 */
export const FALL_MODEL = {
  /** Master switch for the ML path. */
  enabled: true,
  /** Model input sampling rate; the 50Hz stream is resampled to this. */
  modelHz: 20,
  /** Timesteps fed to the model (~2.56s @ 20Hz, a common SisFall window). */
  windowSamples: 51,
  /** Fall probability (sigmoid output) at/above which we trigger. */
  threshold: 0.8,
  /** Only run inference when a sample's magnitude exceeds this (g). */
  gateG: 1.5,
  /** Refractory period between model inferences. */
  cooldownMs: 3_000,
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
