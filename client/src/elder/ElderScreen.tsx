import React, { useEffect, useRef, useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { DemoScreen } from '../design/DemoScreen';
import { useDemoMachine } from '../design/useDemoMachine';
import { theme } from '../design/theme';
import { useFallSensor } from './useFallSensor';
import { careApi } from '../caretaker/api';
import type { DemoUser } from '../app/session';

// Elder experience: the Halo companion screen driven by a real, on-device
// accelerometer fall detector. A detected fall (impact + stillness) triggers
// the same check-in/escalation flow as the "Simulate Fall" button, and the
// outcome is reported to the backend so the caretaker dashboard reflects it.
export function ElderScreen({ user, onLogout }: { user: DemoUser; onLogout: () => void }) {
  const machine = useDemoMachine();
  const [mag, setMag] = useState(1);
  const [lastFall, setLastFall] = useState<number | null>(null);
  const reportedFor = useRef<string>('');

  // Real fall detection: only armed while idle so a check-in isn't re-triggered.
  useFallSensor({
    enabled: machine.state === 'idle',
    onFall: () => {
      setLastFall(Date.now());
      machine.trigger();
    },
    onMagnitude: setMag,
  });

  // Mirror the flow outcome to the backend (so Jack's dashboard sees it).
  useEffect(() => {
    const s = machine.state;
    if (s === 'escalated' && reportedFor.current !== 'escalated') {
      reportedFor.current = 'escalated';
      careApi
        .reportIncident({
          trigger_source: 'fall',
          escalated: true,
          summary: 'Fall detected on device; no clear response — caretaker alerted.',
          last_transcript: 'No clear response — reaching your caretaker.',
        })
        .catch(() => {});
    } else if (s === 'resolved' && reportedFor.current !== 'resolved') {
      reportedFor.current = 'resolved';
      careApi
        .reportIncident({
          trigger_source: 'fall',
          escalated: false,
          summary: 'Fall check-in resolved on device — resident confirmed they are okay.',
          last_transcript: 'I’m fine, just dropped a cup.',
        })
        .catch(() => {});
    } else if (s === 'idle') {
      reportedFor.current = '';
    }
  }, [machine.state]);

  const armed = machine.state === 'idle';

  return (
    <View style={styles.root}>
      <DemoScreen machine={machine} />

      {/* Top overlay: identity + logout */}
      <View style={styles.topBar} pointerEvents="box-none">
        <View style={styles.sensorPill}>
          <View style={[styles.sensorDot, { backgroundColor: armed ? theme.ok : theme.textSecondary }]} />
          <Text style={styles.sensorText}>
            {armed ? 'Fall detection on' : 'Checking in'} · |a| {mag.toFixed(2)}g
          </Text>
        </View>
        <Pressable style={styles.logout} onPress={onLogout}>
          <Text style={styles.logoutText}>Log out</Text>
        </Pressable>
      </View>

      {/* Hint so a demo viewer knows how to trigger a real fall */}
      {armed && (
        <View style={styles.hint} pointerEvents="none">
          <Text style={styles.hintText}>
            Shake the phone sharply, then hold still — or tap “Simulate Fall”.
          </Text>
          {lastFall && (
            <Text style={styles.hintSub}>last real trigger {timeSince(lastFall)}</Text>
          )}
        </View>
      )}
    </View>
  );
}

function timeSince(ts: number): string {
  const s = Math.floor((Date.now() - ts) / 1000);
  return s < 60 ? `${s}s ago` : `${Math.floor(s / 60)}m ago`;
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: theme.bg },
  topBar: {
    position: 'absolute',
    top: 10,
    left: 16,
    right: 16,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  sensorPill: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 7,
    backgroundColor: 'rgba(255,255,255,0.06)',
    borderRadius: 999,
    paddingHorizontal: 10,
    paddingVertical: 5,
  },
  sensorDot: { width: 8, height: 8, borderRadius: 4 },
  sensorText: { color: theme.textSecondary, fontSize: 12, fontWeight: '600' },
  logout: {
    backgroundColor: 'rgba(255,255,255,0.06)',
    borderRadius: 999,
    paddingHorizontal: 12,
    paddingVertical: 6,
  },
  logoutText: { color: theme.textPrimary, fontSize: 12, fontWeight: '700' },
  hint: {
    position: 'absolute',
    bottom: 168,
    left: 24,
    right: 24,
    alignItems: 'center',
  },
  hintText: { color: theme.textSecondary, fontSize: 13, textAlign: 'center', opacity: 0.85 },
  hintSub: { color: theme.textSecondary, fontSize: 11, opacity: 0.7, marginTop: 3 },
});
