import React, { useEffect, useRef } from 'react';
import { Animated, Easing, Pressable, StyleSheet, Text, View } from 'react-native';
import { theme, COUNTDOWN_SECONDS } from './theme';

// ============================================================================
// DESIGN A — "Aurora" fall check-in prompt
// Full-screen, gentle takeover. Large question, a countdown badge with a
// depleting progress track, and two oversized, elder-legible actions:
// "I'm OK" (cancel) and "I need help" (escalate immediately).
// ============================================================================

interface FallPromptProps {
  question: string;
  countdown: number;
  onOk: () => void;
  onHelp: () => void;
}

export function FallPrompt({ question, countdown, onOk, onHelp }: FallPromptProps) {
  const enter = useRef(new Animated.Value(0)).current;
  const progress = useRef(new Animated.Value(1)).current;

  useEffect(() => {
    Animated.timing(enter, {
      toValue: 1,
      duration: 360,
      easing: Easing.out(Easing.cubic),
      useNativeDriver: true,
    }).start();
  }, [enter]);

  useEffect(() => {
    Animated.timing(progress, {
      toValue: countdown / COUNTDOWN_SECONDS,
      duration: 480,
      easing: Easing.linear,
      useNativeDriver: false,
    }).start();
  }, [countdown, progress]);

  const translateY = enter.interpolate({ inputRange: [0, 1], outputRange: [40, 0] });
  const widthPct = progress.interpolate({
    inputRange: [0, 1],
    outputRange: ['0%', '100%'],
  });

  return (
    <Animated.View style={[styles.overlay, { opacity: enter }]}>
      <Animated.View style={[styles.card, { transform: [{ translateY }] }]}>
        <Text style={styles.kicker}>CHECK-IN</Text>
        <Text style={styles.question} accessibilityRole="header">
          {question}
        </Text>

        <View style={styles.countWrap}>
          <View style={styles.countBadge}>
            <Text style={styles.countNum}>{countdown}</Text>
            <Text style={styles.countUnit}>sec</Text>
          </View>
          <Text style={styles.countHelp}>
            If you don’t respond, we’ll reach your caretaker.
          </Text>
          <View style={styles.track}>
            <Animated.View style={[styles.fill, { width: widthPct }]} />
          </View>
        </View>

        <Pressable
          testID="btn-ok"
          style={({ pressed }) => [styles.ok, pressed && styles.pressed]}
          onPress={onOk}
        >
          <Text style={styles.okLabel}>I’m OK</Text>
        </Pressable>
        <Pressable
          testID="btn-help"
          style={({ pressed }) => [styles.help, pressed && styles.pressed]}
          onPress={onHelp}
        >
          <Text style={styles.helpLabel}>I need help</Text>
        </Pressable>
      </Animated.View>
    </Animated.View>
  );
}

const styles = StyleSheet.create({
  overlay: {
    ...StyleSheet.absoluteFillObject,
    backgroundColor: 'rgba(4,16,22,0.62)',
    alignItems: 'center',
    justifyContent: 'flex-end',
    padding: 20,
    // @ts-ignore web-only
    backdropFilter: 'blur(8px)',
  },
  card: {
    width: '100%',
    maxWidth: 460,
    backgroundColor: 'rgba(12,38,48,0.96)',
    borderRadius: 32,
    borderWidth: 1,
    borderColor: 'rgba(94,234,212,0.25)',
    padding: 28,
    gap: 18,
    marginBottom: 12,
  },
  kicker: {
    color: theme.textSecondary,
    fontSize: 13,
    fontWeight: '800',
    letterSpacing: 3,
    textAlign: 'center',
    fontFamily: theme.fontFamily,
  },
  question: {
    color: theme.textPrimary,
    fontSize: 30,
    fontWeight: '800',
    textAlign: 'center',
    lineHeight: 38,
    fontFamily: theme.fontFamily,
  },
  countWrap: { alignItems: 'center', gap: 12 },
  countBadge: {
    width: 96,
    height: 96,
    borderRadius: 48,
    borderWidth: 3,
    borderColor: theme.accent,
    alignItems: 'center',
    justifyContent: 'center',
  },
  countNum: { color: theme.textPrimary, fontSize: 38, fontWeight: '900', fontFamily: theme.fontFamily },
  countUnit: { color: theme.textSecondary, fontSize: 12, fontWeight: '700', marginTop: -4 },
  countHelp: {
    color: theme.textSecondary,
    fontSize: 15,
    textAlign: 'center',
    fontFamily: theme.fontFamily,
  },
  track: {
    width: '100%',
    height: 8,
    borderRadius: 4,
    backgroundColor: 'rgba(94,234,212,0.15)',
    overflow: 'hidden',
  },
  fill: { height: 8, borderRadius: 4, backgroundColor: theme.accent },
  ok: {
    backgroundColor: theme.ok,
    borderRadius: 18,
    paddingVertical: 22,
    alignItems: 'center',
  },
  okLabel: { color: theme.okText, fontSize: 24, fontWeight: '800', fontFamily: theme.fontFamily },
  help: {
    backgroundColor: theme.danger,
    borderRadius: 18,
    paddingVertical: 22,
    alignItems: 'center',
  },
  helpLabel: { color: theme.dangerText, fontSize: 24, fontWeight: '800', fontFamily: theme.fontFamily },
  pressed: { opacity: 0.85 },
});
