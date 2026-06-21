// Stubbed fall detector. A real on-device TFLite model will replace this later.
// The Simulate-Fall button intentionally BYPASSES this stub.

export interface AccelSample {
  x: number;
  y: number;
  z: number;
  /** Signal magnitude sqrt(x^2 + y^2 + z^2). */
  magnitude: number;
  ts: number;
}

// Always returns false for now.
export function detectFall(_window: AccelSample[]): boolean {
  return false;
}
