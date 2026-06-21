import React from 'react';
import {
  Pressable,
  SafeAreaView,
  StatusBar,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { initSentry, Sentry } from './src/sentry';
import { useQuietcare } from './src/hooks/useQuietcare';
import { StatusBanner } from './src/components/StatusBanner';
import { DebugLog } from './src/components/DebugLog';

initSentry();

function App() {
  const { status, connection, accelMagnitude, logs, simulateFall } =
    useQuietcare();

  return (
    <SafeAreaView style={styles.safe}>
      <StatusBar barStyle="light-content" />
      <View style={styles.container}>
        <View style={styles.header}>
          <Text style={styles.title}>Quietcare</Text>
          <Text style={styles.meta}>
            ws: {connection} · |a|: {accelMagnitude.toFixed(2)} g
          </Text>
        </View>

        <StatusBanner status={status} />

        <Pressable
          style={({ pressed }) => [styles.button, pressed && styles.buttonPressed]}
          onPress={simulateFall}
        >
          <Text style={styles.buttonText}>Simulate Fall</Text>
        </Pressable>

        <DebugLog logs={logs} />
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: {
    flex: 1,
    backgroundColor: '#0f172a',
  },
  container: {
    flex: 1,
    padding: 16,
    gap: 16,
  },
  header: {
    alignItems: 'center',
  },
  title: {
    color: '#f8fafc',
    fontSize: 22,
    fontWeight: '800',
  },
  meta: {
    color: '#94a3b8',
    fontSize: 13,
    marginTop: 2,
  },
  button: {
    backgroundColor: '#dc2626',
    paddingVertical: 24,
    borderRadius: 16,
    alignItems: 'center',
  },
  buttonPressed: {
    opacity: 0.8,
  },
  buttonText: {
    color: '#ffffff',
    fontSize: 24,
    fontWeight: '800',
  },
});

// Sentry.wrap enables native crash + error reporting around the root component.
export default Sentry.wrap(App);
