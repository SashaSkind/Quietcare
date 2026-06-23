import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  ActivityIndicator,
  Pressable,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { theme } from '../design/theme';
import { careApi, isIncident, type BackendHealth, type EventRecord, type IncidentEvent } from './api';

type StepTone = 'idle' | 'active' | 'done' | 'warn';

interface AgentStep {
  id: string;
  title: string;
  detail: string;
  provider?: string;
  tone: StepTone;
}

const POLL_MS = 5000;

function newestIncident(events: EventRecord[]): IncidentEvent | null {
  return events
    .filter(isIncident)
    .sort((a, b) => new Date(b.ts).getTime() - new Date(a.ts).getTime())[0] ?? null;
}

function timeAgo(iso?: string): string {
  if (!iso) return '—';
  const secs = Math.max(0, Math.floor((Date.now() - new Date(iso).getTime()) / 1000));
  if (secs < 45) return 'just now';
  if (secs < 3600) return `${Math.floor(secs / 60)}m ago`;
  if (secs < 86400) return `${Math.floor(secs / 3600)}h ago`;
  return `${Math.floor(secs / 86400)}d ago`;
}

function toneColor(tone: StepTone): string {
  if (tone === 'active') return theme.accent;
  if (tone === 'done') return theme.ok;
  if (tone === 'warn') return theme.danger;
  return theme.textSecondary;
}

function buildSteps(health: BackendHealth | null, incident: IncidentEvent | null): AgentStep[] {
  const recent = incident ? Date.now() - new Date(incident.ts).getTime() < 10 * 60 * 1000 : false;
  const escalated = Boolean(recent && incident?.escalated);
  const resolved = Boolean(recent && incident && !incident.escalated);
  const agentTone: StepTone = recent ? 'active' : 'idle';
  const decisionTone: StepTone = escalated ? 'warn' : resolved ? 'done' : recent ? 'active' : 'idle';
  return [
    {
      id: 'inputs',
      title: '1. Elder device inputs',
      detail: 'Fall sensor, wake word transcript, and YAMNet audio scene clips enter the backend.',
      tone: recent ? 'done' : 'idle',
    },
    {
      id: 'router',
      title: '2. FastAPI trigger router',
      detail: 'Routes fall incidents to the check-in agent and wake phrases to the voice conversation agent.',
      tone: recent ? 'done' : 'idle',
    },
    {
      id: 'elder-agent',
      title: '3. Elder agent loop',
      detail: 'LLM chooses tools: speak to elder, listen for reply, classify audio, then decide next action.',
      provider: 'llm',
      tone: agentTone,
    },
    {
      id: 'voice-ml',
      title: '4. Voice + ML tools',
      detail: 'Deepgram transcribes/speaks; YAMNet labels distress sounds like thud, glass, scream, or bang.',
      provider: 'audio_scene',
      tone: recent ? 'active' : health ? 'done' : 'idle',
    },
    {
      id: 'decision',
      title: '5. Safety decision',
      detail: escalated
        ? 'Latest flow escalated because the response or acoustic evidence looked unsafe.'
        : resolved
          ? 'Latest flow resolved because the elder confirmed they were okay.'
          : 'Combines transcript, acoustic evidence, and recent context before alerting anyone.',
      provider: 'policy_gate',
      tone: decisionTone,
    },
    {
      id: 'caretaker-agent',
      title: '6. Caretaker agent',
      detail: 'Packages evidence for the caretaker, sends dashboard events, and coordinates follow-up.',
      provider: 'bus',
      tone: escalated ? 'warn' : recent ? 'done' : 'idle',
    },
    {
      id: 'telephony',
      title: '7. Call / SMS / emergency fallback',
      detail: 'Telephony calls the caretaker first; policy gate can allow emergency fallback if needed.',
      provider: 'telephony',
      tone: escalated ? 'warn' : 'idle',
    },
  ];
}

