import { INACTIVITY } from '../config';
import type { AccelSample } from './detectFall';

/** A sample counts as "motion" when |a| deviates from rest (~1g) beyond the band. */
export function isMotion(sample: AccelSample, motionBandG: number = INACTIVITY.motionBandG): boolean {
  return Math.abs(sample.magnitude - 1) > motionBandG;
}

/** Local hour is within the expected-active window [start, end). Handles
 * windows that don't wrap midnight (the common case). */
export function isExpectedActive(
  hour: number,
  start: number = INACTIVITY.expectedActiveStartHour,
  end: number = INACTIVITY.expectedActiveEndHour,
): boolean {
  if (start <= end) return hour >= start && hour < end;
  // Wrapping window (e.g. 22->6): active if after start OR before end.
  return hour >= start || hour < end;
}

/**
 * Pure inactivity decision: given the last time real motion was observed and
 * "now", decide whether to fire an inactivity trigger. Kept pure so it is unit
 * testable without sensors or timers.
 */
export function shouldFireInactivity(params: {
  now: number;
  lastMotionTs: number;
  hour: number;
  cooldownUntil: number;
  noMotionMs?: number;
}): boolean {
  const { now, lastMotionTs, hour, cooldownUntil } = params;
  const noMotionMs = params.noMotionMs ?? INACTIVITY.noMotionMs;
  if (now < cooldownUntil) return false;
  if (!isExpectedActive(hour)) return false;
  return now - lastMotionTs >= noMotionMs;
}

/**
 * Stateful tracker driven by accelerometer samples + periodic checks. Designed
 * to be polled (e.g. once per minute) via `check(now)`; call `observe(sample)`
 * on each accelerometer sample.
 */
export class InactivityTracker {
  private lastMotionTs = Date.now();
  private cooldownUntil = 0;

  observe(sample: AccelSample): void {
    if (isMotion(sample)) this.lastMotionTs = sample.ts;
  }

  /** Returns true exactly once when inactivity is first detected (then arms the
   * cooldown). `now` and `hour` are injectable for testing. */
  check(now = Date.now(), hour = new Date().getHours()): boolean {
    if (
      shouldFireInactivity({
        now,
        lastMotionTs: this.lastMotionTs,
        hour,
        cooldownUntil: this.cooldownUntil,
      })
    ) {
      this.cooldownUntil = now + INACTIVITY.cooldownMs;
      this.lastMotionTs = now; // reset so it doesn't immediately re-fire
      return true;
    }
    return false;
  }

  reset(): void {
    this.lastMotionTs = Date.now();
    this.cooldownUntil = 0;
  }
}
