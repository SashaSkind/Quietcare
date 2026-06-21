// On-device fall detector (threshold algorithm).
//
// A fall looks like: a brief high-g IMPACT spike (the body hitting the ground)
// immediately followed by a STILLNESS window (the person lying motionless).
// We scan a sliding accelerometer-magnitude buffer for that pattern. A future
// TFLite model can replace `detectFall` while keeping the same signature.
//
// The Simulate-Fall button intentionally BYPASSES this detector.

import { FALL_DETECTION } from '../config';

export interface AccelSample {
  x: number;
  y: number;
  z: number;
  /** Signal magnitude sqrt(x^2 + y^2 + z^2), in g. */
  magnitude: number;
  ts: number;
}

export interface FallThresholds {
  impactThresholdG: number;
  stillnessBandG: number;
  stillnessMs: number;
}

/**
 * Returns true when `window` contains an impact spike followed by a sustained
 * stillness period. `window` is expected to be ordered oldest -> newest.
 */
export function detectFall(
  window: AccelSample[],
  thresholds: FallThresholds = FALL_DETECTION,
): boolean {
  const { impactThresholdG, stillnessBandG, stillnessMs } = thresholds;
  if (window.length < 3) return false;

  // 1) Find the strongest impact in the window.
  let impactIndex = -1;
  let peak = 0;
  for (let i = 0; i < window.length; i++) {
    if (window[i].magnitude > peak) {
      peak = window[i].magnitude;
      impactIndex = i;
    }
  }
  if (peak < impactThresholdG) return false;

  // 2) Require a continuous stillness window AFTER the impact: enough samples
  //    near 1g spanning at least `stillnessMs`.
  let stillStartTs: number | null = null;
  for (let i = impactIndex + 1; i < window.length; i++) {
    const isStill = Math.abs(window[i].magnitude - 1) <= stillnessBandG;
    if (isStill) {
      if (stillStartTs === null) stillStartTs = window[i].ts;
      const stillSpan = window[i].ts - stillStartTs;
      if (stillSpan >= stillnessMs) return true;
    } else {
      // Movement after the impact breaks the stillness (e.g. they got back up).
      stillStartTs = null;
    }
  }

  return false;
}
