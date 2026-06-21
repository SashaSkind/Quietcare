import React, { useCallback, useEffect, useRef, useState } from 'react';
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
import type { DemoUser } from '../app/session';
import {
  careApi,
  isIncident,
  isMedication,
  type AdherenceSummary,
  type ElderProfile,
  type EventRecord,
  type MedicationItem,
  type WellnessTrends,
} from './api';

type CareStatus = 'ok' | 'checking_in' | 'alerting';

interface DashboardData {
  profile: ElderProfile;
  summary: string;
  trends: WellnessTrends;
  adherence: AdherenceSummary;
  medications: MedicationItem[];
  events: EventRecord[];
  pendingConfirmation: boolean;
}

const POLL_MS = 5000;

function timeAgo(iso?: string): string {
  if (!iso) return '—';
  const secs = Math.max(0, Math.floor((Date.now() - new Date(iso).getTime()) / 1000));
  if (secs < 45) return 'just now';
  if (secs < 3600) return `${Math.floor(secs / 60)}m ago`;
  if (secs < 86400) return `${Math.floor(secs / 3600)}h ago`;
  return `${Math.floor(secs / 86400)}d ago`;
}

function deriveStatus(events: EventRecord[], pending: boolean): CareStatus {
  if (pending) return 'alerting';
  const incidents = events.filter(isIncident);
  const last = incidents[incidents.length - 1];
  if (!last) return 'ok';
  const ageMs = Date.now() - new Date(last.ts).getTime();
  if (last.escalated && ageMs < 10 * 60 * 1000) return 'alerting';
  if (ageMs < 2 * 60 * 1000) return 'checking_in';
  return 'ok';
}

const STATUS_META: Record<CareStatus, { label: string; color: string; bg: string }> = {
  ok: { label: 'All good', color: '#34d399', bg: 'rgba(52,211,153,0.16)' },
  checking_in: { label: 'Checking in', color: '#fbbf24', bg: 'rgba(251,191,36,0.16)' },
  alerting: { label: 'Needs attention', color: '#fb7185', bg: 'rgba(251,113,133,0.18)' },
};

