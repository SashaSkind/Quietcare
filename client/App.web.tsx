import React from 'react';
import { StyleSheet, View } from 'react-native';
import { DemoScreen } from './src/design/DemoScreen';

// Web-only entry (Metro resolves App.web.tsx on web). This renders the
// elder-facing DESIGN PREVIEW inside a phone frame and avoids importing any
// native-only modules (camera/av/sensors/sentry), so it runs cleanly in the
// browser for design review + Playwright video capture. The real native app
// stays in App.tsx untouched.
export default function App() {
  return (
    <View style={styles.page}>
      <View style={styles.phone}>
        <DemoScreen />
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  page: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#05080c',
    // @ts-ignore web-only
    minHeight: '100vh',
  },
  phone: {
    width: 414,
    height: 896,
    borderRadius: 44,
    overflow: 'hidden',
    backgroundColor: '#000',
    borderWidth: 10,
    borderColor: '#11161d',
    // @ts-ignore web-only
    boxShadow: '0 30px 80px rgba(0,0,0,0.6)',
  },
});
