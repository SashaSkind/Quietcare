import React, { useState } from 'react';
import {
  Pressable,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';
import { theme } from '../design/theme';
import { DEMO_USERS, type DemoUser, type Role } from './session';

// Login screen with two one-tap demo accounts. The email/password fields are
// presentational (the demo buttons below sign you in directly).
export function LoginScreen({ onLogin }: { onLogin: (user: DemoUser) => void }) {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');

  const loginAs = (role: Role) => () => {
    const user = DEMO_USERS[role];
    setEmail(user.email);
    onLogin(user);
  };

  return (
    <View style={styles.root}>
      <View style={styles.brand}>
        <View style={styles.logoDot} />
        <Text style={styles.brandName}>Quietcare</Text>
        <Text style={styles.brandTag}>Calm care for the people you love</Text>
      </View>

      <View style={styles.card}>
        <Text style={styles.label}>Email</Text>
        <TextInput
          style={styles.input}
          placeholder="you@example.com"
          placeholderTextColor={theme.textSecondary}
          autoCapitalize="none"
          keyboardType="email-address"
          value={email}
          onChangeText={setEmail}
        />
        <Text style={styles.label}>Password</Text>
        <TextInput
          style={styles.input}
          placeholder="••••••••"
          placeholderTextColor={theme.textSecondary}
          secureTextEntry
          value={password}
          onChangeText={setPassword}
        />
        <Pressable style={({ pressed }) => [styles.signIn, pressed && styles.pressed]}>
          <Text style={styles.signInText}>Sign in</Text>
        </Pressable>

        <View style={styles.divider}>
          <View style={styles.line} />
          <Text style={styles.dividerText}>demo accounts</Text>
          <View style={styles.line} />
        </View>

        <Pressable
          style={({ pressed }) => [styles.demoBtn, styles.caretakerBtn, pressed && styles.pressed]}
          onPress={loginAs('caretaker')}
        >
          <Text style={styles.demoEmoji}>🧑‍⚕️</Text>
          <View>
            <Text style={styles.demoTitle}>Continue as Caretaker</Text>
            <Text style={styles.demoSub}>Jack · sees the dashboard</Text>
          </View>
        </Pressable>

        <Pressable
          style={({ pressed }) => [styles.demoBtn, styles.elderBtn, pressed && styles.pressed]}
          onPress={loginAs('elder')}
        >
          <Text style={styles.demoEmoji}>👵</Text>
          <View>
            <Text style={styles.demoTitle}>Continue as Elder</Text>
            <Text style={styles.demoSub}>Margaret · the Halo companion</Text>
          </View>
        </Pressable>
      </View>

      <Text style={styles.footer}>No password needed — these are demo logins.</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  root: {
    flex: 1,
    backgroundColor: theme.bg,
    paddingHorizontal: 24,
    justifyContent: 'center',
  },
  brand: { alignItems: 'center', marginBottom: 28 },
  logoDot: {
    width: 56,
    height: 56,
    borderRadius: 28,
    backgroundColor: theme.accent,
    marginBottom: 12,
  },
  brandName: { color: theme.textPrimary, fontSize: 30, fontWeight: '900', letterSpacing: 0.5 },
  brandTag: { color: theme.textSecondary, fontSize: 15, marginTop: 4 },
  card: {
    backgroundColor: 'rgba(255,255,255,0.04)',
    borderRadius: 24,
    borderWidth: 1,
    borderColor: 'rgba(255,255,255,0.08)',
    padding: 20,
    gap: 8,
  },
  label: { color: theme.textSecondary, fontSize: 13, fontWeight: '600', marginTop: 4 },
  input: {
    backgroundColor: 'rgba(255,255,255,0.06)',
    borderRadius: 12,
    borderWidth: 1,
    borderColor: 'rgba(255,255,255,0.10)',
    paddingHorizontal: 14,
    paddingVertical: 12,
    color: theme.textPrimary,
    fontSize: 16,
  },
  signIn: {
    backgroundColor: 'rgba(255,255,255,0.10)',
    borderRadius: 12,
    paddingVertical: 14,
    alignItems: 'center',
    marginTop: 12,
  },
  signInText: { color: theme.textPrimary, fontSize: 16, fontWeight: '700' },
  divider: { flexDirection: 'row', alignItems: 'center', gap: 10, marginVertical: 14 },
  line: { flex: 1, height: 1, backgroundColor: 'rgba(255,255,255,0.10)' },
  dividerText: { color: theme.textSecondary, fontSize: 12, textTransform: 'uppercase', letterSpacing: 1 },
  demoBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 14,
    borderRadius: 16,
    paddingVertical: 16,
    paddingHorizontal: 18,
    marginTop: 10,
  },
  caretakerBtn: { backgroundColor: theme.accent },
  elderBtn: { backgroundColor: 'rgba(165,180,252,0.18)', borderWidth: 1, borderColor: 'rgba(165,180,252,0.4)' },
  demoEmoji: { fontSize: 26 },
  demoTitle: { color: theme.textPrimary, fontSize: 17, fontWeight: '800' },
  demoSub: { color: theme.textSecondary, fontSize: 13, marginTop: 1 },
  pressed: { opacity: 0.75 },
  footer: { color: theme.textSecondary, fontSize: 12, textAlign: 'center', marginTop: 22 },
});
