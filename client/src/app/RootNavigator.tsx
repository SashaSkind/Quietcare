import React, { useState } from 'react';
import { SafeAreaView, StatusBar, StyleSheet } from 'react-native';
import { theme } from '../design/theme';
import { LoginScreen } from './LoginScreen';
import { AgentFlowScreen } from '../caretaker/AgentFlowScreen';
import { CaretakerDashboard } from '../caretaker/CaretakerDashboard';
import { ElderPickerScreen } from '../caretaker/ElderPickerScreen';
import { ElderScreen } from '../elder/ElderScreen';
import type { DemoUser } from './session';

// Role-based root: login -> (caretaker: pick elder -> dashboard | elder Halo).
// There's no real auth; the login screen offers one-tap demo accounts.
export function RootNavigator() {
  const [user, setUser] = useState<DemoUser | null>(null);
  // Which resident the caretaker is currently viewing (null = picker screen).
  const [selectedElder, setSelectedElder] = useState<string | null>(null);
  const [showAgentFlow, setShowAgentFlow] = useState(false);

  const logout = () => {
    setSelectedElder(null);
    setShowAgentFlow(false);
    setUser(null);
  };

  const renderCaretaker = (u: DemoUser) => {
    if (selectedElder == null) {
      return <ElderPickerScreen user={u} onSelect={setSelectedElder} onLogout={logout} />;
    }
    if (showAgentFlow) {
      return (
        <AgentFlowScreen
          elderId={selectedElder}
          onBack={() => setShowAgentFlow(false)}
          onLogout={logout}
        />
      );
    }
    return (
      <CaretakerDashboard
        user={u}
        elderId={selectedElder}
        onBack={() => setSelectedElder(null)}
        onLogout={logout}
        onShowAgentFlow={() => setShowAgentFlow(true)}
      />
    );
  };

  return (
    <SafeAreaView style={styles.safe}>
      <StatusBar barStyle="light-content" />
      {!user ? (
        <LoginScreen onLogin={setUser} />
      ) : user.role === 'caretaker' ? (
        renderCaretaker(user)
      ) : (
        <ElderScreen user={user} onLogout={logout} />
      )}
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: theme.bg },
});
