import React from 'react';
import { StyleSheet, Text, View } from 'react-native';
import type { AppStatus } from '../types';

const CONFIG: Record<AppStatus, { label: string; color: string }> = {
  all_good: { label: 'All good', color: '#16a34a' },
  checking_in: { label: 'Checking in…', color: '#d97706' },
  alerting: { label: 'Alerting caretaker…', color: '#dc2626' },
};

export function StatusBanner({ status }: { status: AppStatus }) {
  const { label, color } = CONFIG[status];
  return (
    <View style={[styles.banner, { backgroundColor: color }]}>
      <Text style={styles.text}>{label}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  banner: {
    width: '100%',
    paddingVertical: 36,
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: 16,
  },
  text: {
    color: '#ffffff',
    fontSize: 30,
    fontWeight: '700',
  },
});
