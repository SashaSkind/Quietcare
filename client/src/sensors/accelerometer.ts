import { Accelerometer } from 'expo-sensors';
import { ACCELEROMETER_HZ, FALL_DETECTION, FALL_MODEL } from '../config';
import type { AccelSample } from './detectFall';
import { detectFall } from './detectFall';
import { predictFall } from './fallModel';

const UPDATE_INTERVAL_MS = Math.round(1000 / ACCELEROMETER_HZ);
// Sliding window sized to the configured analysis window (~2.5s @ 50Hz).
const WINDOW_SIZE = Math.ceil((FALL_DETECTION.windowMs / 1000) * ACCELEROMETER_HZ);

export interface AccelerometerHandlers {
  onSample: (sample: AccelSample) => void;
  onFallDetected: () => void;
}

export class AccelerometerMonitor {
  private subscription: ReturnType<typeof Accelerometer.addListener> | null = null;
  private windowBuffer: AccelSample[] = [];
  private handlers: AccelerometerHandlers;
  // Refractory period: ignore detections for cooldownMs after one fires so a
  // single fall doesn't spam multiple triggers.
  private cooldownUntil = 0;
  // Separate refractory + in-flight guard for the (async) ML confirmer.
  private modelCooldownUntil = 0;
  private modelInFlight = false;

  constructor(handlers: AccelerometerHandlers) {
    this.handlers = handlers;
  }

  start(): void {
    Accelerometer.setUpdateInterval(UPDATE_INTERVAL_MS);
    this.subscription = Accelerometer.addListener(({ x, y, z }: { x: number; y: number; z: number }) => {
      const magnitude = Math.sqrt(x * x + y * y + z * z);
      const sample: AccelSample = { x, y, z, magnitude, ts: Date.now() };

      this.windowBuffer.push(sample);
      if (this.windowBuffer.length > WINDOW_SIZE) {
        this.windowBuffer.shift();
      }

      this.handlers.onSample(sample);

      if (sample.ts < this.cooldownUntil) return;

      if (detectFall(this.windowBuffer)) {
        this.cooldownUntil = sample.ts + FALL_DETECTION.cooldownMs;
        // Clear the buffer so the same impact samples can't re-trigger.
        this.windowBuffer = [];
        this.handlers.onFallDetected();
        return;
      }

      // ML confirmer: only when enabled, past cooldowns, not already running,
      // and a sample exceeds the cheap pre-gate (keeps inference off when idle).
      if (
        FALL_MODEL.enabled &&
        !this.modelInFlight &&
        sample.ts >= this.modelCooldownUntil &&
        sample.magnitude >= FALL_MODEL.gateG
      ) {
        this.runModel([...this.windowBuffer]);
      }
    });
  }

  /** Fire-and-forget ML inference; triggers on a high fall probability. The
   * threshold detector is unaffected if the model is absent (predictFall -> null). */
  private runModel(window: AccelSample[]): void {
    this.modelInFlight = true;
    predictFall(window)
      .then((prob) => {
        this.modelInFlight = false;
        if (prob !== null && prob >= FALL_MODEL.threshold) {
          const now = Date.now();
          this.modelCooldownUntil = now + FALL_MODEL.cooldownMs;
          this.cooldownUntil = now + FALL_DETECTION.cooldownMs;
          this.windowBuffer = [];
          this.handlers.onFallDetected();
        }
      })
      .catch(() => {
        this.modelInFlight = false;
      });
  }

  stop(): void {
    this.subscription?.remove();
    this.subscription = null;
    this.windowBuffer = [];
    this.cooldownUntil = 0;
    this.modelCooldownUntil = 0;
    this.modelInFlight = false;
  }
}
