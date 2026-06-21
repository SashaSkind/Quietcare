import React, { useEffect, useRef } from 'react';
import { ScrollView, StyleSheet, Text, View } from 'react-native';
import type { LogEntry } from '../hooks/useQuietcare';

const COLORS: Record<LogEntry['direction'], string> = {
  in: '#38bdf8',
  out: '#a3e635',
  info: '#94a3b8',
};

const PREFIX: Record<LogEntry['direction'], string> = {
  in: '<<',
  out: '>>',
  info: '··',
};

export function DebugLog({ logs }: { logs: LogEntry[] }) {
  const scrollRef = useRef<ScrollView>(null);

  useEffect(() => {
    scrollRef.current?.scrollToEnd({ animated: true });
  }, [logs]);

  return (
    <View style={styles.container}>
      <Text style={styles.title}>Debug log</Text>
      <ScrollView
        ref={scrollRef}
        style={styles.scroll}
        contentContainerStyle={styles.content}
      >
        {logs.map((entry) => (
          <Text key={entry.id} style={[styles.line, { color: COLORS[entry.direction] }]}>
            {entry.ts} {PREFIX[entry.direction]} {entry.text}
          </Text>
        ))}
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    width: '100%',
    backgroundColor: '#0b1220',
    borderRadius: 12,
    padding: 12,
  },
  title: {
    color: '#e2e8f0',
    fontWeight: '700',
    marginBottom: 8,
  },
  scroll: {
    flex: 1,
  },
  content: {
    paddingBottom: 8,
  },
  line: {
    fontFamily: 'monospace',
    fontSize: 11,
    marginBottom: 2,
  },
});
