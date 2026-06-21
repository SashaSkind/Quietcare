import React, { useState } from 'react';
import { SafeAreaView, StatusBar, StyleSheet } from 'react-native';
import { theme } from '../design/theme';
import { LoginScreen } from './LoginScreen';
import { CaretakerDashboard } from '../caretaker/CaretakerDashboard';
import { ElderScreen } from '../elder/ElderScreen';
import type { DemoUser } from './session';

// Role-based root: login -> (caretaker dashboard | elder Halo companion).
// There's no real auth; the login screen offers one-tap demo accounts.
export function RootNavigator() {
  const [user, setUser] = useState<DemoUser | null>(null);
  const logout = () => setUser(null);

  return (
    <SafeAreaView style={styles.safe}>
      <StatusBar barStyle="light-content" />
      {!user ? (
        <LoginScreen onLogin={setUser} />
      ) : user.role === 'caretaker' ? (
        <CaretakerDashboard user={user} onLogout={logout} />
      ) : (
        <ElderScreen user={user} onLogout={logout} />
      )}
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: theme.bg },
});
