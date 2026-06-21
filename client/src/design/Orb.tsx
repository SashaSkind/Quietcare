import React, { useEffect, useRef } from 'react';
import { Animated, Easing, StyleSheet, View } from 'react-native';
import type { OrbMode } from './types';
import { theme } from './theme';

// ============================================================================
// DESIGN C — "Halo" orb
// A circular, audio-reactive waveform: a ring of bars whose lengths breathe in
// and out organically, around a soft glowing core. Calm + premium when idle,
// livelier while listening, rose-toned when urgent. Pure RN primitives.
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

const BAR_COUNT = 36;

interface BarCfg {
  value: Animated.Value;
  dur: number;
  peak: number;
}

export function Orb({ mode, size = 260 }: OrbProps) {
  const accent = accentFor(mode);
  const active = mode === 'listening' || mode === 'urgent';
  const glow = useRef(new Animated.Value(0)).current;
  // Stable per-bar config (random phase/speed/peak) for an organic waveform.
  const bars = useRef<BarCfg[]>(
    Array.from({ length: BAR_COUNT }, () => ({
      value: new Animated.Value(Math.random()),
      dur: 700 + Math.random() * 900,
      peak: 0.55 + Math.random() * 0.6,
    })),
  ).current;

  const radius = size * 0.34;
  const barLen = size * 0.22;
  const amp = active ? 1 : 0.45;
  const speed = active ? 0.6 : 1.1;

  useEffect(() => {
    const loops = bars.map(({ value, dur }) =>
      Animated.loop(
        Animated.sequence([
          Animated.timing(value, { toValue: 1, duration: dur * speed, easing: Easing.inOut(Easing.sin), useNativeDriver: true }),
          Animated.timing(value, { toValue: 0, duration: dur * speed, easing: Easing.inOut(Easing.sin), useNativeDriver: true }),
        ]),
      ),
    );
    loops.forEach((l) => l.start());
    const g = Animated.loop(
      Animated.sequence([
        Animated.timing(glow, { toValue: 1, duration: active ? 1400 : 3800, easing: Easing.inOut(Easing.sin), useNativeDriver: true }),
        Animated.timing(glow, { toValue: 0, duration: active ? 1400 : 3800, easing: Easing.inOut(Easing.sin), useNativeDriver: true }),
      ]),
    );
    g.start();
    return () => {
      loops.forEach((l) => l.stop());
      g.stop();
    };
  }, [bars, glow, active, speed]);

  const glowScale = glow.interpolate({ inputRange: [0, 1], outputRange: active ? [0.92, 1.1] : [0.97, 1.05] });
  const coreSize = size * 0.34;

  return (
    <View style={[styles.wrap, { width: size * 1.7, height: size * 1.7 }]}>
      {/* Soft glowing core */}
      <Animated.View
        style={[
          styles.core,
          {
            width: coreSize,
            height: coreSize,
            borderRadius: coreSize / 2,
            backgroundColor: accent,
            opacity: 0.9,
            transform: [{ scale: glowScale }],
            ...({ filter: 'blur(6px)', boxShadow: `0 0 ${size / 2.4}px ${accent}` } as object),
          },
        ]}
      />
      {/* Circular waveform of bars */}
      {bars.map(({ value, peak }, i) => {
        const rot = (360 / BAR_COUNT) * i;
        const scaleY = value.interpolate({
          inputRange: [0, 1],
          outputRange: [0.3, 0.3 + peak * amp],
        });
        return (
          <Animated.View
            key={i}
            style={[
              styles.bar,
              {
                width: 4,
                height: barLen,
                borderRadius: 2,
                backgroundColor: accent,
                transform: [
                  { rotate: `${rot}deg` },
                  { translateY: -radius },
                  { scaleY },
                ],
              },
            ]}
          />
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { alignItems: 'center', justifyContent: 'center' },
  core: { position: 'absolute' },
  bar: { position: 'absolute' },
});
