import React, { useEffect, useRef, useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { Audio, InterruptionModeIOS } from 'expo-av';
import * as Speech from 'expo-speech';
import { DemoScreen } from '../design/DemoScreen';
import { useDemoMachine } from '../design/useDemoMachine';
import { theme } from '../design/theme';
import { useFallSensor } from './useFallSensor';
import { recordAudioBase64 } from '../audio/audioManager';
import { careApi } from '../caretaker/api';
import type { DemoUser } from '../app/session';

// Classify a spoken check-in reply. Help wins over OK for safety.
const HELP_RE = /\b(help|can'?t|cannot|hurt|emergency|fell|fall|stuck)\b/i;
const OK_RE = /\b(ok|okay|fine|good|yes|yeah|yep|alright|all right|great)\b/i;

// Elder experience: the Halo companion screen driven by a real, on-device
// accelerometer fall detector. A detected fall (impact + stillness) triggers
// the same check-in/escalation flow as the "Simulate Fall" button, and the
// outcome is reported to the backend so the caretaker dashboard reflects it.
export function ElderScreen({ user, onLogout }: { user: DemoUser; onLogout: () => void }) {
  const machine = useDemoMachine();
  const [mag, setMag] = useState(1);
  const [lastFall, setLastFall] = useState<number | null>(null);
  const [voice, setVoice] = useState('');
  const reportedFor = useRef<string>('');
  // Latest state, readable inside the async listen flow without stale closures.
  const stateRef = useRef(machine.state);
  stateRef.current = machine.state;

  // Allow the spoken check-in to be heard even with the iOS mute switch on.
  // Set a full playback session so AVSpeechSynthesizer routes to the speaker.
  useEffect(() => {
    Audio.setAudioModeAsync({
      playsInSilentModeIOS: true,
      allowsRecordingIOS: false,
      interruptionModeIOS: InterruptionModeIOS.DuckOthers,
      shouldDuckAndroid: true,
      playThroughEarpieceAndroid: false,
    }).catch((e) => setVoice(`audio mode err: ${String(e)}`));
  }, []);

  // Direct TTS test so audio can be verified independent of the fall flow.
  const testVoice = () => {
    setVoice('speaking…');
    Speech.stop();
    Speech.speak('Margaret, can you hear me? This is a voice test.', {
      rate: 0.95,
      onDone: () => setVoice('voice ok ✓'),
      onStopped: () => setVoice('stopped'),
      onError: (e) => setVoice(`voice error: ${String(e)}`),
    });
  };

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

  // Hybrid check-in: while the prompt is up, also LISTEN. Record after the
  // spoken question finishes (so we don't transcribe our own TTS), transcribe
  // via the backend (Deepgram), and resolve/escalate on the reply. The tap
  // buttons stay active — whichever resolves first wins.
  useEffect(() => {
    if (machine.state !== 'checking_in') return;
    let cancelled = false;
    const stillChecking = () => !cancelled && stateRef.current === 'checking_in';

    (async () => {
      setVoice('listening…');
      // Wait for the spoken prompt to finish (poll up to ~3s).
      for (let i = 0; i < 12; i++) {
        let speaking = false;
        try {
          speaking = await Speech.isSpeakingAsync();
        } catch {
          // ignore
        }
        if (!speaking || cancelled) break;
        await new Promise((r) => setTimeout(r, 250));
      }
      if (!stillChecking()) return;

      let clip = '';
      try {
        clip = await recordAudioBase64(5000);
      } catch {
        if (!cancelled) setVoice('mic unavailable — tap to respond');
        return;
      }
      // Recording switched the session to record mode; restore playback so the
      // resolved/escalation prompts are audible.
      Audio.setAudioModeAsync({
        playsInSilentModeIOS: true,
        allowsRecordingIOS: false,
        interruptionModeIOS: InterruptionModeIOS.DuckOthers,
      }).catch(() => {});
      if (!stillChecking()) return;

      let transcript = '';
      try {
        transcript = (await careApi.transcribe(clip)).transcript || '';
      } catch {
        // ignore — fall back to tap / countdown
      }
      if (!stillChecking()) return;
      setVoice(transcript ? `heard: “${transcript}”` : 'no reply heard');
      if (HELP_RE.test(transcript)) machine.callForHelp();
      else if (OK_RE.test(transcript)) machine.confirmOk();
      // else: let the countdown escalate naturally.
    })();

    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
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
        <View style={styles.rightBtns}>
          <Pressable style={styles.logout} onPress={testVoice}>
            <Text style={styles.logoutText}>🔊 Test</Text>
          </Pressable>
          <Pressable style={styles.logout} onPress={onLogout}>
            <Text style={styles.logoutText}>Log out</Text>
          </Pressable>
        </View>
      </View>

      {!!voice && (
        <View style={styles.voiceStatus} pointerEvents="none">
          <Text style={styles.voiceStatusText}>{voice}</Text>
        </View>
      )}

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
  rightBtns: { flexDirection: 'row', gap: 8 },
  voiceStatus: { position: 'absolute', top: 48, right: 16 },
  voiceStatusText: { color: theme.textSecondary, fontSize: 11 },
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
