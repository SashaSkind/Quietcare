import { detectFall } from './detectFall';
import type { AccelSample, FallThresholds } from './detectFall';

const THRESHOLDS: FallThresholds = {
  impactThresholdG: 2.5,
  stillnessBandG: 0.18,
  stillnessMs: 1_200,
};

const DT = 20; // 50 Hz sampling

/** Build a window from a list of magnitudes, timestamped at 50 Hz. */
function windowOf(magnitudes: number[], startTs = 0): AccelSample[] {
  return magnitudes.map((magnitude, i) => ({
    x: 0,
    y: 0,
    z: magnitude,
    magnitude,
    ts: startTs + i * DT,
  }));
}

/** n samples at ~1g (resting), with small deterministic jitter. */
function resting(n: number): number[] {
  return Array.from({ length: n }, (_, i) => 1 + (i % 2 === 0 ? 0.02 : -0.02));
}

describe('detectFall', () => {
  it('returns false for too-few samples', () => {
    expect(detectFall(windowOf([1, 5]), THRESHOLDS)).toBe(false);
  });

  it('returns false for normal resting motion (no impact)', () => {
    expect(detectFall(windowOf(resting(125)), THRESHOLDS)).toBe(false);
  });

  it('returns false for an impact with NO following stillness window', () => {
    // Spike, then immediately more samples but window ends before stillness.
    const mags = [...resting(10), 3.2, ...resting(3)]; // only ~60ms still after
    expect(detectFall(windowOf(mags), THRESHOLDS)).toBe(false);
  });

  it('returns true for an impact followed by sustained stillness', () => {
    // Spike at index 10, then ~1.5s of stillness (75 samples * 20ms).
    const mags = [...resting(10), 3.2, ...resting(75)];
    expect(detectFall(windowOf(mags), THRESHOLDS)).toBe(true);
  });

  it('returns false when the person keeps moving after the impact', () => {
    // Spike then oscillating movement (got back up) — never sustains stillness.
    const moving = Array.from({ length: 80 }, (_, i) =>
      i % 2 === 0 ? 1.6 : 0.4,
    );
    const mags = [...resting(10), 3.2, ...moving];
    expect(detectFall(windowOf(mags), THRESHOLDS)).toBe(false);
  });

  it('resets the stillness timer if movement interrupts before stillnessMs', () => {
    // Impact, brief stillness (<1.2s), a jolt, then long stillness -> true.
    const mags = [
      ...resting(5),
      3.5,
      ...resting(30), // 600ms still (not enough)
      2.0, // movement breaks it
      ...resting(75), // 1.5s still -> confirms
    ];
    expect(detectFall(windowOf(mags), THRESHOLDS)).toBe(true);
  });

  it('does not count stillness that occurred BEFORE the impact', () => {
    // Long stillness first, then a spike at the very end (no time after).
    const mags = [...resting(100), 3.2];
    expect(detectFall(windowOf(mags), THRESHOLDS)).toBe(false);
  });

  it('respects a lower impact threshold (more sensitive)', () => {
    const sensitive: FallThresholds = { ...THRESHOLDS, impactThresholdG: 1.8 };
    const mags = [...resting(10), 2.0, ...resting(75)];
    expect(detectFall(windowOf(mags), THRESHOLDS)).toBe(false);
    expect(detectFall(windowOf(mags), sensitive)).toBe(true);
  });

  it('uses the strongest impact, ignoring earlier weaker spikes', () => {
    // A weak spike, then the real impact, then stillness.
    const mags = [...resting(5), 1.5, ...resting(5), 4.0, ...resting(75)];
    expect(detectFall(windowOf(mags), THRESHOLDS)).toBe(true);
  });
});
