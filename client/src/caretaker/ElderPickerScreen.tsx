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
import { careApi, type ElderSummaryItem } from './api';

// First screen a caretaker sees after login: pick which elder to care for.
// Caretakers often look after more than one person, so we list every
// provisioned elder and let them choose before opening the dashboard.
export function ElderPickerScreen({
  user,
  onSelect,
  onLogout,
}: {
  user: DemoUser;
  onSelect: (elderId: string) => void;
  onLogout: () => void;
}) {
  const [elders, setElders] = useState<ElderSummaryItem[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const mounted = useRef(true);

  const load = useCallback(async () => {
    try {
      const list = await careApi.listElders();
      if (!mounted.current) return;
      setElders(list);
      setError(null);
    } catch (e) {
      if (mounted.current) setError(String((e as Error).message || e));
    }
  }, []);

  useEffect(() => {
    mounted.current = true;
    void load();
    return () => {
      mounted.current = false;
    };
  }, [load]);

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    await load();
    setRefreshing(false);
  }, [load]);

  return (
    <View style={styles.root}>
      <View style={styles.header}>
        <View>
          <Text style={styles.brand}>Quietcare</Text>
          <Text style={styles.role}>Caretaker · {user.name}</Text>
        </View>
        <Pressable style={styles.logout} onPress={onLogout}>
          <Text style={styles.logoutText}>Log out</Text>
        </Pressable>
      </View>

      <Text style={styles.title}>Who are you caring for?</Text>
      <Text style={styles.subtitle}>Choose a resident to open their dashboard.</Text>

      {!elders && !error && (
        <View style={styles.center}>
          <ActivityIndicator color={theme.accent} />
          <Text style={styles.muted}>Loading residents…</Text>
        </View>
      )}

      {error && !elders && (
        <View style={styles.center}>
          <Text style={styles.errTitle}>Can't reach the backend</Text>
          <Text style={styles.muted}>{error}</Text>
          <Text style={styles.muted}>Check EXPO_PUBLIC_API_URL (LAN IP:8080).</Text>
        </View>
      )}

      {elders && (
        <ScrollView
          contentContainerStyle={styles.scroll}
          refreshControl={
            <RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={theme.accent} />
          }
        >
          {elders.length === 0 ? (
            <Text style={styles.muted}>No residents provisioned yet.</Text>
          ) : (
            elders.map((e) => {
              const name = e.profile?.name ?? e.elder_id;
              const conditions = (e.profile?.conditions ?? []).join(', ');
              return (
                <Pressable
                  key={e.elder_id}
                  style={({ pressed }) => [styles.elderCard, pressed && styles.pressed]}
                  onPress={() => onSelect(e.elder_id)}
                >
                  <View style={styles.avatar}>
                    <Text style={styles.avatarText}>{name.slice(0, 1).toUpperCase()}</Text>
                  </View>
                  <View style={{ flex: 1 }}>
                    <Text style={styles.elderName}>{name}</Text>
                    <Text style={styles.muted}>
                      {e.profile?.age ? `${e.profile.age} · ` : ''}
                      {conditions || 'no conditions on file'}
                    </Text>
                  </View>
                  <Text style={styles.chevron}>›</Text>
                </Pressable>
              );
            })
          )}
        </ScrollView>
      )}
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
  title: { color: theme.textPrimary, fontSize: 26, fontWeight: '900', paddingHorizontal: 20, marginTop: 8 },
  subtitle: { color: theme.textSecondary, fontSize: 14, paddingHorizontal: 20, marginTop: 4 },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center', gap: 8, padding: 24 },
  errTitle: { color: '#fb7185', fontSize: 16, fontWeight: '700' },
  muted: { color: theme.textSecondary, fontSize: 13 },
  scroll: { padding: 16, gap: 12, paddingBottom: 40 },
  elderCard: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 14,
    backgroundColor: 'rgba(255,255,255,0.04)',
    borderRadius: 18,
    borderWidth: 1,
    borderColor: 'rgba(255,255,255,0.08)',
    padding: 16,
  },
  pressed: { opacity: 0.7 },
  avatar: {
    width: 52,
    height: 52,
    borderRadius: 26,
    backgroundColor: 'rgba(192,132,252,0.22)',
    alignItems: 'center',
    justifyContent: 'center',
  },
  avatarText: { color: theme.accent, fontSize: 22, fontWeight: '900' },
  elderName: { color: theme.textPrimary, fontSize: 19, fontWeight: '800' },
  chevron: { color: theme.textSecondary, fontSize: 28, fontWeight: '300' },
});