export function AgentFlowScreen({
  elderId,
  onBack,
  onLogout,
}: {
  elderId: string;
  onBack: () => void;
  onLogout: () => void;
}) {
  const [health, setHealth] = useState<BackendHealth | null>(null);
  const [events, setEvents] = useState<EventRecord[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const mounted = useRef(true);

  const load = useCallback(async () => {
    try {
      const [h, e] = await Promise.all([careApi.health(), careApi.events(elderId, 30)]);
      if (!mounted.current) return;
      setHealth(h);
      setEvents(e.events);
      setError(null);
    } catch (e) {
      if (mounted.current) setError(String((e as Error).message || e));
    }
  }, [elderId]);

  useEffect(() => {
    mounted.current = true;
    void load();
    const t = setInterval(load, POLL_MS);
    return () => {
      mounted.current = false;
      clearInterval(t);
    };
  }, [load]);

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    await load();
    setRefreshing(false);
  }, [load]);

  const incident = useMemo(() => newestIncident(events), [events]);
  const steps = useMemo(() => buildSteps(health, incident), [health, incident]);
  const providerEntries = Object.entries(health?.providers ?? {}).filter(([key]) =>
    ['llm', 'voice', 'audio_scene', 'telephony', 'bus', 'policy_gate'].includes(key),
  );
  const recentEvents = [...events]
    .sort((a, b) => new Date(b.ts ?? 0).getTime() - new Date(a.ts ?? 0).getTime())
    .slice(0, 6);

  return (
    <View style={styles.root}>
      <View style={styles.header}>
        <View style={styles.headerLeft}>
          <Pressable style={styles.backBtn} onPress={onBack}>
            <Text style={styles.backText}>‹</Text>
          </Pressable>
          <View>
            <Text style={styles.brand}>Backend agents</Text>
            <Text style={styles.role}>Live flow · {elderId}</Text>
          </View>
        </View>
        <Pressable style={styles.logout} onPress={onLogout}>
          <Text style={styles.logoutText}>Log out</Text>
        </Pressable>
      </View>

      <ScrollView
        contentContainerStyle={styles.scroll}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={theme.accent} />}
      >
        {!health && !error && (
          <View style={styles.loadingCard}>
            <ActivityIndicator color={theme.accent} />
            <Text style={styles.muted}>Loading backend agent state…</Text>
          </View>
        )}

        {error && (
          <View style={styles.errorCard}>
            <Text style={styles.errorTitle}>Backend flow unavailable</Text>
            <Text style={styles.muted}>{error}</Text>
          </View>
        )}

        <View style={styles.heroCard}>
          <View>
            <Text style={styles.kicker}>What happens after a trigger</Text>
            <Text style={styles.heroTitle}>Sensor/audio → agents → tools → caretaker</Text>
          </View>
          <View style={[styles.healthPill, { borderColor: health ? theme.ok : theme.textSecondary }]}>
            <View style={[styles.healthDot, { backgroundColor: health ? theme.ok : theme.textSecondary }]} />
            <Text style={styles.healthText}>{health?.status ?? 'unknown'}</Text>
          </View>
        </View>

        {providerEntries.length > 0 && (
          <View style={styles.providerGrid}>
            {providerEntries.map(([key, value]) => (
              <View key={key} style={styles.providerTile}>
                <Text style={styles.providerKey}>{key.replace('_', ' ')}</Text>
                <Text style={styles.providerValue}>{String(value)}</Text>
              </View>
            ))}
          </View>
        )}

        <View style={styles.flowCard}>
          <Text style={styles.cardTitle}>Agent execution path</Text>
          <View style={styles.steps}>
            {steps.map((step, index) => (
              <View key={step.id} style={styles.stepRow}>
                <View style={styles.rail}>
                  <View style={[styles.stepDot, { backgroundColor: toneColor(step.tone) }]} />
                  {index < steps.length - 1 && <View style={styles.railLine} />}
                </View>
                <View style={[styles.stepCard, { borderColor: `${toneColor(step.tone)}55` }]}>
                  <View style={styles.stepTitleRow}>
                    <Text style={styles.stepTitle}>{step.title}</Text>
                    <Text style={[styles.stepState, { color: toneColor(step.tone) }]}>{step.tone}</Text>
                  </View>
                  <Text style={styles.stepDetail}>{step.detail}</Text>
                  {!!step.provider && (
                    <Text style={styles.providerHint}>
                      provider: {step.provider.replace('_', ' ')} · {health?.providers?.[step.provider] ?? 'not loaded'}
                    </Text>
                  )}
                </View>
              </View>
            ))}
          </View>
        </View>

        <View style={styles.flowCard}>
          <Text style={styles.cardTitle}>Latest backend evidence</Text>
          {incident ? (
            <View style={styles.latestCard}>
              <Text style={styles.latestTitle}>{incident.escalated ? 'Escalated incident' : 'Resolved incident'}</Text>
              <Text style={styles.stepDetail}>{incident.summary || incident.last_transcript || 'No transcript captured.'}</Text>
              <Text style={styles.providerHint}>{incident.trigger_source} · {timeAgo(incident.ts)}</Text>
            </View>
          ) : (
            <Text style={styles.muted}>No incident agent runs yet. Trigger a fall or wake conversation to populate this.</Text>
          )}
        </View>

        <View style={styles.flowCard}>
          <Text style={styles.cardTitle}>Recent event stream</Text>
          {recentEvents.length === 0 ? (
            <Text style={styles.muted}>No backend events yet.</Text>
          ) : (
            recentEvents.map((event, index) => <TraceRow key={`${event.ts ?? index}-${index}`} event={event} />)
          )}
        </View>
      </ScrollView>
    </View>
  );
}