export function CaretakerDashboard({ user, onLogout }: { user: DemoUser; onLogout: () => void }) {
  const [data, setData] = useState<DashboardData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const mounted = useRef(true);

  const load = useCallback(async () => {
    try {
      const [elder, summary, wellness, adherence, meds, events, confirmation] =
        await Promise.all([
          careApi.elder(user.elderId),
          careApi.summary(user.elderId),
          careApi.wellness(user.elderId),
          careApi.adherence(user.elderId),
          careApi.medications(user.elderId),
          careApi.events(user.elderId),
          careApi.confirmation(user.elderId),
        ]);
      if (!mounted.current) return;
      setData({
        profile: elder.profile,
        summary: summary.summary,
        trends: wellness.trends,
        adherence: adherence.adherence,
        medications: meds.medications,
        events: events.events,
        pendingConfirmation: confirmation?.status === 'pending',
      });
      setError(null);
    } catch (e) {
      if (mounted.current) setError(String((e as Error).message || e));
    }
  }, [user.elderId]);

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

  const name = data?.profile?.name ?? 'Margaret';
  const status = data ? deriveStatus(data.events, data.pendingConfirmation) : 'ok';
  const sm = STATUS_META[status];
  const lastTs = data?.events?.[data.events.length - 1]?.ts;
  const adherencePct =
    data && data.adherence.total > 0 && data.adherence.adherence_rate != null
      ? Math.round(data.adherence.adherence_rate * 100)
      : null;

  return (
    <View style={styles.root}>
      {/* Header */}
      <View style={styles.header}>
        <View>
          <Text style={styles.brand}>Quietcare</Text>
          <Text style={styles.role}>Caretaker · {user.name}</Text>
        </View>
        <Pressable style={styles.logout} onPress={onLogout}>
          <Text style={styles.logoutText}>Log out</Text>
        </Pressable>
      </View>

      {!data && !error && (
        <View style={styles.center}>
          <ActivityIndicator color={theme.accent} />
          <Text style={styles.muted}>Loading {name}'s status…</Text>
        </View>
      )}

      {error && !data && (
        <View style={styles.center}>
          <Text style={styles.errTitle}>Can't reach the backend</Text>
          <Text style={styles.muted}>{error}</Text>
          <Text style={styles.muted}>Check EXPO_PUBLIC_API_URL ({'LAN IP'}:8000).</Text>
        </View>
      )}

      {data && (
        <ScrollView
          contentContainerStyle={styles.scroll}
          refreshControl={
            <RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={theme.accent} />
          }
        >
          {/* Alert banner */}
          {status === 'alerting' && (
            <View style={styles.alertBanner}>
              <Text style={styles.alertBannerText}>
                {data.pendingConfirmation
                  ? `${name} needs an emergency decision.`
                  : `${name} had a recent escalation.`}
              </Text>
            </View>
          )}

          {/* Resident hero */}
          <View style={styles.card}>
            <View style={styles.heroRow}>
              <View style={styles.avatar}>
                <Text style={styles.avatarText}>{name.slice(0, 1).toUpperCase()}</Text>
              </View>
              <View style={{ flex: 1 }}>
                <Text style={styles.name}>{name}</Text>
                <Text style={styles.sub}>
                  {data.profile.age ? `${data.profile.age} · ` : ''}
                  {(data.profile.conditions ?? []).join(', ') || 'no conditions on file'}
                </Text>
              </View>
            </View>
            <View style={styles.statusRow}>
              <View style={[styles.pill, { backgroundColor: sm.bg }]}>
                <View style={[styles.dot, { backgroundColor: sm.color }]} />
                <Text style={[styles.pillText, { color: sm.color }]}>{sm.label}</Text>
              </View>
              <Text style={styles.muted}>last activity {timeAgo(lastTs)}</Text>
            </View>
          </View>

          {/* Recap */}
          <View style={styles.card}>
            <Text style={styles.cardTitle}>How {name.split(' ')[0]} is doing</Text>
            <Text style={styles.recap}>{data.summary || 'No update available yet.'}</Text>
          </View>

          {/* Wellness tiles */}
          <View style={styles.card}>
            <Text style={styles.cardTitle}>This week</Text>
            <View style={styles.tiles}>
              <Tile value={data.trends.check_ins} label="check-ins" />
              <Tile value={data.trends.incidents} label="incidents" />
              <Tile value={data.trends.escalations} label="escalations" tone={data.trends.escalations ? 'alert' : undefined} />
              <Tile value={adherencePct == null ? '—' : `${adherencePct}%`} label="meds" tone={adherencePct != null && adherencePct < 70 ? 'warn' : 'ok'} />
            </View>
          </View>

          {/* Medications */}
          <View style={styles.card}>
            <Text style={styles.cardTitle}>Medications</Text>
            {data.medications.length === 0 ? (
              <Text style={styles.muted}>No medications scheduled.</Text>
            ) : (
              data.medications.map((m, i) => (
                <View key={i} style={styles.medRow}>
                  <Text style={styles.medName}>{m.name}</Text>
                  <Text style={styles.muted}>
                    {m.time}
                    {m.dose ? ` · ${m.dose}` : ''}
                  </Text>
                </View>
              ))
            )}
          </View>

          {/* Recent activity */}
          <View style={styles.card}>
            <Text style={styles.cardTitle}>Recent activity</Text>
            {data.events.length === 0 ? (
              <Text style={styles.muted}>No history yet — all quiet.</Text>
            ) : (
              [...data.events].reverse().slice(0, 12).map((e, i) => <EventRow key={i} e={e} />)
            )}
          </View>

          <Text style={styles.footer}>Live · refreshes every {POLL_MS / 1000}s · pull to refresh</Text>
        </ScrollView>
      )}
    </View>
  );
}

function Tile({ value, label, tone }: { value: number | string; label: string; tone?: 'ok' | 'warn' | 'alert' }) {
  const color = tone === 'alert' ? '#fb7185' : tone === 'warn' ? '#fbbf24' : tone === 'ok' ? '#34d399' : theme.textPrimary;
  return (
    <View style={styles.tile}>
      <Text style={[styles.tileValue, { color }]}>{value}</Text>
      <Text style={styles.tileLabel}>{label}</Text>
    </View>
  );
}

