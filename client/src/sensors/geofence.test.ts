import { haversineMeters, isOutsideGeofence } from './geofence';

const HOME = { lat: 37.7749, lng: -122.4194 }; // San Francisco

describe('haversineMeters', () => {
  it('is ~0 for identical points', () => {
    expect(haversineMeters(HOME, HOME)).toBeLessThan(1);
  });

  it('computes a known distance roughly correctly', () => {
    // ~1.11 km north (0.01 deg latitude).
    const north = { lat: HOME.lat + 0.01, lng: HOME.lng };
    const d = haversineMeters(HOME, north);
    expect(d).toBeGreaterThan(1050);
    expect(d).toBeLessThan(1200);
  });
});

describe('isOutsideGeofence', () => {
  it('is inside within the radius', () => {
    const near = { lat: HOME.lat + 0.0003, lng: HOME.lng }; // ~33m
    expect(isOutsideGeofence(HOME, near, 150)).toBe(false);
  });

  it('is outside beyond the radius', () => {
    const far = { lat: HOME.lat + 0.01, lng: HOME.lng }; // ~1.1km
    expect(isOutsideGeofence(HOME, far, 150)).toBe(true);
  });
});