function TraceRow({ event }: { event: EventRecord }) {
  const incident = isIncident(event) ? event : null;
  const tone = incident?.escalated ? theme.danger : incident ? theme.ok : theme.textSecondary;
  const title = incident
    ? `${incident.trigger_source} ${incident.escalated ? 'escalated' : 'resolved'}`
    : event.kind ?? 'backend event';
  return (
    <View style={styles.traceRow}>
      <View style={[styles.traceDot, { backgroundColor: tone }]} />
      <View style={{ flex: 1 }}>
        <Text style={styles.traceTitle}>{title}</Text>
        {incident && <Text style={styles.muted}>{incident.summary || incident.last_transcript || 'No summary'}</Text>}
      </View>
      <Text style={styles.traceTime}>{timeAgo(event.ts)}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: theme.bg, paddingTop: 8 },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 20,
    paddingVertical: 12,
  },
  headerLeft: { flexDirection: 'row', alignItems: 'center', gap: 8, flex: 1 },
  backBtn: {
    width: 36,
    height: 36,
    borderRadius: 18,
    borderWidth: 1,
    borderColor: 'rgba(255,255,255,0.14)',
    alignItems: 'center',
    justifyContent: 'center',
  },
  backText: { color: theme.textPrimary, fontSize: 24, fontWeight: '700', marginTop: -3 },
  brand: { color: theme.textPrimary, fontSize: 21, fontWeight: '900' },
  role: { color: theme.textSecondary, fontSize: 13, marginTop: 1 },
  logout: {
    borderRadius: 10,
    borderWidth: 1,
    borderColor: 'rgba(255,255,255,0.14)',
    paddingHorizontal: 12,
    paddingVertical: 7,
  },
  logoutText: { color: theme.textPrimary, fontSize: 13, fontWeight: '600' },
  scroll: { padding: 16, gap: 14, paddingBottom: 44 },
  loadingCard: {
    backgroundColor: 'rgba(255,255,255,0.04)',
    borderRadius: 18,
    padding: 18,
    alignItems: 'center',
    gap: 8,
  },
  errorCard: {
    backgroundColor: 'rgba(251,113,133,0.12)',
    borderRadius: 18,
    borderWidth: 1,
    borderColor: 'rgba(251,113,133,0.35)',
    padding: 16,
    gap: 6,
  },
  errorTitle: { color: theme.danger, fontSize: 16, fontWeight: '800' },
  heroCard: {
    backgroundColor: 'rgba(192,132,252,0.12)',
    borderRadius: 22,
    borderWidth: 1,
    borderColor: 'rgba(192,132,252,0.25)',
    padding: 18,
    gap: 14,
  },
  kicker: { color: theme.accent, fontSize: 12, fontWeight: '900', textTransform: 'uppercase', letterSpacing: 0.8 },
  heroTitle: { color: theme.textPrimary, fontSize: 24, lineHeight: 30, fontWeight: '900', marginTop: 5 },
  healthPill: {
    alignSelf: 'flex-start',
    flexDirection: 'row',
    alignItems: 'center',
    gap: 7,
    borderWidth: 1,
    borderRadius: 999,
    paddingHorizontal: 11,
    paddingVertical: 6,
  },
  healthDot: { width: 8, height: 8, borderRadius: 4 },
  healthText: { color: theme.textPrimary, fontSize: 13, fontWeight: '800' },
  providerGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: 10 },
  providerTile: {
    width: '48%',
    backgroundColor: 'rgba(255,255,255,0.04)',
    borderRadius: 16,
    borderWidth: 1,
    borderColor: 'rgba(255,255,255,0.08)',
    padding: 12,
    gap: 4,
  },
  providerKey: { color: theme.textSecondary, fontSize: 11, fontWeight: '700', textTransform: 'uppercase' },
  providerValue: { color: theme.textPrimary, fontSize: 15, fontWeight: '800' },
  flowCard: {
    backgroundColor: 'rgba(255,255,255,0.04)',
    borderRadius: 20,
    borderWidth: 1,
    borderColor: 'rgba(255,255,255,0.08)',
    padding: 16,
    gap: 12,
  },
  cardTitle: { color: theme.textPrimary, fontSize: 17, fontWeight: '900' },
  steps: { gap: 0 },
  stepRow: { flexDirection: 'row', gap: 12 },
  rail: { width: 18, alignItems: 'center' },
  stepDot: { width: 13, height: 13, borderRadius: 7, marginTop: 17 },
  railLine: { flex: 1, width: 2, backgroundColor: 'rgba(255,255,255,0.12)', marginTop: 4 },
  stepCard: {
    flex: 1,
    borderWidth: 1,
    backgroundColor: 'rgba(12,10,31,0.68)',
    borderRadius: 16,
    padding: 13,
    marginBottom: 10,
    gap: 6,
  },
  stepTitleRow: { flexDirection: 'row', justifyContent: 'space-between', gap: 8 },
  stepTitle: { color: theme.textPrimary, fontSize: 15, fontWeight: '800', flex: 1 },
  stepState: { fontSize: 11, fontWeight: '900', textTransform: 'uppercase' },
  stepDetail: { color: theme.textSecondary, fontSize: 13, lineHeight: 18 },
  providerHint: { color: theme.textSecondary, fontSize: 11, fontWeight: '700', opacity: 0.9 },
  latestCard: {
    backgroundColor: 'rgba(255,255,255,0.04)',
    borderRadius: 14,
    padding: 13,
    gap: 6,
  },
  latestTitle: { color: theme.textPrimary, fontSize: 15, fontWeight: '800' },
  muted: { color: theme.textSecondary, fontSize: 13, lineHeight: 18 },
  traceRow: { flexDirection: 'row', alignItems: 'flex-start', gap: 10, paddingVertical: 8 },
  traceDot: { width: 9, height: 9, borderRadius: 5, marginTop: 5 },
  traceTitle: { color: theme.textPrimary, fontSize: 14, fontWeight: '700' },
  traceTime: { color: theme.textSecondary, fontSize: 12 },
});
