import { useEffect, useRef } from 'react';
import { Accelerometer } from 'expo-sensors';
import { ACCELEROMETER_HZ, FALL_DETECTION } from '../config';
import { detectFall, type AccelSample } from '../sensors/detectFall';

// Lightweight real fall detector for the Expo Go demo. Subscribes to the live
// accelerometer (expo-sensors) and runs the SAME threshold detector the real
// client uses (impact spike + stillness). It deliberately avoids the TFLite ML
// confirmer (react-native-fast-tflite is a native module unavailable in Expo
// Go), so this runs unchanged on a plain phone via the Expo Go QR.

const UPDATE_INTERVAL_MS = Math.round(1000 / ACCELEROMETER_HZ);
const WINDOW_SIZE = Math.ceil((FALL_DETECTION.windowMs / 1000) * ACCELEROMETER_HZ);

export interface FallSensorOptions {
  /** When false, the sensor pauses (e.g. while already handling a check-in). */
  enabled: boolean;
  onFall: () => void;
  onMagnitude?: (g: number) => void;
}

export function useFallSensor({ enabled, onFall, onMagnitude }: FallSensorOptions): void {
  // Keep latest callbacks in refs so we don't resubscribe on every render.
  const onFallRef = useRef(onFall);
  const onMagRef = useRef(onMagnitude);
  onFallRef.current = onFall;
  onMagRef.current = onMagnitude;

  useEffect(() => {
    if (!enabled) return;
    let buffer: AccelSample[] = [];
    let cooldownUntil = 0;

    // The accelerometer is unavailable on some platforms (e.g. web); fail soft
    // so the "Simulate Fall" control still works there.
    let sub: { remove: () => void } | null = null;
    try {
      Accelerometer.setUpdateInterval(UPDATE_INTERVAL_MS);
      sub = Accelerometer.addListener(({ x, y, z }) => {
        const magnitude = Math.sqrt(x * x + y * y + z * z);
        const sample: AccelSample = { x, y, z, magnitude, ts: Date.now() };

        buffer.push(sample);
        if (buffer.length > WINDOW_SIZE) buffer.shift();

        onMagRef.current?.(magnitude);

        if (sample.ts < cooldownUntil) return;
        if (detectFall(buffer)) {
          cooldownUntil = sample.ts + FALL_DETECTION.cooldownMs;
          buffer = [];
          onFallRef.current();
        }
      });
    } catch {
      sub = null;
    }

    return () => sub?.remove();
  }, [enabled]);
}
