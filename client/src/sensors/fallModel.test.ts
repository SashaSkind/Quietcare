import { decideFall, predictFall, prepareWindow, _resetFallModelForTest } from './fallModel';
import type { AccelSample } from './detectFall';

const DT = 20; // 50 Hz source sampling

/** Build a 50Hz window from (x,y,z) triples. */
function windowOf(triples: Array<[number, number, number]>, startTs = 0): AccelSample[] {
  return triples.map(([x, y, z], i) => ({
    x,
    y,
    z,
    magnitude: Math.sqrt(x * x + y * y + z * z),
    ts: startTs + i * DT,
  }));
}

describe('prepareWindow', () => {
  it('returns all-zeros of the right length for an empty window', () => {
    const out = prepareWindow([], { modelHz: 20, windowSamples: 4 });
    expect(out).toHaveLength(12);
    expect(Array.from(out)).toEqual([0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]);
  });

  it('produces windowSamples*3 values ending at the latest sample', () => {
    // Constant signal -> every resampled triple equals it.
    const samples = windowOf(Array.from({ length: 200 }, () => [0.1, 0.2, 0.9]));
    const out = prepareWindow(samples, { modelHz: 20, windowSamples: 51 });
    expect(out).toHaveLength(153);
    // Last triple is the most recent reading.
    const n = out.length;
    expect(out[n - 3]).toBeCloseTo(0.1, 5);
    expect(out[n - 2]).toBeCloseTo(0.2, 5);
    expect(out[n - 1]).toBeCloseTo(0.9, 5);
  });

  it('linearly interpolates between source samples when downsampling', () => {
    // A ramp on x from 0..1 over the window; downsampling should interpolate.
    const samples = windowOf(
      Array.from({ length: 101 }, (_, i) => [i / 100, 0, 1]),
    );
    const out = prepareWindow(samples, { modelHz: 20, windowSamples: 11 });
    // First resampled x is near the value 1.25s before the end (ts span = 2000ms).
    // End ts = 2000ms (x=1). Start ts = 2000 - 10*50 = 1500ms -> x ~= 0.75.
    expect(out[0]).toBeCloseTo(0.75, 2);
    // Last is the end (x = 1).
    expect(out[out.length - 3]).toBeCloseTo(1, 5);
  });

  it('clamps to the earliest sample when the window predates available data', () => {
    const samples = windowOf([[5, 6, 7], [5, 6, 7]]); // only 40ms of data
    const out = prepareWindow(samples, { modelHz: 20, windowSamples: 51 });
    // The far-back timesteps clamp to the earliest reading.
    expect(out[0]).toBeCloseTo(5, 5);
    expect(out[1]).toBeCloseTo(6, 5);
    expect(out[2]).toBeCloseTo(7, 5);
  });
});

describe('decideFall', () => {
  it('triggers at/above threshold and not below', () => {
    expect(decideFall(0.9, 0.8)).toBe(true);
    expect(decideFall(0.8, 0.8)).toBe(true);
    expect(decideFall(0.79, 0.8)).toBe(false);
  });
});

describe('predictFall', () => {
  beforeEach(() => _resetFallModelForTest());

  it('returns null when no model source is injected (graceful no-op)', async () => {
    const samples = windowOf(Array.from({ length: 60 }, () => [0, 0, 1]));
    await expect(predictFall(samples)).resolves.toBeNull();
  });
});