function EventRow({ e }: { e: EventRecord }) {
  if (isIncident(e)) {
    const color = e.escalated ? '#fb7185' : '#34d399';
    return (
      <View style={styles.eventRow}>
        <View style={[styles.eventDot, { backgroundColor: color }]} />
        <View style={{ flex: 1 }}>
          <Text style={styles.eventTitle}>
            {cap(e.trigger_source)} check-in {e.escalated ? '· escalated' : '· resolved'}
          </Text>
          {!!e.summary && <Text style={styles.muted}>{e.summary}</Text>}
        </View>
        <Text style={styles.eventTime}>{timeAgo(e.ts)}</Text>
      </View>
    );
  }
  if (isMedication(e)) {
    const ok = e.status === 'confirmed';
    return (
      <View style={styles.eventRow}>
        <View style={[styles.eventDot, { backgroundColor: ok ? '#34d399' : '#fbbf24' }]} />
        <View style={{ flex: 1 }}>
          <Text style={styles.eventTitle}>
            {e.medication || 'Medication'} {ok ? '· taken' : '· missed'}
          </Text>
          {!!e.scheduled_time && <Text style={styles.muted}>scheduled {e.scheduled_time}</Text>}
        </View>
        <Text style={styles.eventTime}>{timeAgo(e.ts)}</Text>
      </View>
    );
  }
  return null;
}

function cap(s: string): string {
  return s ? s.charAt(0).toUpperCase() + s.slice(1).replace(/_/g, ' ') : s;
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
  brand: { color: theme.textPrimary, fontSize: 22, fontWeight: '900' },
  role: { color: theme.textSecondary, fontSize: 13, marginTop: 1 },
  logout: {
    borderRadius: 10,
    borderWidth: 1,
    borderColor: 'rgba(255,255,255,0.14)',
    paddingHorizontal: 12,
    paddingVertical: 7,
  },
  logoutText: { color: theme.textPrimary, fontSize: 13, fontWeight: '600' },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center', gap: 8, padding: 24 },
  errTitle: { color: '#fb7185', fontSize: 16, fontWeight: '700' },
  muted: { color: theme.textSecondary, fontSize: 13 },
  scroll: { padding: 16, gap: 14, paddingBottom: 40 },
  alertBanner: {
    backgroundColor: 'rgba(251,113,133,0.16)',
    borderColor: 'rgba(251,113,133,0.45)',
    borderWidth: 1,
    borderRadius: 14,
    padding: 14,
  },
  alertBannerText: { color: '#fecdd3', fontSize: 15, fontWeight: '700' },
  card: {
    backgroundColor: 'rgba(255,255,255,0.04)',
    borderRadius: 18,
    borderWidth: 1,
    borderColor: 'rgba(255,255,255,0.08)',
    padding: 16,
    gap: 10,
  },
  heroRow: { flexDirection: 'row', alignItems: 'center', gap: 14 },
  avatar: {
    width: 52,
    height: 52,
    borderRadius: 26,
    backgroundColor: 'rgba(192,132,252,0.22)',
    alignItems: 'center',
    justifyContent: 'center',
  },
  avatarText: { color: theme.accent, fontSize: 22, fontWeight: '900' },
  name: { color: theme.textPrimary, fontSize: 22, fontWeight: '800' },
  sub: { color: theme.textSecondary, fontSize: 14, marginTop: 2 },
  statusRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  pill: { flexDirection: 'row', alignItems: 'center', gap: 7, borderRadius: 999, paddingHorizontal: 12, paddingVertical: 6 },
  dot: { width: 9, height: 9, borderRadius: 5 },
  pillText: { fontSize: 14, fontWeight: '700' },
  cardTitle: { color: theme.textPrimary, fontSize: 16, fontWeight: '800' },
  recap: { color: theme.textPrimary, fontSize: 16, lineHeight: 23, opacity: 0.92 },
  tiles: { flexDirection: 'row', gap: 10 },
  tile: {
    flex: 1,
    backgroundColor: 'rgba(255,255,255,0.04)',
    borderRadius: 12,
    paddingVertical: 14,
    alignItems: 'center',
  },
  tileValue: { fontSize: 22, fontWeight: '900' },
  tileLabel: { color: theme.textSecondary, fontSize: 11, marginTop: 3 },
  medRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', paddingVertical: 4 },
  medName: { color: theme.textPrimary, fontSize: 15, fontWeight: '600' },
  eventRow: { flexDirection: 'row', alignItems: 'flex-start', gap: 10, paddingVertical: 7 },
  eventDot: { width: 9, height: 9, borderRadius: 5, marginTop: 5 },
  eventTitle: { color: theme.textPrimary, fontSize: 14, fontWeight: '600' },
  eventTime: { color: theme.textSecondary, fontSize: 12 },
  footer: { color: theme.textSecondary, fontSize: 11, textAlign: 'center', marginTop: 6 },
});
