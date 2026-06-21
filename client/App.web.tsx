import React from 'react';
import { StyleSheet, View } from 'react-native';
import { RootNavigator } from './src/app/RootNavigator';

// Web-only entry (Metro resolves App.web.tsx on web). Renders the same
// role-based demo (login -> caretaker dashboard | elder Halo) inside a phone
// frame for browser review + Playwright capture. Accelerometer fall detection
// is a graceful no-op on web (no sensor), so the "Simulate Fall" control is
// used there instead.
export default function App() {
  return (
    <View style={styles.page}>
      <View style={styles.phone}>
        <RootNavigator />
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
