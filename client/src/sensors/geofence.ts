import { GEOFENCE } from '../config';
import type { GeoPoint } from '../types';

const EARTH_RADIUS_M = 6_371_000;

function toRad(deg: number): number {
  return (deg * Math.PI) / 180;
}

/** Great-circle (haversine) distance in meters between two points. */
export function haversineMeters(a: GeoPoint, b: GeoPoint): number {
  const dLat = toRad(b.lat - a.lat);
  const dLng = toRad(b.lng - a.lng);
  const lat1 = toRad(a.lat);
  const lat2 = toRad(b.lat);
  const h =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(lat1) * Math.cos(lat2) * Math.sin(dLng / 2) ** 2;
  return 2 * EARTH_RADIUS_M * Math.asin(Math.min(1, Math.sqrt(h)));
}

/** True when `point` is farther than `radiusM` from `home`. */
export function isOutsideGeofence(home: GeoPoint, point: GeoPoint, radiusM: number): boolean {
  return haversineMeters(home, point) > radiusM;
}

export interface GeofenceHandlers {
  onBreach: (location: GeoPoint) => void;
  onLog?: (msg: string) => void;
}

/**
 * Polls device location and fires `onBreach` when the elder leaves the safe
 * radius around home. Uses expo-location dynamically and is a graceful no-op if
 * the module/permission/home anchor is unavailable.
 */
export class GeofenceMonitor {
  private timer: ReturnType<typeof setInterval> | null = null;
  private cooldownUntil = 0;
  private handlers: GeofenceHandlers;

  constructor(handlers: GeofenceHandlers) {
    this.handlers = handlers;
  }

  async start(): Promise<void> {
    if (!GEOFENCE.enabled || !GEOFENCE.home) {
      this.handlers.onLog?.('geofence disabled or no home anchor set');
      return;
    }
    // Indirect specifier so the optional native module is resolved at runtime
    // (and typed as `any`) — the app builds/typechecks without expo-location.
    let Location: any;
    try {
      const moduleName = 'expo-location';
      Location = await import(moduleName);
    } catch {
      this.handlers.onLog?.('expo-location unavailable; geofence inactive');
      return;
    }
    try {
      const { status } = await Location.requestForegroundPermissionsAsync();
      if (status !== 'granted') {
        this.handlers.onLog?.('location permission denied; geofence inactive');
        return;
      }
    } catch {
      return;
    }

    const poll = async () => {
      try {
        const pos = await Location.getCurrentPositionAsync({});
        const point: GeoPoint = { lat: pos.coords.latitude, lng: pos.coords.longitude };
        const now = Date.now();
        if (
          now >= this.cooldownUntil &&
          GEOFENCE.home &&
          isOutsideGeofence(GEOFENCE.home, point, GEOFENCE.radiusM)
        ) {
          this.cooldownUntil = now + GEOFENCE.cooldownMs;
          this.handlers.onBreach(point);
        }
      } catch (err) {
        this.handlers.onLog?.(`geofence poll failed: ${String(err)}`);
      }
    };
    void poll();
    this.timer = setInterval(poll, GEOFENCE.pollMs);
  }

  stop(): void {
    if (this.timer) clearInterval(this.timer);
    this.timer = null;
    this.cooldownUntil = 0;
  }
}
