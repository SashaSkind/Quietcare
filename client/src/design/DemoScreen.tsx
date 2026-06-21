import React from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { Orb } from './Orb';
import { FallPrompt } from './FallPrompt';
import { useDemoMachine } from './useDemoMachine';
import { theme } from './theme';
import type { DemoState, OrbMode } from './types';

// ============================================================================
// Elder-facing demo screen. Composes the orb + status copy + the fall check-in
// overlay, driven by a local state machine. The "Simulate Fall" control mirrors
// the real client's trigger and is what the Playwright walkthrough taps.
// ============================================================================

function orbMode(state: DemoState): OrbMode {
  if (state === 'escalating' || state === 'escalated') return 'urgent';
  if (state === 'checking_in') return 'listening';
  return 'idle';
}

function caption(state: DemoState): { title: string; sub: string } {
  switch (state) {
    case 'idle':
      return { title: 'Listening', sub: 'All good · I’m here if you need me' };
    case 'checking_in':
      return { title: 'Are you okay?', sub: 'Listening for your answer…' };
    case 'resolved':
      return { title: 'Glad you’re okay', sub: 'Logged · no one was bothered' };
    case 'escalating':
      return { title: 'Reaching your caretaker', sub: 'Hold tight — help is coming' };
    case 'escalated':
      return { title: 'Caretaker notified', sub: 'Help is on the way' };
  }
}

export function DemoScreen() {
  const m = useDemoMachine();
  const mode = orbMode(m.state);
  const cap = caption(m.state);
  const urgent = mode === 'urgent';

  return (
    <View style={[styles.root, { backgroundColor: urgent ? theme.bgUrgent : theme.bg }]}>
      {/* Brand */}
      <View style={styles.brand}>
        <Text style={styles.brandName}>Quietcare</Text>
        <Text style={styles.brandTag}>{theme.name} · {theme.tagline}</Text>
      </View>

      {/* Orb + status */}
      <View style={styles.center}>
        <Orb mode={mode} />
        <View style={styles.status}>
          {m.state === 'resolved' && <Text style={styles.check}>✓</Text>}
          <Text style={styles.title}>{cap.title}</Text>
          <Text style={styles.sub}>{cap.sub}</Text>
          {!!m.transcript && m.state !== 'checking_in' && (
            <Text style={styles.transcript}>{m.transcript}</Text>
          )}
        </View>
      </View>

      {/* Demo control (stand-in for an on-device trigger) */}
      <View style={styles.controls}>
        {m.state === 'idle' && (
          <Pressable
            testID="btn-simulate"
            style={({ pressed }) => [styles.simulate, pressed && styles.pressed]}
            onPress={m.trigger}
          >
            <Text style={styles.simulateLabel}>Simulate Fall</Text>
          </Pressable>
        )}
        <Text style={styles.demoNote}>demo preview · {theme.name}</Text>
      </View>

      {/* Fall check-in overlay */}
      {m.state === 'checking_in' && (
        <FallPrompt
          question={m.transcript || 'Margaret, are you okay?'}
          countdown={m.countdown}
          onOk={m.confirmOk}
          onHelp={m.callForHelp}
        />
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, paddingVertical: 48, paddingHorizontal: 20 },
  brand: { alignItems: 'center', gap: 4 },
  brandName: {
    color: theme.textPrimary,
    fontSize: 22,
    fontWeight: '900',
    letterSpacing: 0.5,
    fontFamily: theme.fontFamily,
  },
  brandTag: { color: theme.textSecondary, fontSize: 13, fontWeight: '600', fontFamily: theme.fontFamily },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center', gap: 8 },
  status: { alignItems: 'center', gap: 6, marginTop: 8 },
  check: { color: theme.ok, fontSize: 44, fontWeight: '900', marginBottom: -4 },
  title: {
    color: theme.textPrimary,
    fontSize: 34,
    fontWeight: '800',
    textAlign: 'center',
    fontFamily: theme.fontFamily,
  },
  sub: { color: theme.textSecondary, fontSize: 17, textAlign: 'center', fontFamily: theme.fontFamily },
  transcript: {
    color: theme.textPrimary,
    fontSize: 18,
    fontStyle: 'italic',
    textAlign: 'center',
    marginTop: 10,
    opacity: 0.9,
    fontFamily: theme.fontFamily,
  },
  controls: { alignItems: 'center', gap: 14 },
  simulate: {
    borderWidth: 2,
    borderColor: theme.accent,
    borderRadius: 16,
    paddingVertical: 16,
    paddingHorizontal: 40,
  },
  simulateLabel: {
    color: theme.textPrimary,
    fontSize: 18,
    fontWeight: '700',
    fontFamily: theme.fontFamily,
  },
  pressed: { opacity: 0.7 },
  demoNote: {
    color: theme.textSecondary,
    fontSize: 12,
    opacity: 0.6,
    fontFamily: theme.fontFamily,
  },
});
