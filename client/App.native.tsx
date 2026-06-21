import React from 'react';
import { SafeAreaView, StatusBar, StyleSheet } from 'react-native';
import { DemoScreen } from './src/design/DemoScreen';
import { theme } from './src/design/theme';

// Native entry (Metro resolves App.native.tsx on iOS/Android). This renders the
// chosen elder-facing DESIGN (Halo) demo flow full-screen. It uses only React
// Native core primitives, so it runs in Expo Go without a custom dev client —
// scan the `expo start` QR to see the demo on a phone.
//
// The full real client (sensors / camera / websocket) still lives in App.tsx
// and is wired in separately; this entry is the design/demo experience.
export default function App() {
  return (
    <SafeAreaView style={styles.safe}>
      <StatusBar barStyle="light-content" />
      <DemoScreen />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: theme.bg },
});
