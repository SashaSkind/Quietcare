import React, { useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { audioManager } from '../audio/audioManager';
import { DemoScreen } from '../design/DemoScreen';
import { theme } from '../design/theme';
import type { DemoUser } from '../app/session';
import type { AudioProbeResultMessage } from '../types';
import { useFallSensor } from './useFallSensor';
import { useElderWebSocket } from './useElderWebSocket';

type AudioSceneResult = AudioProbeResultMessage['audio_scene'];

export function ElderScreen({ onLogout }: { user: DemoUser; onLogout: () => void }) {
  const { machine, connection, voice, agentMode, scene, sendFallTrigger } = useElderWebSocket();
  const [mag, setMag] = useState(1);
  const [lastFall, setLastFall] = useState<number | null>(null);

  const testVoice = () => {
    audioManager
      .speakText('Margaret, can you hear me? This is a voice test.')
      .catch(() => undefined);
  };

  useFallSensor({
    enabled: machine.state === 'idle',
    onFall: () => {
      setLastFall(Date.now());
      sendFallTrigger();
    },
    onMagnitude: setMag,
  });

  const armed = machine.state === 'idle';

  return (
    <View style={styles.root}>
      <DemoScreen machine={machine} showBrand={false} />

      <View style={styles.topBar} pointerEvents="box-none">
        <View style={styles.sensorPill}>
          <View style={[styles.sensorDot, { backgroundColor: armed ? theme.ok : theme.textSecondary }]} />
          <Text style={styles.sensorText}>
            {armed ? 'Fall detection on' : 'Checking in'} · ws {connection} · |a| {mag.toFixed(2)}g
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

      <View style={styles.agentStatus} pointerEvents="none">
        <Text style={styles.agentTitle}>{agentMode}</Text>
        <Text style={styles.agentSub}>WS handles triggers, prompts, audio replies, wake chat, and YAMNet.</Text>
      </View>

      <View style={styles.mlStatus} pointerEvents="none">
        <Text style={styles.mlTitle}>{sceneLabel(scene)}</Text>
        <Text style={styles.mlSub}>{formatAudioScene(scene) || 'waiting for audio tags'}</Text>
      </View>

      {!!voice && (
        <View style={styles.voiceStatus} pointerEvents="none">
          <Text style={styles.voiceStatusText}>{voice}</Text>
        </View>
      )}

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

function sceneLabel(scene: AudioSceneResult | null): string {
  if (!scene) return 'YAMNet ML waiting';
  const model = scene.source === 'yamnet' ? 'YAMNet ML live' : `${scene.source} audio scene`;
  return `${model} · ${scene.distress ? 'distress' : 'normal'}`;
}

function formatAudioScene(scene: AudioSceneResult | null): string {
  if (!scene || scene.tags.length === 0) return '';
  return scene.tags
    .slice(0, 2)
    .map((tag) => `${tag.label} ${(tag.score * 100).toFixed(0)}%`)
    .join(' · ');
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
  agentStatus: {
    position: 'absolute',
    top: 48,
    left: 16,
    right: 16,
    backgroundColor: 'rgba(255,255,255,0.07)',
    borderRadius: 16,
    paddingHorizontal: 12,
    paddingVertical: 9,
  },
  agentTitle: { color: theme.textPrimary, fontSize: 13, fontWeight: '800' },
  agentSub: { color: theme.textSecondary, fontSize: 10, marginTop: 2 },
  mlStatus: {
    position: 'absolute',
    top: 112,
    left: 16,
    right: 16,
    backgroundColor: 'rgba(46, 204, 113, 0.11)',
    borderRadius: 16,
    paddingHorizontal: 12,
    paddingVertical: 9,
  },
  mlTitle: { color: theme.ok, fontSize: 12, fontWeight: '800' },
  mlSub: { color: theme.textSecondary, fontSize: 10, marginTop: 2 },
  voiceStatus: { position: 'absolute', top: 178, right: 16, left: 16, alignItems: 'flex-end' },
  voiceStatusText: { color: theme.textSecondary, fontSize: 11, textAlign: 'right' },
  hint: {
    position: 'absolute',
    bottom: 118,
    left: 24,
    right: 24,
    alignItems: 'center',
  },
  hintText: { color: theme.textSecondary, fontSize: 13, textAlign: 'center', opacity: 0.85 },
  hintSub: { color: theme.textSecondary, fontSize: 11, opacity: 0.7, marginTop: 3 },
});
