import { Accelerometer } from 'expo-sensors';
import { ACCELEROMETER_HZ } from '../config';
import type { AccelSample } from './detectFall';
import { detectFall } from './detectFall';

const UPDATE_INTERVAL_MS = Math.round(1000 / ACCELEROMETER_HZ);
const WINDOW_SIZE = ACCELEROMETER_HZ * 2; // ~2s rolling window

export interface AccelerometerHandlers {
  onSample: (sample: AccelSample) => void;
  onFallDetected: () => void;
}

export class AccelerometerMonitor {
  private subscription: ReturnType<typeof Accelerometer.addListener> | null = null;
  private windowBuffer: AccelSample[] = [];
  private handlers: AccelerometerHandlers;

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

      // Stub always returns false; wired up so the real model can drop in later.
      if (detectFall(this.windowBuffer)) {
        this.handlers.onFallDetected();
      }
    });
  }

  stop(): void {
    this.subscription?.remove();
    this.subscription = null;
    this.windowBuffer = [];
  }
}
