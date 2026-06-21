import React, { useEffect, useRef } from 'react';
import { Animated, Easing, StyleSheet, View } from 'react-native';
import type { OrbMode } from './types';
import { theme } from './theme';

// ============================================================================
// DESIGN A — "Aurora" orb
// A soft, layered-glow sphere that slowly breathes when idle and pulses with
// concentric listening rings during a check-in. Pure RN primitives so it can
// be lifted straight into the native app.
// ============================================================================

interface OrbProps {
  mode: OrbMode;
  size?: number;
}

function colorsFor(mode: OrbMode): string[] {
  if (mode === 'urgent') return theme.orbUrgent;
  if (mode === 'listening') return theme.orbListening;
  return theme.orbIdle;
}

export function Orb({ mode, size = 260 }: OrbProps) {
  const breathe = useRef(new Animated.Value(0)).current;
  const ring = useRef(new Animated.Value(0)).current;
  const colors = colorsFor(mode);
  const active = mode === 'listening' || mode === 'urgent';

  useEffect(() => {
    const speed = active ? 1400 : 4200;
    const loop = Animated.loop(
      Animated.sequence([
        Animated.timing(breathe, {
          toValue: 1,
          duration: speed,
          easing: Easing.inOut(Easing.sin),
          useNativeDriver: true,
        }),
        Animated.timing(breathe, {
          toValue: 0,
          duration: speed,
          easing: Easing.inOut(Easing.sin),
          useNativeDriver: true,
        }),
      ]),
    );
    loop.start();
    return () => loop.stop();
  }, [active, breathe]);

  useEffect(() => {
    if (!active) {
      ring.setValue(0);
      return;
    }
    const loop = Animated.loop(
      Animated.timing(ring, {
        toValue: 1,
        duration: mode === 'urgent' ? 1100 : 1800,
        easing: Easing.out(Easing.ease),
        useNativeDriver: true,
      }),
    );
    loop.start();
    return () => loop.stop();
  }, [active, mode, ring]);

  const coreScale = breathe.interpolate({
    inputRange: [0, 1],
    outputRange: active ? [0.94, 1.06] : [0.97, 1.03],
  });
  const ringScale = ring.interpolate({ inputRange: [0, 1], outputRange: [0.7, 1.7] });
  const ringOpacity = ring.interpolate({ inputRange: [0, 1], outputRange: [0.45, 0] });

  return (
    <View style={[styles.wrap, { width: size * 1.7, height: size * 1.7 }]}>
      {active && (
        <Animated.View
          style={[
            styles.ring,
            {
              width: size,
              height: size,
              borderRadius: size / 2,
              borderColor: colors[2],
              transform: [{ scale: ringScale }],
              opacity: ringOpacity,
            },
          ]}
        />
      )}
      {/* Glow layers, outer -> inner */}
      {colors.map((c, i) => {
        const layerSize = size * (1 - i * 0.2);
        const isCore = i === colors.length - 1;
        return (
          <Animated.View
            key={i}
            style={[
              styles.layer,
              {
                width: layerSize,
                height: layerSize,
                borderRadius: layerSize / 2,
                backgroundColor: c,
                transform: isCore ? [{ scale: coreScale }] : undefined,
                ...({
                  filter: isCore ? 'blur(0.5px)' : 'blur(10px)',
                  boxShadow: isCore ? `0 0 ${size / 4}px ${c}` : undefined,
                } as object),
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
  layer: { position: 'absolute', alignItems: 'center', justifyContent: 'center' },
  ring: { position: 'absolute', borderWidth: 2 },
});
