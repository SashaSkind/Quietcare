import React, { useEffect, useRef } from 'react';
import { Animated, Easing, StyleSheet, View } from 'react-native';
import type { OrbMode } from './types';
import { theme } from './theme';

// ============================================================================
// DESIGN B — "Pulse" orb
// A crisp, high-contrast core that breathes, surrounded by clean concentric
// rings and outward-rippling pulse rings (staggered). No soft blur — bold,
// legible structure. Pure RN primitives, adoptable into the native app.
// ============================================================================

interface OrbProps {
  mode: OrbMode;
  size?: number;
}

function accentFor(mode: OrbMode): string {
  if (mode === 'urgent') return theme.orbUrgent[3];
  if (mode === 'listening') return theme.orbListening[3];
  return theme.orbIdle[3];
}

const RIPPLES = [0, 1, 2];

export function Orb({ mode, size = 260 }: OrbProps) {
  const breathe = useRef(new Animated.Value(0)).current;
  const ripples = useRef(RIPPLES.map(() => new Animated.Value(0))).current;
  const accent = accentFor(mode);
  const active = mode === 'listening' || mode === 'urgent';
  const core = size * 0.42;

  useEffect(() => {
    const speed = active ? 1100 : 3600;
    const loop = Animated.loop(
      Animated.sequence([
        Animated.timing(breathe, { toValue: 1, duration: speed, easing: Easing.inOut(Easing.sin), useNativeDriver: true }),
        Animated.timing(breathe, { toValue: 0, duration: speed, easing: Easing.inOut(Easing.sin), useNativeDriver: true }),
      ]),
    );
    loop.start();
    return () => loop.stop();
  }, [active, breathe]);

  useEffect(() => {
    const period = mode === 'urgent' ? 1400 : 2200;
    const loops = ripples.map((v, i) =>
      Animated.loop(
        Animated.sequence([
          Animated.delay((period / RIPPLES.length) * i),
          Animated.timing(v, { toValue: 1, duration: period, easing: Easing.out(Easing.ease), useNativeDriver: true }),
        ]),
      ),
    );
    loops.forEach((l) => l.start());
    return () => loops.forEach((l) => l.stop());
  }, [mode, ripples]);

  const coreScale = breathe.interpolate({ inputRange: [0, 1], outputRange: active ? [0.9, 1.08] : [0.96, 1.04] });

  return (
    <View style={[styles.wrap, { width: size * 1.7, height: size * 1.7 }]}>
      {/* Static structural rings */}
      {[1, 0.72].map((f, i) => (
        <View
          key={`s${i}`}
          style={[styles.ringBase, { width: size * f, height: size * f, borderRadius: (size * f) / 2, borderColor: accent, opacity: 0.18 }]}
        />
      ))}
      {/* Outward ripple rings */}
      {ripples.map((v, i) => (
        <Animated.View
          key={`r${i}`}
          style={[
            styles.ringBase,
            {
              width: size * 0.6,
              height: size * 0.6,
              borderRadius: size * 0.3,
              borderColor: accent,
              transform: [{ scale: v.interpolate({ inputRange: [0, 1], outputRange: [1, 2.4] }) }],
              opacity: v.interpolate({ inputRange: [0, 1], outputRange: [0.6, 0] }),
            },
          ]}
        />
      ))}
      {/* Bold solid core */}
      <Animated.View
        style={[
          styles.core,
          {
            width: core,
            height: core,
            borderRadius: core / 2,
            backgroundColor: accent,
            transform: [{ scale: coreScale }],
            ...({ boxShadow: `0 0 ${size / 3}px ${accent}` } as object),
          },
        ]}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { alignItems: 'center', justifyContent: 'center' },
  ringBase: { position: 'absolute', borderWidth: 3 },
  core: { position: 'absolute' },
});
