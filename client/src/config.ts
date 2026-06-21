// Centralized configuration sourced from EXPO_PUBLIC_* env vars.
// These are injected at build time by Expo. No secrets belong here.

export const WS_URL: string =
  process.env.EXPO_PUBLIC_WS_URL ?? 'ws://localhost:8080/ws';

// REST base URL of the Quietcare backend (caretaker dashboard + demo incident
// reporting). On a physical device this must be the machine's LAN IP, e.g.
// http://10.0.0.218:8000 — localhost only works in a simulator/emulator.
export const API_URL: string =
  process.env.EXPO_PUBLIC_API_URL ?? 'http://localhost:8000';

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
 * Inactivity / no-motion detection. Absence of expected motion is a trigger we
 * get almost for free from the accelerometer, and it catches silent emergencies
 * (e.g. a stroke in bed) that a fall model misses. A sample counts as "motion"
 * when |a| deviates from rest (~1g) by more than `motionBandG`. If no motion is
 * seen for `noMotionMs` AND the local hour is within the expected-active window,
 * we fire an `inactivity` trigger.
 */
export const INACTIVITY = {
  /** Master switch. */
  enabled: true,
  /** Deviation from 1g that counts as real movement. */
  motionBandG: 0.08,
  /** No-motion duration that fires a check (default 60 min). */
  noMotionMs: 60 * 60 * 1000,
  /** Only fire during expected-active local hours [startHour, endHour). */
  expectedActiveStartHour: 9,
  expectedActiveEndHour: 21,
  /** Refractory period between inactivity triggers. */
  cooldownMs: 60 * 60 * 1000,
} as const;

/**
 * Geofence / wandering detection (for dementia). When enabled and a home anchor
 * is set, leaving the safe radius fires a `geofence` trigger with the location;
 * the backend raises severity at night. Uses expo-location when available and is
 * a graceful no-op otherwise.
 */
export const GEOFENCE = {
  /** Master switch. */
  enabled: false,
  /** Home anchor; null until set by the caretaker during setup. */
  home: null as { lat: number; lng: number } | null,
  /** Safe radius in meters around home. */
  radiusM: 150,
  /** How often to poll location. */
  pollMs: 60 * 1000,
  /** Refractory period between geofence triggers. */
  cooldownMs: 10 * 60 * 1000,
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
