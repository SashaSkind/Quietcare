// On-device ML fall detector (SisFall-style CNN-LSTM via TFLite).
//
// This is a more-robust *confirmer* that runs alongside the threshold detector
// in detectFall.ts. The threshold path always works; this model adds coverage
// for falls that lack a clean "impact + stillness" signature (e.g. a slow slump
// from a stroke). It is a graceful no-op until a model asset is injected via
// setFallModelSource(...), so the app builds and runs with zero ML setup.
//
// Pipeline: 50 Hz accelerometer window -> resample to FALL_MODEL.modelHz ->
// flat Float32Array of [t0x,t0y,t0z, t1x,...] of length windowSamples*3 ->
// TFLite -> single sigmoid fall probability.
//
// react-native-fast-tflite requires a custom dev build + the `.tflite` asset
// (see client README "On-device fall model"). The require is dynamic and
// guarded so this file imports cleanly under ts-jest without the native module.

import { FALL_MODEL } from '../config';
import type { AccelSample } from './detectFall';

// `require` is provided by Metro (RN) and Node (jest); declare it for tsc.
declare const require: (moduleName: string) => any;

export interface PrepareOptions {
  /** Model input rate; the source stream is resampled to this. */
  modelHz: number;
  /** Number of timesteps the model expects. */
  windowSamples: number;
}

/** Linear-interpolate the (x,y,z) reading at time `t` from a ts-ordered window. */
function interpAt(
  samples: AccelSample[],
  t: number,
): { x: number; y: number; z: number } {
  const first = samples[0];
  const last = samples[samples.length - 1];
  if (t <= first.ts) return { x: first.x, y: first.y, z: first.z };
  if (t >= last.ts) return { x: last.x, y: last.y, z: last.z };
  for (let i = 0; i < samples.length - 1; i++) {
    const a = samples[i];
    const b = samples[i + 1];
    if (t >= a.ts && t <= b.ts) {
      const span = b.ts - a.ts || 1;
      const f = (t - a.ts) / span;
      return {
        x: a.x + (b.x - a.x) * f,
        y: a.y + (b.y - a.y) * f,
        z: a.z + (b.z - a.z) * f,
      };
    }
  }
  return { x: last.x, y: last.y, z: last.z };
}

/**
 * Resample a (ts-ordered) accelerometer window to the model's rate and shape it
 * into a flat Float32Array of length windowSamples*3, row-major [x,y,z] per
 * timestep, ending at the most recent sample. Pure + deterministic so it can be
 * unit-tested without the native runtime. Returns all-zeros for an empty input.
 */
export function prepareWindow(
  samples: AccelSample[],
  opts: PrepareOptions = {
    modelHz: FALL_MODEL.modelHz,
    windowSamples: FALL_MODEL.windowSamples,
  },
): Float32Array {
  const { modelHz, windowSamples } = opts;
  const out = new Float32Array(windowSamples * 3);
  if (samples.length === 0) return out;

  const stepMs = 1000 / modelHz;
  const endTs = samples[samples.length - 1].ts;
  const startTs = endTs - (windowSamples - 1) * stepMs;
  for (let i = 0; i < windowSamples; i++) {
    const s = interpAt(samples, startTs + i * stepMs);
    out[i * 3] = s.x;
    out[i * 3 + 1] = s.y;
    out[i * 3 + 2] = s.z;
  }
  return out;
}

/** Decision helper: fall iff probability is at/above the configured threshold. */
export function decideFall(
  probability: number,
  threshold: number = FALL_MODEL.threshold,
): boolean {
  return probability >= threshold;
}

// ---- native model loading (graceful, lazy) ----
let _modelSource: unknown = null;
let _model: any = null;
let _loadAttempted = false;

/**
 * Inject the bundled TFLite model. Call once at startup AFTER adding the asset:
 *   setFallModelSource(require('../../assets/models/fall_sisfall.tflite'))
 * Until called, the ML path is a no-op (threshold detector still runs).
 */
export function setFallModelSource(source: unknown): void {
  _modelSource = source;
  _loadAttempted = false;
  _model = null;
}

export async function loadFallModel(): Promise<any | null> {
  if (_model) return _model;
  if (_loadAttempted) return _model;
  _loadAttempted = true;
  if (!_modelSource) return null;
  try {
    const { loadTensorflowModel } = require('react-native-fast-tflite');
    _model = await loadTensorflowModel(_modelSource);
  } catch {
    _model = null; // native module/asset absent -> stay on threshold path
  }
  return _model;
}

/**
 * Run the model on an accelerometer window. Returns the fall probability
 * [0..1], or null when the model is unavailable or inference fails (so callers
 * can safely fall back to the threshold detector).
 */
export async function predictFall(samples: AccelSample[]): Promise<number | null> {
  const model = await loadFallModel();
  if (!model) return null;
  try {
    const input = prepareWindow(samples);
    const outputs = await model.run([input]);
    const first = outputs?.[0];
    const prob = typeof first === 'number' ? first : first?.[0];
    return typeof prob === 'number' ? prob : null;
  } catch {
    return null;
  }
}

/** Test-only: reset module state between unit tests. */
export function _resetFallModelForTest(): void {
  _modelSource = null;
  _model = null;
  _loadAttempted = false;
}
