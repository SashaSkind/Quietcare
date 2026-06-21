import {
  isMotion,
  isExpectedActive,
  shouldFireInactivity,
  InactivityTracker,
} from './inactivity';
import type { AccelSample } from './detectFall';

function sample(magnitude: number, ts = Date.now()): AccelSample {
  return { x: 0, y: 0, z: magnitude, magnitude, ts };
}

describe('isMotion', () => {
  it('flags deviation from rest as motion', () => {
    expect(isMotion(sample(1.0), 0.08)).toBe(false);
    expect(isMotion(sample(1.3), 0.08)).toBe(true);
    expect(isMotion(sample(0.85), 0.08)).toBe(true);
  });
});

describe('isExpectedActive', () => {
  it('handles a normal daytime window', () => {
    expect(isExpectedActive(10, 9, 21)).toBe(true);
    expect(isExpectedActive(3, 9, 21)).toBe(false);
    expect(isExpectedActive(21, 9, 21)).toBe(false);
  });
  it('handles a wrapping window', () => {
    expect(isExpectedActive(23, 22, 6)).toBe(true);
    expect(isExpectedActive(2, 22, 6)).toBe(true);
    expect(isExpectedActive(12, 22, 6)).toBe(false);
  });
});

describe('shouldFireInactivity', () => {
  const HOUR = 60 * 60 * 1000;
  it('fires after no-motion window during active hours', () => {
    expect(
      shouldFireInactivity({
        now: 10 * HOUR,
        lastMotionTs: 10 * HOUR - 2 * HOUR,
        hour: 10,
        cooldownUntil: 0,
        noMotionMs: HOUR,
      }),
    ).toBe(true);
  });
  it('does not fire within cooldown', () => {
    expect(
      shouldFireInactivity({
        now: 10 * HOUR,
        lastMotionTs: 0,
        hour: 10,
        cooldownUntil: 11 * HOUR,
        noMotionMs: HOUR,
      }),
    ).toBe(false);
  });
  it('does not fire outside active hours', () => {
    expect(
      shouldFireInactivity({
        now: 10 * HOUR,
        lastMotionTs: 0,
        hour: 3,
        cooldownUntil: 0,
        noMotionMs: HOUR,
      }),
    ).toBe(false);
  });
  it('does not fire when motion was recent', () => {
    expect(
      shouldFireInactivity({
        now: 10 * HOUR,
        lastMotionTs: 10 * HOUR - 60_000,
        hour: 10,
        cooldownUntil: 0,
        noMotionMs: HOUR,
      }),
    ).toBe(false);
  });
});

describe('InactivityTracker', () => {
  it('observing motion resets the timer', () => {
    const t = new InactivityTracker();
    const now = 12 * 60 * 60 * 1000;
    t.observe(sample(1.5, now)); // motion
    // Immediately checking should not fire (motion just happened).
    expect(t.check(now + 1000, 12)).toBe(false);
  });
});
